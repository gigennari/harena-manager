from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User
from google.oauth2 import id_token
from google.auth.transport import requests
from .models import Person, InstitutionDomain, ProfessorInviteToken, Quest, QuestViewerInviteToken, Case, QuestCase, QuestAccessToken
from django.db.models import Q
from django.contrib.auth.models import Group
from .serializers import QuestSerializer,CaseSerializer
from django.core.mail import send_mail
from datetime import timedelta
from django.utils import timezone

def send_invite_email(professor_invite_token):

    link = f"{settings.CLIENT_URL}/invite/{professor_invite_token.token}/"

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

                    # Se o token exige que o usuário já exista
                    if created and token.role == 'other':
                        return Response({'error': 'This token is only valid for existing users'}, status=403)

                    # Se o usuário for novo e o token permitir 'guest', define o role como guest
                    if created and token.role == 'guest':
                        person.role = 'guest'

                    # Atribui instituição se ainda não tiver
                    if person.institution is None:
                        person.institution = quest.institution

                    person.save()

                    # Adiciona o user ao grupo (viewer/author/editor)
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
                person.role = 'student'
                person.save()

            # Create or get authentication token
            token, created = Token.objects.get_or_create(user=user)

            return Response({
                'token': token.key,
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'name': f"{user.first_name} {user.last_name}".strip(),
                    'picture': person.profile_picture,
                    'institution': person.institution.name if person.institution else None,
                    'role': person.role
                }
            })

        except ValueError:
            return Response({'error': 'Invalid Google token'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class UserView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    queryset = Person.objects.all()

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
    group_names = user.groups.values_list('name', flat=True)
    return (
        quest.owner == person
    )



#Lists all quests that the user can view, either by being the owner, part of the institution, or via group membership.
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
   
    
# Allows a user to use a token to gain access to view a quest.
class UseQuestViewerTokenView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token_value = request.data.get('token')

        if not token_value:
            return Response({'error': 'Token não enviado'}, status=400)

        try:
            token_obj = QuestViewerInviteToken.objects.get(token=token_value)

            if not token_obj.is_valid():
                return Response({'error': 'Token expirado'}, status=400)

            person = request.user.person
            quest = token_obj.quest

            group = Group.objects.get(name=f"viewers_{quest.id}")
            group.user_set.add(person.user)


            return Response({'success': f"{person} agora pode visualizar a quest '{quest.name}'."})

        except QuestViewerInviteToken.DoesNotExist:
            return Response({'error': 'Token inválido'}, status=404)  
        
#Lists all the cases associated with a quest
class QuestCasesView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, quest_id):
        try:
            quest = Quest.objects.get(id=quest_id)
        except Quest.DoesNotExist:
            return Response({'error': 'Quest not found'}, status=404)

        # Verifica se o usuário pode ver essa quest
        if not user_can_view_quest(request.user, quest):
            return Response({'error': 'You do not have permission to view this quest'}, status=403)

        # Lista os cases associados à quest
        cases = quest.quest_cases.all()
        serializer = CaseSerializer(cases, many=True)
        return Response(serializer.data)
    
# Adds a case to a quest
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
    

# Remove a case from a quest
class RemoveCaseToQuestView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, quest_id, case_id):
        try:
            quest = Quest.objects.get(id=quest_id)
        except Quest.DoesNotExist:
            return Response({'error': 'Quest not found'}, status=404)

        if not user_can_edit_quest(request.user, quest):
            return Response({'error': 'You do not have permission to remove cases from this quest'}, status=403)

        try:
            case = Case.objects.get(id=case_id)
        except Case.DoesNotExist:
            return Response({'error': 'Case not found'}, status=404)

        QuestCase.objects.filter(quest=quest, case=case).delete()
        return Response({'success': f'Case {case.name} removed from quest {quest.name}'}, status=200)



#Create a Quest Acess Token 
class CreateQuestAccessTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        quest_id = request.data.get('quest_id')
        variant = request.data.get('variant')
        expires_in_days = request.data.get('expires_in_days', 7)

        try:
            quest = Quest.objects.get(id=quest_id)
        except Quest.DoesNotExist:
            return Response({'error': 'Quest not found'}, status=404)

        person = request.user.person

        # only quest owner, authors, or institution owner can create access tokens
        if person != quest.owner and person not in quest.authors.all() and person != quest.institution.owner:
            return Response({'error': 'Permission denied'}, status=403)

        expires_at = timezone.now() + timedelta(days=int(expires_in_days))

        role = request.data.get('role')  # ex: 'guest' ou 'other'
        group = request.data.get('group')  # ex: 'viewer', 'author', 'editor'

        if role not in dict(QuestAccessToken._meta.get_field('role').choices).keys():
            return Response({'error': 'Invalid role'}, status=400)

        if group not in dict(QuestAccessToken._meta.get_field('group').choices).keys():
            return Response({'error': 'Invalid group'}, status=400)
        
        
        token = QuestAccessToken.objects.create(
            quest=quest,
            role=role,
            group=group,
            expires_at=expires_at,
            max_uses=request.data.get('max_uses')
        )

        link = f"{settings.CLIENT_URL}/invite/quest/{token.token}/"

        return Response({
            'token': str(token.token),
            'variant': token.variant,
            'expires_at': expires_at,
            'link': link
        }, status=201)

#Use a Quest Acess Token to access a quest

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