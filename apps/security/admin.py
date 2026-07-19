from django.contrib import admin

from .models import SecurityEvent


@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kind", "ip", "path", "detail")
    list_filter = ("kind",)
    search_fields = ("ip", "path", "detail", "user_agent")
    readonly_fields = [f.name for f in SecurityEvent._meta.fields]
