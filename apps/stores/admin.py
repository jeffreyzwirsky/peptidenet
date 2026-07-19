from django.contrib import admin

from .models import Site


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("domain", "brand_name", "theme", "promo_code", "is_active")
    list_filter = ("theme", "is_active")
    search_fields = ("domain", "brand_name")
    list_editable = ("theme", "is_active")
