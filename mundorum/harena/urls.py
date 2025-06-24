from django.urls import path
from .views import (
    GoogleAuthView,
    UserView,
    QuestListView,
    QuestCasesView,
    AddCaseToQuestView,
    RemoveCaseFromQuestView,
    UseQuestAccessTokenView,
    CreateQuestAccessTokenView,
)

urlpatterns = [
    # Authentication
    path('auth/google/', GoogleAuthView.as_view(), name='google-auth'),
    path('user/', UserView.as_view(), name='user'),

    # Quest access via token
    path('api/quest-access-token/', CreateQuestAccessTokenView.as_view(), name='create-quest-token'),
    path('api/use-quest-token/', UseQuestAccessTokenView.as_view(), name='use-quest-token'),

    # Quest management
    path('api/quests/', QuestListView.as_view(), name='quest-list'),
    path('api/quests/<uuid:quest_id>/cases/', QuestCasesView.as_view(), name='quest-cases'),
    path('api/quests/<uuid:quest_id>/cases/add/', AddCaseToQuestView.as_view(), name='add-case-to-quest'),
    path('api/quests/<uuid:quest_id>/cases/<uuid:case_id>/remove/', RemoveCaseFromQuestView.as_view(), name='remove-case-from-quest'),
]
