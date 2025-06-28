#Mundorum Harena - Models for the Django application

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth.models import Group
import uuid
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from django.contrib.postgres.fields import JSONField
from django.db.models import JSONField

# User roles in the system
ROLE_CHOICES = [
        ('guest', 'Guest'), #Any email domain can register as a guest
        ('student', 'Student'), #Must use institution email domain
        ('professor', 'Professor'), #Must use institution email domain
    ]

# Group choices for Quest permissions
# These groups are created automatically when a Quest is created.   
GROUP_CHOICES = [
        ('viewer', 'Viewer'), # can view the Quest
        ('author', 'Author'), # can add cases to the Quest
        ('editor', 'Editor'), # can add, remove and reorder cases in the Quest
    ]

#Quest owners can deleted the Quest itself, but not the cases inside it.

#Only a case owner can edit or delete the case



class Institution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    active = models.BooleanField(default=True)  # flag to indicate if the institution is active or not
    active_updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.pk:  
            old = Institution.objects.get(pk=self.pk)
            if old.active != self.active:
                self.active_updated_at = timezone.now()
        else:
            self.active_updated_at = timezone.now()
        super().save(*args, **kwargs)


    def __str__(self):
        return self.name
    
#One institution can have multiple domains, but each domain belongs to one institution only.
class InstitutionDomain(models.Model):
    name = models.CharField(max_length=100, unique=True)
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='domains')

    def __str__(self):
        return self.name    


# Professor registration through expirable token 
class ProfessorInviteToken(models.Model):
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True) #cerate token automatically
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE)
    email= models.EmailField(max_length=255, blank=True, null=True)  # email of the invited professor
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    #users who used this token
    is_used = models.BooleanField(default=False)
    
    def is_valid(self):
        
        return timezone.now() < self.expires_at
    
    def __str__(self):
        return f"Token for {self.institution.name} - Expires at {self.expires_at.strftime('%d/%m/%Y %H:%M')}"
    
# A Person is a User with additional fields like Google ID, profile picture, birth date, institution, role.
class Person(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='person',
        primary_key=True)
    google_id = models.CharField(max_length=100, blank=True, null=True)
    profile_picture = models.URLField(max_length=255, blank=True, null=True)
    birth = models.DateField(blank=True, null=True)
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT, related_name='people', null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')


    def __str__(self):
        if self.role == 'professor':
            return f"{self.user.username} (Professor)"
        return self.user.username


# Automatically create or update Person when User is created/updated
@receiver(post_save, sender=User)
def create_or_update_person(sender, instance, created, **kwargs):
    if created:
        Person.objects.create(user=instance)
    else:
        instance.person.save()



# A Quest is a group of cases or challenge that can be assigned to users, associated with an institution.    
class Quest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    institution = models.ForeignKey('Institution', on_delete=models.CASCADE, related_name='quests')
    owner = models.ForeignKey('Person', on_delete=models.PROTECT, related_name='owned_quests')
    visible_to_institution = models.BooleanField(default=False)  # if True, all users in the institution can see this quest

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        # Automatically add the owner to the quest's group
        viewers_group, _ = Group.objects.get_or_create(name=f"viewers_{self.id}")
        authors_group, _ = Group.objects.get_or_create(name=f"authors_{self.id}")
        editors_group, _ = Group.objects.get_or_create(name=f"editors_{self.id}")

        self.owner.user.groups.add(viewers_group, authors_group, editors_group)

    def __str__(self):
        return f"{self.name} ({self.institution.name})" 

# Token for inviting users to view a Quest, with an expiration date
class QuestViewerInviteToken(models.Model):
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    quest = models.ForeignKey('Quest', on_delete=models.CASCADE, related_name='viewer_tokens')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_valid(self):
        return timezone.now() < self.expires_at

    def __str__(self):
        return f"Token for {self.quest.name} - Expires at {self.expires_at.strftime('%d/%m/%Y %H:%M')}"
    
  

class Case(models.Model):

    COMPLEXITY_CHOICES = [
        ('undergraduate', 'Undergraduate'), #still in college
        ('graduate', 'Graduate'), #finished college, but not yet a PhD
        ('postgraduate', 'Postgraduate'), #PhD or higher
    ]   


    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)  # title of the case
    description = models.TextField(blank=True, null=True)  # optional case description 
    content = models.TextField()  # full content of the case
    answer = models.CharField(max_length=255) #correct answer for the case
    possible_answers = JSONField(default=list, blank=True)  # list of possible answers for the case
    created_at = models.DateTimeField(auto_now_add=True)
    case_owner = models.ForeignKey('Person', on_delete=models.PROTECT, related_name='cases_owned')
    complexity = models.CharField(max_length=30, choices=COMPLEXITY_CHOICES, default='undergraduate')
    specialty = models.CharField(max_length=255, blank=True, null=True)
    image = models.ImageField(upload_to='case_images/', blank=True, null=True)  # optional image for the case

    def __str__(self):
        return self.name

    
class QuestCase(models.Model):


    quest = models.ForeignKey('Quest', on_delete=models.CASCADE, related_name='quest_cases')
    case = models.ForeignKey('Case', on_delete=models.CASCADE, related_name='quest_cases')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
        models.UniqueConstraint(
            fields=['quest', 'case'],
            name='unique_quest_case'
        )
        ]

    def __str__(self):
        return f"{self.case.name} in {self.quest.name}"
    

class QuestAccessToken(models.Model):

    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    quest = models.ForeignKey('Quest', on_delete=models.CASCADE, related_name='access_tokens')
    
    # The role of the user who can use this token. 
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='guest')
    # The quest group a user who uses this token will belong to -> control quest permisisons
    group = models.CharField(max_length=20, choices=GROUP_CHOICES, default='viewer')
    
    # Expiration
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    # Usage limits and tracking 
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    used_by = models.ManyToManyField('Person', blank=True)

    def is_valid(self):
        not_expired = timezone.now() < self.expires_at
        within_limit = (
            self.max_uses is None or
            self.used_by.count() < self.max_uses
        )
        return not_expired and within_limit
    def __str__(self):
        return f"{self.group.capitalize()} Token for Quest {self.quest.name} ({self.role})"