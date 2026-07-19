from django.contrib import admin

from .models import BlogPost


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "site", "status", "compliance_status", "ai_generated",
                    "published_at", "created_at")
    list_filter = ("status", "compliance_status", "site", "ai_generated")
    search_fields = ("title", "body", "keyword")
    readonly_fields = ("compliance_notes",)
