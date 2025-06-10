from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Institution(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
    
#One institution can have multiple domains, but each domain belongs to one institution only.
class InstitutionDomain(models.Model):
    name = models.CharField(max_length=100, unique=True)
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='domains')

    def __str__(self):
        return self.name    

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

    def __str__(self):
        return self.user.username

# Automatically create or update Person when User is created/updated
@receiver(post_save, sender=User)
def create_or_update_person(sender, instance, created, **kwargs):
    if created:
        Person.objects.create(user=instance)
    else:
        instance.person.save()
