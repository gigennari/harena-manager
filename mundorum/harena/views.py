from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User
from google.oauth2 import id_token
from google.auth.transport import requests
from .models import Person, InstitutionDomain, ProfessorInviteToken, Quest, Case, QuestCase, QuestAccessToken
from django.db.models import Q
from django.contrib.auth.models import User, Group
from .serializers import QuestSerializer,CaseSerializer, PersonSerializer, InstitutionSerializer, ProfessorInviteTokenSerializer, QuestAccessTokenSerializer
from django.core.mail import send_mail
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import PermissionDenied
import uuid
import re
import json
import logging
logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

def send_invite_email(professor_invite_token):

    link = f"{settings.CLIENT_URL}/invite/professor/{professor_invite_token.token}/"

    subject = "Professor Invitation"
    message = (
        f"You have been invited to join {professor_invite_token.institution.name}.\n\n"
        f"Click the link below to accept the invitation:\n\n"
        f"{link}\n\n"
        "Best regards,\n"
        "The Team"
    )

    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [professor_invite_token.email]

    send_mail(
        subject=subject,
        message=message,
        from_email=from_email,
        recipient_list=recipient_list,
        fail_silently=False
    )


class GoogleAuthView(APIView):
    permission_classes = [AllowAny]

    @staticmethod
    def get_institution_from_email(email):
        domain = email.split('@')[-1]
        try:
            # Assuming InstitutionDomain.domain is the field storing the domain
            institution_domain = InstitutionDomain.objects.get(name=domain)
            return institution_domain.institution
        except InstitutionDomain.DoesNotExist:
            return None

    @staticmethod
    def check_institution_valid(institution):
        if institution is None:
            # Raise an exception that post() can specifically catch and turn into a 403
            raise ValueError("This email domain is not registered to any institution.") 
        if not institution.active:
            # Raise an exception for inactive institution
            raise ValueError("This institution is currently inactive.")

    def post(self, request):
        print("Received Google authentication request with data:", request.data)
        google_token = request.data.get('token')
        professor_invite_token = request.data.get('invite_token', None)
        quest_invite_token = request.data.get('quest_invite_token', None)

        if not google_token:
            return Response({'error': 'Google token is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 1. Verify Google token
            idinfo = id_token.verify_oauth2_token(
                google_token,
                requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )

            google_id = idinfo['sub']
            email = idinfo['email']
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')
            profile_picture = idinfo.get('picture', '')

            # 2. Get or create User and Person
            user, user_created = User.objects.get_or_create(email=email, defaults={
                'username': email.split('@')[0], # Use part of the email as default username
                'first_name': first_name,
                'last_name': last_name
            })
            # If the generated username already exists, add a suffix to make it unique
            if user_created and User.objects.filter(username=user.username).count() > 1:
                user.username = f"{user.username}_{google_id[:8]}"
                user.save()

            person, person_created = Person.objects.get_or_create(user=user, defaults={
                'google_id': google_id,
                'profile_picture': profile_picture,
                'role': 'guest' # Default initial role
            })
            # Update google_id and profile_picture for existing users
            person.google_id = google_id
            person.profile_picture = profile_picture
            person_modified = False # Flag to track if person needs to be saved

            # --- Authentication Flow Logic ---

            # PRIORITY 1: Professor Invite Token
            if professor_invite_token:
                try:
                    professor_token = ProfessorInviteToken.objects.get(token=professor_invite_token)

                    if not professor_token.is_valid():
                        return Response({'error': 'Professor Invite Token has expired or is invalid.'}, status=status.HTTP_400_BAD_REQUEST)

                    # Check if the user's email matches the token's email
                    if email.lower() != professor_token.email.lower():
                        return Response({'error': 'This Professor Invite Token is not for your email address.'}, status=status.HTTP_403_FORBIDDEN)

                    # Check and validate the token's institution
                    self.check_institution_valid(professor_token.institution) # This might now return a Response directly

                    # Assign institution and professor role
                    person.institution = professor_token.institution
                    person.role = 'professor'
                    person_modified = True

                    # Mark token as used (or delete, depending on your rule)
                    professor_token.delete() # Consumes the token

                except ProfessorInviteToken.DoesNotExist:
                    return Response({'error': 'Invalid Professor Invite Token.'}, status=status.HTTP_404_NOT_FOUND)
                except PermissionDenied as e: # Catch PermissionDenied from check_institution_valid
                    return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
                except Exception as e:
                    logger.exception("Error processing Professor Invite Token:")
                    return Response({'error': 'An error occurred while processing professor invite token.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # PRIORITY 2: Quest Access Token
            elif quest_invite_token:
                try:
                    quest_access_token = QuestAccessToken.objects.get(token=quest_invite_token)

                    if not quest_access_token.is_valid():
                        return Response({'error': 'Quest Access Token has expired or reached maximum uses.'}, status=status.HTTP_400_BAD_REQUEST)

                    quest = quest_access_token.quest

                    # Rule 3.1: If token role is 'student' or 'professor', user must already have an institutional account
                    if quest_access_token.role in ['student', 'professor']:
                        # Check if user has an institution AND if it matches the quest's institution
                        if not person.institution or person.institution != quest.institution:
                            return Response({'error': 'This Quest Access Token is only valid for users already associated with this quest\'s institution.'}, status=status.HTTP_403_FORBIDDEN)
                        
                        # If the token's role is higher than the current role, update
                        role_order = ['guest', 'student', 'professor']
                        if role_order.index(quest_access_token.role) > role_order.index(person.role):
                            person.role = quest_access_token.role
                            person_modified = True

                    # Rule 3.2: If token role is 'guest', user can be new or existing
                    elif quest_access_token.role == 'guest':
                        # If the user has no institution, link to the quest's institution
                        if person.institution is None:
                            person.institution = quest.institution
                            person_modified = True
                        # If current role is 'student' or 'professor', do not downgrade to 'guest'
                        if person.role == 'guest': # Only set if already guest or new
                            person.role = 'guest'
                            person_modified = True

                    # Add user to the quest's group
                    group_name = f"{quest_access_token.group}_{quest.id}" # E.g.: viewers_UUID, authors_UUID, editors_UUID
                    group, created_group = Group.objects.get_or_create(name=group_name)
                    user.groups.add(group)

                    # Track token usage
                    quest_access_token.used_by.add(person)
                    # Optional: Decrement max_uses if you want a strict count here
                    # if quest_access_token.max_uses is not None:
                    #     quest_access_token.max_uses -= 1
                    #     quest_access_token.save() # Save the token if max_uses was changed

                except QuestAccessToken.DoesNotExist:
                    return Response({'error': 'Invalid Quest Access Token.'}, status=status.HTTP_404_NOT_FOUND)
                except Exception as e:
                    logger.exception("Error processing Quest Access Token:")
                    return Response({'error': 'An error occurred while processing quest access token.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # PRIORITY 3: Standard Flow (Login without invite token)
            else:
                # Get institution from email
                institution = self.get_institution_from_email(email)

                # Rule 1: Validate institution for standard login
                # NOTE: check_institution_valid now returns a Response directly on failure
                response_from_check = self.check_institution_valid(institution)
                if response_from_check: # If it returned a Response (an error)
                    return response_from_check

                # Assign institution
                if person.institution is None or person.institution != institution:
                    person.institution = institution
                    person_modified = True
                
                # Set default role to 'student' if not already a higher role
                if person.role == 'guest': # Only if guest, do not downgrade professor/student
                    person.role = 'student'
                    person_modified = True

            # Save the Person instance if there were any modifications
            if person_modified:
                person.save()

            # 4. Create or get the DRF authentication token
            drf_token, created_drf_token = Token.objects.get_or_create(user=user)

            # Return user and institution data
            return Response({
                'token': drf_token.key,
                'person': PersonSerializer(person).data,
                "institution": InstitutionSerializer(person.institution).data,
            })


        except ValueError:
            return Response({'error': 'Invalid Google token'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            logger.exception("General error during Google authentication:")
            return Response({'error': 'An unexpected error occurred during authentication.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        
"""
class GoogleAuthView(APIView):
    permission_classes = [AllowAny]

    @staticmethod
    def get_institution_from_email(email):
        domain = email.split('@')[-1]
        try:
            institution_domain = InstitutionDomain.objects.get(name=domain)
            return institution_domain.institution
        except InstitutionDomain.DoesNotExist:
            return None

    @staticmethod
    def check_institution_valid(institution):
        if institution is None:
            raise Exception("This domain is not registered to any institution.")
        if not institution.active:
            raise Exception("This institution is currently inactive.")

    def post(self, request):
        google_token = request.data.get('token')
        professor_invite_token = request.data.get('invite_token', None)
        quest_invite_token = request.data.get('quest_invite_token', None)

        if not google_token:
            return Response({'error': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Verify Google token
            idinfo = id_token.verify_oauth2_token(
                google_token,
                requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )

            google_id = idinfo['sub']
            email = idinfo['email']
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')
            profile_picture = idinfo.get('picture', '')

            # Get or create user
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                username = email.split('@')[0]
                if User.objects.filter(username=username).exists():
                    username = f"{username}_{google_id[:8]}"

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name
                )

            # Get or create person
            person, created = Person.objects.get_or_create(user=user)
            person.google_id = google_id
            person.profile_picture = profile_picture

            # 1️⃣ If using ProfessorInviteToken
            if professor_invite_token:
                try:
                    token = ProfessorInviteToken.objects.get(token=professor_invite_token)

                    if not token.is_valid():
                        return Response({'error': 'Expired Token'}, status=400)

                    self.check_institution_valid(token.institution)

                    person.institution = token.institution
                    person.role = 'professor'
                    person.save()

                    token.is_used = True
                    token.save()

                except ProfessorInviteToken.DoesNotExist:
                    return Response({'error': 'Invalid Professor Invite Token'}, status=400)
                except Exception as e:
                    return Response({'error': str(e)}, status=403)

            # 2️⃣ If using QuestAccessToken
            elif quest_invite_token:
                try:
                    token = QuestAccessToken.objects.get(token=quest_invite_token)

                    if not token.is_valid():
                        return Response({'error': 'Expired or Invalid Quest Token'}, status=400)

                    quest = token.quest

                    # If the user is already registered, we check if the token is valid for existing users
                    if created and (token.role == 'student' or token.role == 'professor'):
                        if person.institution != quest.institution:
                            return Response({'error': 'This token is only valid for existing users and for quests within your institution'}, status=403)

                    # If the user is new and the token is for a guest role
                    if created and token.role == 'guest':
                        person.role = 'guest'

                    #This guard ensures that the person is associated with the quest's institution, but also allows guests to see quests that are visible to all in the institution
                    if person.institution is None:
                        person.institution = quest.institution

                    person.save()

                    # Adds user to the appropriate group based on the token's group
                    group_name = f"{token.group}s_{quest.id}"  # ex: viewers_xx
                    group = Group.objects.get(name=group_name)
                    group.user_set.add(user)

                    token.used_by.add(person)
                    token.save()

                except QuestAccessToken.DoesNotExist:
                    return Response({'error': 'Invalid Quest Invite Token'}, status=400)
                except Exception as e:
                    return Response({'error': str(e)}, status=403)

            # 3️⃣ Default flow (institution from email domain)
            else:
                institution = self.get_institution_from_email(email)

                try:
                    self.check_institution_valid(institution)
                except Exception as e:
                    return Response({'error': str(e)}, status=403)

                person.institution = institution
                if not person.role:
                    person.role = 'student' # Default role for new users
                person.save()

            # Create or get authentication token
            token, created = Token.objects.get_or_create(user=user)

            return Response({
                'token': token.key,
                'user': PersonSerializer(person).data,
                "institution": InstitutionSerializer(person.institution).data,
            })

        except ValueError:
            return Response({'error': 'Invalid Google token'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
"""

"""
This API view lists all users from an insitution.
"""
class UserView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        institution_id = self.request.query_params.get('institution')
        queryset = Person.objects.all()
        if institution_id:
            queryset = queryset.filter(institution_id=institution_id)
        return queryset

    def get(self, request):
        user = request.user

        if not user.is_authenticated:
            return Response({'error': 'Not authenticated'}, status=status.HTTP_401_UNAUTHORIZED)

        return Response({
            'id': user.id,
            'email': user.email,
            'name': f"{user.first_name} {user.last_name}".strip(),
            'picture': user.person.profile_picture if hasattr(user, 'person') else None
        })

# Helper function to check if a user can view a quest
def user_can_view_quest(user, quest):
    person = user.person
    group_names = user.groups.values_list('name', flat=True)

    return (
        quest.owner == person or
        (quest.visible_to_institution and quest.institution == person.institution) or
        any(g in group_names for g in [
            f"viewers_{quest.id}",
            f"authors_{quest.id}",
            f"editors_{quest.id}",
        ])
    )

# helper function to check if a user can add cases to a quest
def user_can_add_cases_to_quest(user, quest):
    person = user.person
    group_names = user.groups.values_list('name', flat=True)

    return (
        quest.owner == person or
        f"authors_{quest.id}" in group_names or
        f"editors_{quest.id}" in group_names
    )

# Helper function to check if a user can edit a quest
def user_can_edit_quest(user, quest):
    person = user.person
    group_names = user.groups.values_list('name', flat=True)
    return (
        quest.owner == person or
        f"editors_{quest.id}" in group_names
    )


def can_delete_quest(user, quest):
    person = user.person
    return (
        quest.owner == person
    )

"""
This API view Lists all quests that the user can view, either by being the owner, part of the institution, or via group membership.
"""
class QuestListView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        quests = Quest.objects.all()

        # Filter quests based on user permissions
        visible_quests = [quest for quest in quests if user_can_view_quest(user, quest)]
        print(f"User {user.username} can view {len(visible_quests)} quests.")
        serializer = QuestSerializer(visible_quests, many=True)
        return Response(serializer.data)
   
        

"""
This API view allows users to retrieve all cases associated with a specific quest.
"""
class QuestCasesView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, quest_id):
        try:
            quest = Quest.objects.get(id=quest_id)
        except Quest.DoesNotExist:
            return Response({'error': 'Quest not found'}, status=404)


        # Lista cases associated with the quest
        quest_cases = quest.quest_cases.select_related('case').all()
        cases = [qc.case for qc in quest_cases]
        serializer = CaseSerializer(cases, many=True)
        return Response(serializer.data)
    
"""
This API view allows users to add a case to a quest.
Only users who can edit the quest (quest owner, authors editors) can perform this action.
"""
class AddCaseToQuestView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, quest_id):
        try:
            quest = Quest.objects.get(id=quest_id)
        except Quest.DoesNotExist:
            return Response({'error': 'Quest not found'}, status=404)

        if not user_can_add_cases_to_quest(request.user, quest):
            return Response({'error': 'You do not have permission to add cases to this quest'}, status=403)

        case_id = request.data.get('case_id')
        if not case_id:
            return Response({'error': 'Case ID is required'}, status=400)

        try:
            case = Case.objects.get(id=case_id)
        except Case.DoesNotExist:
            return Response({'error': 'Case not found'}, status=404)

        if QuestCase.objects.filter(quest=quest, case=case).exists():
            return Response({'info': 'This case is already part of this quest'}, status=200)

        QuestCase.objects.create(quest=quest, case=case)
        return Response({'success': f'Case {case.name} added to quest {quest.name}'}, status=201)
    

"""
This API view allows users to remove a case from a quest.
Only users who can edit the quest (owners or editors) can perform this action.
"""
class RemoveCaseFromQuestView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, quest_id, case_id):
        user = request.user
        
        try:
            quest = Quest.objects.get(id=quest_id)
        except Quest.DoesNotExist:
            return Response({"error": "Quest not found."}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            case = Case.objects.get(id=case_id)
        except Case.DoesNotExist:
            return Response({"error": "Case not found."}, status=status.HTTP_404_NOT_FOUND)

        # Check if the user has permission to edit this quest
        if not user_can_edit_quest(user, quest):
            return Response({'error': 'You do not have permission to remove cases from this quest.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            # Find the specific QuestCase entry
            quest_case = QuestCase.objects.get(quest=quest, case=case)
            quest_case.delete() # Delete the association
            return Response(status=status.HTTP_204_NO_CONTENT) # 204 means no content, successful deletion
        except QuestCase.DoesNotExist:
            return Response({"error": "Case is not associated with this quest."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Error deleting QuestCase: {e}")
            return Response({"error": "An error occurred while removing the case from the quest."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


"""
This API view allows users to create a Quest Access Token.
The token can be used to invite other users to access a quest with specific roles and group permissions.
Roles can be 'guest', 'student', or 'professor'.
Group can be 'view', 'author', or 'editor' as per GROUP_CHOICES.
The token can have a maximum number of uses and an expiration date.
"""
class CreateQuestAccessTokenView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication] # Ensure TokenAuthentication is used

    def post(self, request):
        quest_id = request.data.get('quest')
        role = request.data.get('role', 'guest')
        group_name = request.data.get('group', 'view') # Default to 'view' as per GROUP_CHOICES
        max_uses = request.data.get('max_uses')
        expires_at_str = request.data.get('expires_at') 

        if not quest_id:
            return Response({'error': 'Quest ID is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not expires_at_str:
            return Response({'error': 'Expiration date is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            quest = Quest.objects.get(id=quest_id)
        except Quest.DoesNotExist:
            return Response({'error': 'Quest not found'}, status=status.HTTP_404_NOT_FOUND)

        person = request.user.person # Assuming request.user has a 'person' attribute

        # Permission check: Only quest owner or users in the 'editors_UUID' group can create tokens
        is_owner = quest.owner == person
        is_editor_group = request.user.groups.filter(name=f'editors_{quest_id}').exists()

        if not (is_owner or is_editor_group):
            return Response({'error': 'Permission denied. Only quest owners or editors can create invite tokens.'}, status=status.HTTP_403_FORBIDDEN)

        # Parse the expires_at ISO string
        try:
            # Replace 'Z' with '+00:00' for consistent parsing across Python versions
            # and ensure it's timezone-aware if USE_TZ is True
            expires_at = timezone.datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            if timezone.is_naive(expires_at):
                expires_at = timezone.make_aware(expires_at, timezone.utc)
        except ValueError:
            return Response({'error': 'Invalid expiration date format. Expected YYYY-MM-DDTHH:MM:SSZ'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate max_uses
        if max_uses is not None:
            try:
                max_uses = int(max_uses)
                if max_uses < 1:
                    return Response({'error': 'Max uses must be at least 1.'}, status=status.HTTP_400_BAD_REQUEST)
            except ValueError:
                return Response({'error': 'Max uses must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)

        token = QuestAccessToken.objects.create(
            quest=quest,
            role=role,
            group=group_name, # Use group_name here to match the model field
            expires_at=expires_at,
            max_uses=max_uses # Pass the validated max_uses
        )

        serializer = QuestAccessTokenSerializer(token)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


"""
API view to use a Quest Access Token.
"""
class UseQuestAccessTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        invite_token = request.data.get('invite_token')

        try:
            token = QuestAccessToken.objects.get(token=invite_token)

            if not token.is_valid():
                return Response({'error': 'Expired or Invalid Token'}, status=400)

            quest = token.quest
            person = request.user.person

            group_name = f"{token.group}s_{quest.id}"
            group = Group.objects.get(name=group_name)
            group.user_set.add(person.user)


            token.used_by.add(person)
            token.save()

            return Response({'message': 'Access granted to quest.'}, status=200)

        except QuestAccessToken.DoesNotExist:
            return Response({'error': 'Invalid Token'}, status=400)
        
"""
API view to create a new quest.
Only professors or institution owners can create quests.    
The quest will be associated with the user's institution.
The quest will be visible to the institution if specified.
"""
class CreateQuestView(APIView):
    
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        person = request.user.person

        if person.role != 'professor' and not person.institution:
            return Response({'error': 'Only professors or institution owners can create quests.'}, status=403)

        name = request.data.get('name')
        visible = request.data.get('visible_to_institution', False)

        if not name:
            return Response({'error': 'Name is required.'}, status=400)

        quest = Quest.objects.create(
            name=name,
            institution=person.institution,
            owner=person,
            visible_to_institution=visible
        )

        return Response({
            'id': str(quest.id),
            'name': quest.name,
            'visible_to_institution': quest.visible_to_institution,
            'institution': str(quest.institution.id),
            'created_at': quest.created_at
        }, status=201)
    

class CreateCaseView(APIView):
    """API view to create a new case.
    Only authenticated users can create cases.
    The case owner is automatically set to the authenticated user.  
    If a quest_id is provided, the case will be linked to that quest.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            person = request.user.person
            mutable_data = request.data.copy()
            mutable_data['case_owner'] = str(person.pk)

            serializer = CaseSerializer(data=mutable_data)

            print(f"Creating case for {person.user.username} with data: {mutable_data}")
            print(f"Files: {request.FILES}")
            if serializer.is_valid():
                case = serializer.save(case_owner=person)

                quest_id = mutable_data.get('quest_id')
                if quest_id:
                    try:
                        quest = Quest.objects.get(id=quest_id)
                        QuestCase.objects.create(case=case, quest=quest)
                    except Quest.DoesNotExist:
                        return Response(
                            {"error": "Quest not found."},
                            status=status.HTTP_404_NOT_FOUND
                        )

                return Response(CaseSerializer(case).data, status=status.HTTP_201_CREATED)
            else:
                print(f"Case creation failed for {person.user.username} with errors: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return Response(
                {"error": "An internal server error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class InviteProfessorView(APIView):
    """API view to invite a professor to an institution.
    Only institution owners can send invitations.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        person = request.user.person 

        if not email:
            return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        

        if person.pk != person.institution.owner.pk:
            return Response({"error": "Only institution owners can invite professors."}, status=status.HTTP_403_FORBIDDEN)
            
        if User.objects.filter(email=email).exists():
            return Response({"error": "A user with this email already exists."}, status=status.HTTP_409_CONFLICT)
        
        
        try:
            expires_in_days = int(request.data.get('expires_in_days', 7))

            invite_token_obj = ProfessorInviteToken.objects.create(
                email=email,
                institution=person.institution,
                expires_at=timezone.now() + timedelta(days=expires_in_days)
            )
            
            send_invite_email(invite_token_obj)
            
            return Response({"message": f"Invitation sent to {email} successfully."}, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            print(f"Error creating invite token: {e}")
            return Response({"error": "Could not send invitation."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserCaseListView(APIView):
    """API view to list all cases owned by the authenticated user.
    Accessible only by the user themselves.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        person = request.user.person
        cases = Case.objects.filter(case_owner=person).order_by('name')
        serializer = CaseSerializer(cases, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class QuestDetailView(APIView):
    """
    API view to retrieve a specific quest by its ID.
    Accessible only by the quest owner or users in the 'editors_UUID' group for that quest.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, quest_id):
        try:
            quest = Quest.objects.get(id=quest_id)
        except Quest.DoesNotExist:
                return Response({"error": "Quest not found."}, status=status.HTTP_400_BAD_REQUEST)
            

        if not user_can_view_quest(request.user, quest):
            return Response({'error': 'You do not have permission to view this quest'}, status=403)

        serializer = QuestSerializer(quest)
        return Response(serializer.data)
    
class EditableQuestListView(APIView):
    """API view to list all quests that the user can edit.
    This includes quests owned by the user and quests that the user can edit via group membership (editors_UUID).
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        try:
            person = user.person
        except AttributeError:
            print(f"DEBUG: User '{user.username}' (ID: {user.id}) does not have a linked Person object. Returning empty quests list.")
            return Response([], status=status.HTTP_200_OK)
       
        owner_quests = Quest.objects.filter(owner=person)

        user_groups = user.groups.all()
        
        editable_quest_ids = set()

        # Regex to get quest UUID from group name - 'authors_UUID' or 'editors_UUID'
        uuid_pattern = re.compile(r'^(?:authors|editors)_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$')

        for group in user_groups:
            match = uuid_pattern.match(group.name)
            if match:
                quest_uuid = match.group(1)
                editable_quest_ids.add(quest_uuid)
        
        #get quests that the user can edit via groups
        editable_quests_via_groups = Quest.objects.none() 
        if editable_quest_ids:
            editable_quests_via_groups = Quest.objects.filter(id__in=list(editable_quest_ids))

        # removes duplicates
        all_editable_quests = (owner_quests | editable_quests_via_groups).distinct()

        serializer = QuestSerializer(all_editable_quests, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class CaseDetailView(RetrieveUpdateDestroyAPIView):
    """"
    API view to retrieve, update, or delete a specific case.
    Accessible only by the case owner.
    """
    queryset = Case.objects.all()
    serializer_class = CaseSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Ensure only the case owner can retrieve, update, or delete their cases
        # This is crucial for security.
        return self.queryset.filter(case_owner=self.request.user.person)

class QuestAccessTokenListView(APIView):
    """
    API view to list all Quest Access Tokens for a specific quest.
    Accessible only by the quest owner or users in the 'editors_UUID' group for that quest.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = QuestAccessTokenSerializer 

    def get(self, request, quest_id, *args, **kwargs):
        
        user = request.user
        person = user.person 
        logger.debug(f"QUEST ACCESS TOKEN LIST: Received GET request for Quest ID: {quest_id}. User: {user.username} (ID: {user.id})")

        try:
            quest = Quest.objects.get(id=quest_id)
        except Quest.DoesNotExist:
            
            return Response({'error': 'Quest not found.'}, status=status.HTTP_404_NOT_FOUND)
       
        is_owner = False
        if (quest.owner.pk == request.user.person.pk):
            is_owner = True
        
        is_editor_group = user.groups.filter(name=f'editors_{quest_id}').exists()

        if not (is_owner or is_editor_group):
            return Response({'error': 'You do not have permission to view these tokens.'}, 
                            status=status.HTTP_403_FORBIDDEN)


        queryset = QuestAccessToken.objects.filter(quest=quest).order_by('-created_at')
        serializer = self.serializer_class(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
