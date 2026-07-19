from django.db import models

from . import phone


class PhoneNumber(models.Model):
    """A Twilio number. Tied to a Site, or shared network-wide when site is null.
    Mirrors SMASH's per-tenant SALES numbers + region routing."""

    e164 = models.CharField(max_length=20, unique=True)
    label = models.CharField(max_length=80, blank=True)
    site = models.ForeignKey(
        "stores.Site", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="numbers", help_text="Leave blank for a shared network number.",
    )
    region = models.CharField(max_length=4, blank=True, help_text="MB/SK/AB/… (auto)")
    sms_enabled = models.BooleanField(default=True)
    voice_enabled = models.BooleanField(default=True)
    # Voice: greeting played before recording a voicemail; optional simple IVR.
    greeting = models.TextField(
        blank=True,
        default="Thanks for calling. Please leave a message after the tone and we'll get back to you.",
    )
    ivr_enabled = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        self.e164 = phone.normalize(self.e164)
        if not self.region:
            self.region = phone.region_of(self.e164)
        super().save(*args, **kwargs)

    @property
    def display_phone(self):
        return phone.display(self.e164)

    def __str__(self):
        return f"{phone.display(self.e164)} ({self.label or 'number'})"


class Contact(models.Model):
    """A customer/lead reachable by phone. Comms attach here + to the site."""

    e164 = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    site = models.ForeignKey(
        "stores.Site", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="contacts", help_text="Site where first seen.",
    )
    marketing_opted_out = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.e164 = phone.normalize(self.e164)
        super().save(*args, **kwargs)

    @property
    def display_phone(self):
        return phone.display(self.e164)

    def __str__(self):
        return self.name or self.display_phone


class Message(models.Model):
    """2-way SMS. direction + status mirror the SMASH TextMessage model."""

    DIRECTION = [("in", "Inbound"), ("out", "Outbound")]
    STATUS = [
        ("draft", "Draft"), ("queued", "Queued"), ("sent", "Sent"),
        ("delivered", "Delivered"), ("received", "Received"),
        ("failed", "Failed"), ("blocked", "Blocked (opted out)"),
    ]
    CATEGORY = [("transactional", "Transactional"), ("marketing", "Marketing")]

    direction = models.CharField(max_length=3, choices=DIRECTION)
    status = models.CharField(max_length=10, choices=STATUS, default="queued")
    category = models.CharField(max_length=14, choices=CATEGORY, default="transactional")
    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="messages")
    site = models.ForeignKey("stores.Site", null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="messages")
    from_number = models.CharField(max_length=20)
    to_number = models.CharField(max_length=20)
    body = models.TextField()
    twilio_sid = models.CharField(max_length=64, blank=True)
    error = models.CharField(max_length=200, blank=True)
    ai_generated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.direction}] {self.body[:40]}"


class Call(models.Model):
    """Inbound/outbound call log with transcription fields (OpenAI Whisper)."""

    DIRECTION = [("in", "Inbound"), ("out", "Outbound")]
    direction = models.CharField(max_length=3, choices=DIRECTION)
    status = models.CharField(max_length=20, default="completed")
    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="calls")
    site = models.ForeignKey("stores.Site", null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="calls")
    from_number = models.CharField(max_length=20)
    to_number = models.CharField(max_length=20)
    twilio_sid = models.CharField(max_length=64, blank=True)
    duration_sec = models.PositiveIntegerField(default=0)
    recording_url = models.URLField(blank=True)
    transcript = models.TextField(blank=True)
    transcript_source = models.CharField(max_length=20, blank=True)  # e.g. "whisper"
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_direction_display()} call {self.twilio_sid or ''}"


class Voicemail(models.Model):
    CATEGORY = [("sales", "Sales"), ("support", "Support"), ("general", "General")]

    call = models.ForeignKey(Call, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="voicemails")
    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="voicemails")
    site = models.ForeignKey("stores.Site", null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="voicemails")
    from_number = models.CharField(max_length=20)
    category = models.CharField(max_length=10, choices=CATEGORY, default="general")
    recording_url = models.URLField(blank=True)
    duration_sec = models.PositiveIntegerField(default=0)
    transcript = models.TextField(blank=True)
    listened = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Voicemail from {phone.display(self.from_number)}"


class OptOut(models.Model):
    """Append-only opt-out/consent log per number (STOP→out, START→in).
    Marketing sends are blocked to opted-out numbers; transactional flows."""

    ACTION = [("opt_out", "Opt out"), ("opt_in", "Opt in"), ("help", "Help")]
    e164 = models.CharField(max_length=20, db_index=True)
    action = models.CharField(max_length=8, choices=ACTION)
    keyword = models.CharField(max_length=20, blank=True)  # STOP/START/HELP/manual
    site = models.ForeignKey("stores.Site", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.e164 = phone.normalize(self.e164)
        super().save(*args, **kwargs)


class IvrOption(models.Model):
    """A DTMF key on a number's phone tree → voicemail category (kept simple)."""

    number = models.ForeignKey(PhoneNumber, on_delete=models.CASCADE, related_name="ivr_options")
    digit = models.CharField(max_length=1)
    label = models.CharField(max_length=60)
    voicemail_category = models.CharField(max_length=10, default="general")

    class Meta:
        ordering = ["digit"]
        unique_together = ("number", "digit")
