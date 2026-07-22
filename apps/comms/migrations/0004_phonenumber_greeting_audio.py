"""Add PhoneNumber.greeting_audio — path to a pre-generated ElevenLabs greeting
mp3, played via TwiML <Play> instead of the Polly <Say> when present."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("comms", "0003_rebrand_business_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="phonenumber",
            name="greeting_audio",
            field=models.CharField(
                blank=True, default="", max_length=300,
                help_text="Path to a pre-generated ElevenLabs greeting mp3 (e.g. "
                          "/static/comms/greeting-1.mp3). Played instead of the Polly "
                          "<Say> when set; regenerate with `manage.py generate_greeting_audio`."),
        ),
    ]
