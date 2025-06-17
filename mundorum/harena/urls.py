from django.urls import path
from .views import GoogleAuthView, UserView, UseQuestViewerTokenView, QuestCasesView, AddCaseToQuestView, RemoveCaseFromQuestView

urlpatterns = [
    path('auth/google/', GoogleAuthView.as_view(), name='google-auth'),
    path('user/', UserView.as_view(), name='user'),
    path('api/use-quest-token/', UseQuestViewerTokenView.as_view(), name='use-quest-token'),
    path('api/quests/<uuid:quest_id>/cases/', QuestCasesView.as_view(), name='quest-cases'),
    path('api/quests/<uuid:quest_id>/cases/add/', AddCaseToQuestView.as_view(), name='add-case-to-quest'),
    path('api/quests/<uuid:quest_id>/cases/<uuid:case_id>/remove/', RemoveCaseFromQuestView.as_view(), name='remove-case-from-quest'),
]
