from django.contrib import admin

from .models import PurchaseOrder, PurchaseOrderItem, Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "preferred_channel", "lead_time_window",
                    "currency", "is_default", "is_active")
    list_filter = ("is_active", "is_default", "preferred_channel")
    search_fields = ("name", "contact_name", "email", "whatsapp")
    prepopulated_fields = {"slug": ("name",)}


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 0


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("number", "order", "supplier", "status", "sent_at",
                    "tracking_number")
    list_filter = ("status", "supplier", "channel")
    search_fields = ("number", "order__number", "tracking_number",
                     "supplier_reference")
    inlines = [PurchaseOrderItemInline]
    readonly_fields = ("number", "created_at")
