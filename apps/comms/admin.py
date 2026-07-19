from django.contrib import admin

from .models import Call, Contact, IvrOption, Message, OptOut, PhoneNumber, Voicemail


class IvrOptionInline(admin.TabularInline):
    model = IvrOption
    extra = 0


@admin.register(PhoneNumber)
class PhoneNumberAdmin(admin.ModelAdmin):
    list_display = ("e164", "label", "site", "region", "sms_enabled", "voice_enabled", "ivr_enabled", "is_active")
    list_filter = ("sms_enabled", "voice_enabled", "ivr_enabled", "is_active")
    inlines = [IvrOptionInline]


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("display_phone", "name", "email", "site", "marketing_opted_out")
    search_fields = ("e164", "name", "email")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "direction", "status", "category", "from_number", "to_number", "site")
    list_filter = ("direction", "status", "category", "site")
    search_fields = ("from_number", "to_number", "body")


@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    list_display = ("created_at", "direction", "status", "from_number", "to_number", "duration_sec", "site")
    list_filter = ("direction", "site")


@admin.register(Voicemail)
class VoicemailAdmin(admin.ModelAdmin):
    list_display = ("created_at", "from_number", "category", "duration_sec", "listened", "site")
    list_filter = ("category", "listened", "site")


@admin.register(OptOut)
class OptOutAdmin(admin.ModelAdmin):
    list_display = ("created_at", "e164", "action", "keyword", "site")
    list_filter = ("action",)
    search_fields = ("e164",)
