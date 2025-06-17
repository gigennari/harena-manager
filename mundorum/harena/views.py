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
from .models import Person, InstitutionDomain, ProfessorInviteToken, Quest, QuestViewerInviteToken, Case, QuestCase
from django.db.models import Q
from django.contrib.auth.models import Group
from .serializers import QuestSerializer,CaseSerializer

class GoogleAuthView(APIView):
    permission_classes = [AllowAny]

    @staticmethod
    def get_institution_from_email(email):
        """
        Extracts the institution from the email domain.
        Assumes that the institution is determined by the email domain.
        """
        domain = email.split('@')[-1]
        try:
            institution_domain = InstitutionDomain.objects.get(name=domain)
            return institution_domain.institution
        except InstitutionDomain.DoesNotExist:
            return None
            
    def post(self, request):
        google_token = request.data.get('token')
        invite_token = request.data.get('invite_token', None)

        # Check if 

        if not google_token:
            return Response({'error': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Verify the token with Google
            idinfo = id_token.verify_oauth2_token(
                google_token, 
                requests.Request(), 
                settings.GOOGLE_CLIENT_ID
            )

            # Get user information from the token
            google_id = idinfo['sub']
            email = idinfo['email']
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')
            profile_picture = idinfo.get('picture', '')

            # Check if user exists, create if not
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                # Create a new user
                username = email.split('@')[0]
                # Make sure username is unique
                if User.objects.filter(username=username).exists():
                    username = f"{username}_{google_id[:8]}"

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name
                )

            # Update or create person
            person, created = Person.objects.get_or_create(user=user)
            person.google_id = google_id
            person.profile_picture = profile_picture
            person.institution = self.get_institution_from_email(email)

            #Determine role and institution based on invite token if provided
            if invite_token:
                try:
                    token = ProfessorInviteToken.objects.get(token=invite_token)

                    if not token.is_valid():
                        return Response({'error': 'Token expirado'}, status=400)


                    person.institution = token.institution
                    person.role = 'professor'
                    person.save()

                    token.used_by.add(person)
                    token.save()

                except ProfessorInviteToken.DoesNotExist:
                    return Response({'error': 'Token de convite inválido'}, status=400)
            else:
                person.institution = self.get_institution_from_email(email)
                person.role = 'student'
                person.save()

            person.save()

            # Create or get authentication token
            token, created = Token.objects.get_or_create(user=user)

            # Return user data and token
            return Response({
                'token': token.key,
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'name': f"{user.first_name} {user.last_name}".strip(),
                    'picture': person.profile_picture,
                    'institution': user.person.institution.name if user.person.institution else None
                }
            })

        except ValueError:
            # Invalid token
            return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
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
        f"viewers_{quest.id}" in group_names or
        f"authors_{quest.id}" in group_names
    )

# Helper function to check if a user can edit a quest
def user_can_edit_quest(user, quest):
    person = user.person
    group_names = user.groups.values_list('name', flat=True)
    return (
        quest.owner == person or
        f"authors_{quest.id}" in group_names
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

        if not user_can_edit_quest(request.user, quest):
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
class RemoveCaseFromQuestView(APIView):
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


