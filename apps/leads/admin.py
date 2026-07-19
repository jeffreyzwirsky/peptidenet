from django.contrib import admin

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kind", "name", "email", "rating", "site")
    list_filter = ("kind", "site")
    search_fields = ("name", "email", "message")
