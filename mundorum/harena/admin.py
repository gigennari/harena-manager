from django.contrib import admin
from datetime import timedelta
from django.utils import timezone
from django.urls import path, reverse
from django.shortcuts import redirect
from django.contrib import messages
from .views import send_invite_email
from django.conf import settings
from .models import Person, Institution, InstitutionDomain, ProfessorInviteToken, Quest, QuestViewerInviteToken, QuestCase, Case, QuestAccessToken
from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin as DefaultGroupAdmin
from django import forms

admin.site.register(Person)


class InstitutionDomainInline(admin.TabularInline):
    model = InstitutionDomain
    extra = 1

@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ('name', 'active', 'owner')
    inlines = [InstitutionDomainInline]

    change_form_template = "admin/harena/institution/change_form.html"

    readonly_fields = ('active_updated_at',)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<uuid:institution_id>/create-invite-token/',
                self.admin_site.admin_view(self.redirect_to_invite_token),
                name='create-invite-token',
            ),
        ]
        return custom_urls + urls

    def redirect_to_invite_token(self, request, institution_id):
        return redirect(
            reverse('admin:harena_professorinvitetoken_add') + f'?institution={institution_id}'
        )
    

@admin.register(ProfessorInviteToken)
class ProfessorInviteTokenAdmin(admin.ModelAdmin):


    list_display = ('token', 'institution', 'email', 'expires_at', 'created_at', 'is_valid', 'is_used')
    list_filter = ('institution',)
    search_fields = ('token', 'email')

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        institution_id = request.GET.get('institution')
        if institution_id:
            initial['institution'] = institution_id
        return initial

    def save_model(self, request, obj, form, change):
        is_new = not change
        super().save_model(request, obj, form, change)

        if is_new:
            send_invite_email(obj)
            self.message_user(
                request,
                f"Invitation email sent to {obj.email}.",
                messages.SUCCESS
            )

@admin.action(description='Gerar token de convite para professores')
def generate_professor_invite_token(modeladmin, request, queryset):
    for institution in queryset:
        token = ProfessorInviteToken.objects.create(
            institution=institution,
            expires_at=timezone.now() + timedelta(days=7)
        )
        modeladmin.message_user(
            request,
            f"Token gerado para {institution.name}: {token.token}"
        )



@admin.register(Quest)
class QuestAdmin(admin.ModelAdmin):
    list_display = ('name', 'institution', 'owner')
    change_form_template = "admin/harena/quest/change_form.html"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('institution', 'owner')


class QuestCaseInline(admin.TabularInline):
    model = QuestCase
    extra = 1


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'case_owner', 'created_at', 'complexity', 'specialty', 
                    'content', 'answer', 'possible_answers', 'quest_count')
    list_filter = ('complexity', 'specialty', 'case_owner')
    search_fields = ('name', 'description', 'content', 'answer')

    def quest_count(self, obj):
        return obj.quest_cases.count()

    quest_count.short_description = "Number of Quests"
    
    inlines = [QuestCaseInline]

@admin.register(QuestAccessToken)
class QuestAccessTokenAdmin(admin.ModelAdmin):
    list_display = ('token', 'quest', 'role', 'group', 'expires_at', 'max_uses', 'created_at', 'is_valid_display', 'used_count')
    list_filter = ('role', 'group', 'quest')
    search_fields = ('token',)
    readonly_fields = ('created_at',)

    def used_count(self, obj):
        return obj.used_by.count()
    
    used_count.short_description = 'Used by (count)'

    def used_count(self, obj):
        return obj.used_by.count()
    used_count.short_description = 'Used by (count)'

    def is_valid_display(self, obj):
        return obj.is_valid()
    
    is_valid_display.boolean = True
    is_valid_display.short_description = 'Is Valid?'


    def save_model(self, request, obj, form, change):
        if not obj.expires_at:
            obj.expires_at = timezone.now() + timedelta(days=30)
        super().save_model(request, obj, form, change)
    
        link = f"{settings.CLIENT_URL}/invite/quest/{obj.token}"

        self.message_user(
                request,
                f"✅ Access token created successfully! Link: {link}",
                level=messages.SUCCESS
            )

class SafeGroupAdminForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name']  # remove 'permissions'

class GroupAdminWithMembers(DefaultGroupAdmin):
    form = SafeGroupAdminForm
    list_display = ('name', 'user_count', 'list_members')
    readonly_fields = ('list_members',)
    search_fields = ('name',)

    def user_count(self, obj):
        return obj.user_set.count()
    user_count.short_description = 'Number of Members'

    def list_members(self, obj):
        users = obj.user_set.all()
        return ", ".join([u.username for u in users]) if users else "No members"
    list_members.short_description = 'Members'

# Substitui o Group admin padrão
admin.site.unregister(Group)
admin.site.register(Group, GroupAdminWithMembers)