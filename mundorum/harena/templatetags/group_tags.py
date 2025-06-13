from django import template
from django.contrib.auth.models import Group

register = template.Library()

@register.simple_tag
def group_id_by_name(name):
    try:
        group = Group.objects.get(name=name)
        
        return group.id
    except Group.DoesNotExist:
        return ""
