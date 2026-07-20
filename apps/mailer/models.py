from django.db import models


class EmailLog(models.Model):
    """Every email the platform attempts — sent, stubbed (not live), or failed.
    Mirrors the comms Message/Call ledger so the portal can show email history."""

    KIND = [
        ("order", "Order confirmation"),
        ("lead", "Contact / lead alert"),
        ("voicemail", "Voicemail alert"),
        ("sms", "SMS alert"),
        ("invite", "Staff invite / reset"),
        ("customer", "Customer message"),
        ("other", "Other"),
    ]
    STATUS = [
        ("stub", "Stub (email not live)"),
        ("sent", "Sent"),
        ("failed", "Failed"),
    ]

    kind = models.CharField(max_length=12, choices=KIND, default="other")
    status = models.CharField(max_length=8, choices=STATUS, default="stub")
    to_email = models.CharField(max_length=254)
    from_email = models.CharField(max_length=254, blank=True)
    subject = models.CharField(max_length=255)
    site = models.ForeignKey(
        "stores.Site", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="emails",
    )
    provider_id = models.CharField(max_length=140, blank=True)  # Mailgun message id
    error = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.status}] {self.subject} → {self.to_email}"
