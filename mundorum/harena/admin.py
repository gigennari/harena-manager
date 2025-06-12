from django.contrib import admin
from datetime import timedelta
from django.utils import timezone
from django.urls import path
from django.shortcuts import redirect
from django.contrib import messages

from .models import Person, Institution, InstitutionDomain, ProfessorInviteToken

admin.site.register(Person)


class InstitutionDomainInline(admin.TabularInline):
    model = InstitutionDomain
    extra = 1

class InstitutionAdmin(admin.ModelAdmin):
    list_display = ('name',)
    inlines = [InstitutionDomainInline]

    # Custom action to generate invite token for selected institutions
    change_form_template = "admin/harena/institution/change_form.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:institution_id>/generate-token/',
                self.admin_site.admin_view(self.generate_invite_token_view),
                name='generate-invite-token',
            ),
        ]
        return custom_urls + urls
    def generate_invite_token_view(self, request, institution_id):
        from .models import ProfessorInviteToken
        from datetime import timedelta
        from django.utils import timezone

        institution = Institution.objects.get(pk=institution_id)
        token = ProfessorInviteToken.objects.create(
            institution=institution,
            expires_at=timezone.now() + timedelta(days=7)
        )

        messages.success(request, f"Token gerado para {institution.name}: {token.token}")
        return redirect(f'/admin/harena/institution/{institution_id}/change/')


@admin.register(ProfessorInviteToken)
class ProfessorInviteTokenAdmin(admin.ModelAdmin):

    def used_by_list_display(self, obj):
        return ", ".join(p.user.username for p in obj.used_by.all()) if obj.used_by.exists() else 'N/A'
    
    list_display = ('token', 'institution', 'expires_at', 'created_at', 'used_by_list_display', 'is_valid')
    list_filter = ('institution',)
    search_fields = ('token',)


admin.site.register(Institution, InstitutionAdmin)

@admin.action(description='Gerar token de convite para professores')
def generate_professor_invite_token(modeladmin, request, queryset):
    for institution in queryset:
        token = ProfessorInviteToken.objects.create(
            institution=institution,
            expires_at=timezone.now() + timedelta(days=7)
        )
        modeladmin.message_user(
            request,
            f"Token gerado para {institution.name}: {token.code}"
        )