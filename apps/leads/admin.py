from django.contrib import admin

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("created_at", "status", "kind", "name", "email", "phone", "rating", "site")
    list_filter = ("status", "kind", "site")
    search_fields = ("name", "email", "phone", "message", "notes")
    readonly_fields = ("created_at", "reviewed_by", "reviewed_at")
