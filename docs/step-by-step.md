# Django Server
## Step-by-Step Construction

## Virtual Environment

This is a step-by-step presentation to understand how this server setup was produced.

### Creating a Virtual Environment for Django

~~~
python3 -m venv .venv
~~~

### Running a Virtual Environment for Django

~~~
source .venv/bin/activate
~~~

## Django Setup

~~~
pip install -r requirements.txt
~~~

## Creating a Django Project (Mundorum)

~~~
django-admin startproject mundorum

cd mundorum
~~~

## Creating an Harena inside Mundorum

~~~
python3 manage.py startapp harena
~~~

## settings.py

Adding in `harena/settings.py`:

Load environment variables and set constants. The field `SECRET_KEY` produced by Django is transferred to the .env file (`DJANGO_SECRET_KEY` field) and its value is replaced by `os.getenv('DJANGO_SECRET_KEY')`:

~~~python
import os
from dotenv import load_dotenv

# ...

# Load environment variables from .env file
load_dotenv()

# The key produced by Django here was transferred to the .env file.
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')

# Google OAuth settings
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')

CLIENT_URL = os.getenv('CLIENT_URL')
SERVER_URL = os.getenv('SERVER_URL')

...
~~~

### Adding Apps

Adding the Harena app configuration, REST, and CORS support:

~~~python
INSTALLED_APPS = [
    'harena.apps.HarenaConfig',
    ...
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders'
]
~~~

### Connecting the PostgreSQL DBMS

Replace the default configuration to define the PostgreSQL DBMS:

~~~python
DATABASES = {
    'default': {
        'ENGINE': os.getenv('DB_ENGINE'),
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT')
    }
}
~~~

### Authentication Policy

Add the following default authentication policies:

~~~python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ]
}
~~~

### CORS Support

Add the following CORS directives in the Middleware:

~~~python
MIDDLEWARE = [
    ...
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware'
]

...

# Allow requests from your React app
CORS_ALLOWED_ORIGINS = [
    CLIENT_URL
]

# If you want to allow credentials (cookies, etc.)
CORS_ALLOW_CREDENTIALS = True
~~~

## model.py

Adding `harena/models.py`:

~~~python
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Person(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='person',
        primary_key=True)
    google_id = models.CharField(max_length=100, blank=True, null=True)
    profile_picture = models.URLField(max_length=255, blank=True, null=True)
    birth = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.user.username

# Automatically create or update Person when User is created/updated
@receiver(post_save, sender=User)
def create_or_update_person(sender, instance, created, **kwargs):
    if created:
        Person.objects.create(user=instance)
    else:
        instance.person.save()
~~~

## api.py

Create an API specification for Harena (`harena/api.py`). The person serializer considers the authentication approach TokenAuthentication/IsAuthenticated (`harena/api.py`):

~~~python
from rest_framework import routers, serializers, viewsets
from django.contrib.auth.models import User
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from .models import Person

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

class PersonSerializer(serializers.HyperlinkedModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Person
        fields = ['user_id', 'username', 'first_name', 'last_name', 'email', 'birth', 'google_id', 'profile_picture']

class PersonViewSet(viewsets.ModelViewSet):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    queryset = Person.objects.all()
    serializer_class = PersonSerializer

router = routers.DefaultRouter()
router.register(r'person', PersonViewSet, basename='harena')
~~~

Create the complete API specification file (`mundorum/api.py`), importing the Harena API and adding routes to access administrative data - users:

~~~python
from rest_framework import routers, serializers, viewsets

from django.contrib.auth.models import User
from harena.api import router as harena_router

# Serializers define the API representation.
class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ['url', 'username', 'email', 'is_staff']

# ViewSets define the view behavior.
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.register(r'users', UserViewSet)
router.registry.extend(harena_router.registry)
~~~

## views.py

Adding the `harena/views.py` that also handles authentication:

~~~python
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
from .models import Person

class GoogleAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        google_token = request.data.get('token')

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
                    'picture': person.profile_picture
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
~~~

## urls.py - Endpoints

Add the local route (`harena/urls.py`) to include authentication:

~~~python
from django.urls import path
from .views import GoogleAuthView, UserView

urlpatterns = [
    path('auth/google/', GoogleAuthView.as_view(), name='google-auth'),
    path('user/', UserView.as_view(), name='user'),
]
~~~

Expand the `mundorum/urls.py` file to consider REST APIs and authorization:

~~~python
from django.contrib import admin
from django.urls import include, path
from . import api

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path('', include(api.router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('', include('harena.urls')),
    path('admin/', admin.site.urls),
]
~~~

## Adding in the admin panel

File `harena/admin.py`:

~~~python
from django.contrib import admin

from .models import Person

admin.site.register(Person)
~~~

Inside the root `/mundorum`:

## Building a Migration Code

~~~
python3 manage.py makemigrations harena
~~~

## Showing the SQL that creates the tables

~~~
python3 manage.py sqlmigrate harena 0001
~~~

Expected output:

~~~sql
BEGIN;
--
-- Create model Person
--
CREATE TABLE "harena_person" ("user_id" integer NOT NULL PRIMARY KEY, "google_id" varchar(100) NULL, "profile_picture" varchar(255) NULL, "birth" date NULL);
ALTER TABLE "harena_person" ADD CONSTRAINT "harena_person_user_id_c2fd8ab4_fk_auth_user_id" FOREIGN KEY ("user_id") REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED;
COMMIT;
~~~

## Applying Migration

~~~
python3 manage.py migrate
~~~

## Adding an admin user

~~~
python3 manage.py createsuperuser
~~~

### Updating `requirements.txt`

~~~
pip freeze -l > requirements.txt
~~~

## Leaving the Virtual Environment

~~~
deactivate
~~~
