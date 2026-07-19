from django.db import models


class Lead(models.Model):
    """Contact-form / feedback capture, centralized across every site —
    the same idea as the lead system's central lead engine."""

    KIND = [("contact", "Contact"), ("feedback", "Feedback"), ("request", "Product request")]

    site = models.ForeignKey("stores.Site", on_delete=models.PROTECT, related_name="leads")
    kind = models.CharField(max_length=12, choices=KIND, default="contact")
    name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    message = models.TextField(blank=True)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} — {self.email or self.name} ({self.site.domain})"
