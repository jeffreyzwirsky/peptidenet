"""AI phone intake: PhoneNumber.ai_intake (per-number toggle) and
Voicemail.subject (the AI-generated subject line from the caller's reason)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("comms", "0004_phonenumber_greeting_audio"),
    ]

    operations = [
        migrations.AddField(
            model_name="phonenumber",
            name="ai_intake",
            field=models.BooleanField(
                default=False,
                help_text="Turn-based AI intake: greet, answer basic catalogue "
                          "questions (guarded, research-use-only, no company/medical "
                          "info), build a voicemail subject line, then record."),
        ),
        migrations.AddField(
            model_name="voicemail",
            name="subject",
            field=models.CharField(
                blank=True, default="", max_length=200,
                help_text="AI-intake subject line (from the caller's stated reason)."),
        ),
    ]
