from django.urls import path
from .views import GoogleAuthView, UserView, UseQuestViewerTokenView

urlpatterns = [
    path('auth/google/', GoogleAuthView.as_view(), name='google-auth'),
    path('user/', UserView.as_view(), name='user'),
    path('api/use-quest-token/', UseQuestViewerTokenView.as_view(), name='use-quest-token'),
]
