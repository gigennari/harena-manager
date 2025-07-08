from rest_framework import serializers
from .models import Quest, QuestCase, Case, Institution, Person, User, ProfessorInviteToken, QuestAccessToken
from django.contrib.auth.models import Group

   

class QuestSerializer(serializers.ModelSerializer):
    institution_name = serializers.CharField(source='institution.name', read_only=True)
    owner_name = serializers.CharField(source='owner.user.get_full_name', read_only=True)

    class Meta:
        model = Quest
        fields = [
            'id',
            'name',
            'institution',         # insitution id
            'institution_name',    
            'owner',               # owner id
            'owner_name',          
            'visible_to_institution',
            'created_at' 
        ]

class InstitutionSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Institution
        fields = ['id', 'name', 'owner']

        def get_owner(self, obj):
        # Return the user ID linked to the person who is the owner of the institution
            return obj.owner.user.id if obj.owner and obj.owner.user else None

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

class PersonSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    institution = InstitutionSerializer(read_only=True)

    class Meta:
        model = Person
        fields = [
            'user',
            'google_id',
            'profile_picture',
            'birth',
            'institution',
            'role',
        ]

class ProfessorInviteTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessorInviteToken
        fields = ['email', 'institution', 'token']
        read_only_fields = ['token']

class CaseSerializer(serializers.ModelSerializer):
    quests = serializers.SerializerMethodField()
    case_owner = PersonSerializer(read_only=True)

    class Meta:
        model = Case
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'case_owner']

    def get_quests(self, obj):
        quests = [qc.quest for qc in obj.quest_cases.all()]
        return QuestSerializer(quests, many=True).data
    
    def get_complexity_choices(self, obj):
        return Case.COMPLEXITY_CHOICES
    

class QuestAccessTokenSerializer(serializers.ModelSerializer):
    """
    Serializer for the QuestAccessToken model.
    Handles serialization and deserialization of Quest Access Tokens.
    """
    class Meta:
        model = QuestAccessToken
        fields = [
            'token',        # The UUID token itself
            'quest',        # The ID of the associated Quest
            'role',         # The role assigned by this token (guest, student, professor)
            'group',        # The group assigned by this token (viewer, author, editor)
            'max_uses',     # Maximum number of times this token can be used
            'expires_at',   # The date and time when this token expires
            'created_at',   # When the token was created (read-only)
            'used_by',      # Users who have used this token (read-only, M2M field)
            'used_by_count', # Custom field to count how many users have used this token
        ]
        read_only_fields = ['token', 'created_at', 'used_by', 'used_by_count'] # Token and created_at are auto-generated/managed by Django
                                                              # used_by is managed via the UseQuestAccessTokenView

        def get_used_by_count(self, obj):
            return obj.used_by.count()                                                      