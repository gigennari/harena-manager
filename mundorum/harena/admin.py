from django.contrib import admin

from .models import Person, Institution, InstitutionDomain

admin.site.register(Person)


class InstitutionDomainInline(admin.TabularInline):
    model = InstitutionDomain
    extra = 1

class InstitutionAdmin(admin.ModelAdmin):
    list_display = ('name',)
    inlines = [InstitutionDomainInline]

admin.site.register(Institution, InstitutionAdmin)