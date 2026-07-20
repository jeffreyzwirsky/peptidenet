from django.contrib import admin

from .models import Category, Product, Review


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "color", "order")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "unit_cost", "price", "margin", "stock_qty", "stock_state", "is_active")
    list_filter = ("category", "track_inventory", "is_new", "is_active")
    list_editable = ("unit_cost", "price", "stock_qty", "is_active")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("author", "product", "rating", "location", "is_verified", "is_published", "created_at")
    list_filter = ("rating", "is_verified", "is_published")
    list_editable = ("is_published",)
    search_fields = ("author", "body")
