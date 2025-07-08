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
    CreateQuestView,
    CreateCaseView,
    InviteProfessorView,
    UserCaseListView,
    QuestDetailView,
    EditableQuestListView,
    CaseDetailView,
    QuestAccessTokenListView,
)

urlpatterns = [
    # Authentication
    path('auth/google/', GoogleAuthView.as_view(), name='google-auth'),
    path('user/', UserView.as_view(), name='user'),

    # Professor invite token management
    path('api/invite/professor/', InviteProfessorView.as_view(), name='invite-professor'),

    # Quest access via token
    path('api/quest-access-token/', CreateQuestAccessTokenView.as_view(), name='create-quest-token'),
    path('api/use-quest-token/', UseQuestAccessTokenView.as_view(), name='use-quest-token'),

    # Quest management
    path('api/quests/<uuid:quest_id>/', QuestDetailView.as_view(), name='quest-detail'), # Get single quest details
    path('api/quests/create/', CreateQuestView.as_view(), name='create-quest'), #Ceating a quest
    path('api/quests/', QuestListView.as_view(), name='quest-list'), # List all quests a user can access
    path('api/quests/<uuid:quest_id>/cases/', QuestCasesView.as_view(), name='quest-cases'), # List cases in a quest
    path('api/quests/<uuid:quest_id>/cases/add/', AddCaseToQuestView.as_view(), name='add-case-to-quest'), # Add a case to a quest
    path('api/quests/<uuid:quest_id>/cases/<uuid:case_id>/remove/', RemoveCaseFromQuestView.as_view(), name='remove-case-from-quest'), # Remove a case from a quest
    path('api/quests/editable/', EditableQuestListView.as_view(), name='editable-quest-list'), # Get quests a user can edit
    path('api/quests/<uuid:quest_id>/access-tokens/', QuestAccessTokenListView.as_view(), name='quest-access-token-list'),


    #Case management
    path('api/cases/create/', CreateCaseView.as_view(), name='create-case'),
    path('api/cases/mycases/', UserCaseListView.as_view(), name='my-cases'),
    path('api/cases/<uuid:pk>/', CaseDetailView.as_view(), name='case-detail'), 
]
