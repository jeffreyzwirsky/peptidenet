from django.db import models
from django.utils import timezone


class Lead(models.Model):
    """Contact-form / feedback capture, centralized across every site —
    the same idea as the lead system's central lead engine.

    A lead moves through a tiny review pipeline worked from /manage/leads/:
    it arrives ``new``, an operator marks it ``reviewed`` (looked at, nothing
    to do yet), ``replied`` (we answered by email), ``closed`` (done), or
    ``spam``. Spam stays stored — it trains the eye for what the honeypot
    misses — but is hidden from the default queue.
    """

    KIND = [("contact", "Contact"), ("feedback", "Feedback"), ("request", "Product request")]
    STATUS = [
        ("new", "New"),
        ("reviewed", "Reviewed"),
        ("replied", "Replied"),
        ("closed", "Closed"),
        ("spam", "Spam"),
    ]
    OPEN_STATUSES = ("new", "reviewed")  # the queue that still needs a human

    site = models.ForeignKey("stores.Site", on_delete=models.PROTECT, related_name="leads")
    kind = models.CharField(max_length=12, choices=KIND, default="contact")
    name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    message = models.TextField(blank=True)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # --- review workflow ---
    status = models.CharField(max_length=10, choices=STATUS, default="new", db_index=True)
    notes = models.TextField(blank=True, help_text="Internal notes — never shown to the customer.")
    reviewed_by = models.CharField(max_length=150, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} — {self.email or self.name} ({self.site.domain})"

    def set_status(self, status, by=""):
        """Move the lead and stamp who touched it. Raises on unknown status so
        a typo in a POST can't silently invent a state."""
        if status not in dict(self.STATUS):
            raise ValueError(f"Unknown lead status: {status!r}")
        self.status = status
        self.reviewed_by = (by or self.reviewed_by)[:150]
        self.reviewed_at = timezone.now()
        self.save(update_fields=["status", "reviewed_by", "reviewed_at"])
