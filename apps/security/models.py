from django.db import models


class SecurityEvent(models.Model):
    """Audit trail of suspicious activity — honeypot trips, rate-limit blocks,
    bad webhook signatures, failed logins, bot-trap hits. Feeds the control-panel
    Security view (and could feed fail2ban). Mirrors the SMASH honeypot/audit idea."""

    KIND = [
        ("honeypot", "Honeypot trip"),
        ("ratelimit", "Rate limit hit"),
        ("bot_trap", "Bot trap URL"),
        ("bad_signature", "Bad webhook signature"),
        ("login_failed", "Failed admin login"),
        ("blocked", "Request blocked"),
    ]
    kind = models.CharField(max_length=16, choices=KIND)
    ip = models.GenericIPAddressField(null=True, blank=True)
    path = models.CharField(max_length=300, blank=True)
    detail = models.CharField(max_length=300, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    # Two-letter ISO code from Cloudflare's CF-IPCountry header. This column has
    # existed in the production database (NOT NULL varchar(2)) since ~2026-08-11
    # but was never in the model, so every SecurityEvent insert raised
    # IntegrityError — and log_event swallowed it. The entire security audit
    # trail was dead for three days and nothing said so.
    country = models.CharField(max_length=2, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["kind", "created_at"]), models.Index(fields=["ip"])]

    def __str__(self):
        return f"{self.get_kind_display()} {self.ip or ''} {self.path}"
