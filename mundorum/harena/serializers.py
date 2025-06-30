from rest_framework import serializers
from .models import Quest, QuestCase, Case, Institution, Person, User, ProfessorInviteToken
from django.contrib.auth.models import Group


class CaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Case
        fields = [
            'id', 'name', 'description', 'content', 'answer', 'possible_answers',
            'created_at', 'case_owner', 'image', 'complexity', 'specialty'
        ]
        read_only_fields = ['id', 'created_at']

class QuestSerializer(serializers.ModelSerializer):
    institution_name = serializers.CharField(source='institution.name', read_only=True)
    owner_name = serializers.CharField(source='owner.user.get_full_name', read_only=True)
    #cases = serializers.SerializerMethodField()

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