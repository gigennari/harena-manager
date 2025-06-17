from rest_framework import serializers
from .models import Quest, QuestCase, Case


class CaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Case
        fields = [
            'id', 'name', 'description', 'content', 'answer', 'answer_options',
            'created_at', 'case_owner'
        ]

class QuestSerializer(serializers.ModelSerializer):
    institution_name = serializers.CharField(source='institution.name', read_only=True)
    owner_name = serializers.CharField(source='owner.user.get_full_name', read_only=True)
    cases = serializers.SerializerMethodField()

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
            'created_at',
            'cases' 
        ]

    def get_cases(self, obj):
        return CaseSerializer(
            [qc.case for qc in obj.quest_cases.all()],
            many=True
        ).data
