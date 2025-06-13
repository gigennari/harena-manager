from rest_framework import serializers
from .models import Quest

class QuestSerializer(serializers.ModelSerializer):
    institution_name = serializers.CharField(source='institution.name', read_only=True)
    owner_name = serializers.CharField(source='owner.user.get_full_name', read_only=True)

    class Meta:
        model = Quest
        fields = [
            'id',
            'name',
            'institution',         # id da instituição
            'institution_name',    # nome da instituição
            'owner',               # id do dono
            'owner_name',          # nome do dono
            'visible_to_institution',
            'created_at',
            # 'cases' ← deixamos pra incluir depois
        ]