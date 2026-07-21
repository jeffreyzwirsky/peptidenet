import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "__first__"),
        ("comms", "0001_initial"),
    ]

    operations = [
        # --- Voicemail AI triage fields ---
        migrations.AddField(
            model_name="voicemail",
            name="transcript_source",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="voicemail",
            name="urgency",
            field=models.CharField(
                choices=[("low", "Low"), ("normal", "Normal"), ("high", "High"), ("urgent", "Urgent")],
                default="normal", max_length=8),
        ),
        migrations.AddField(
            model_name="voicemail",
            name="tier",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="voicemail",
            name="tier_confidence",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="voicemail",
            name="tier_rationale",
            field=models.CharField(blank=True, default="", max_length=300),
        ),
        migrations.AddField(
            model_name="voicemail",
            name="handled",
            field=models.BooleanField(default=False),
        ),
        # --- Compliance models ---
        migrations.CreateModel(
            name="SmsConsent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("e164", models.CharField(db_index=True, max_length=20)),
                ("event_type", models.CharField(choices=[("opt_in", "Opt in"), ("opt_out", "Opt out"), ("resubscribe", "Re-subscribe"), ("admin_suppress", "Admin suppress")], max_length=16)),
                ("category", models.CharField(choices=[("transactional", "Transactional"), ("marketing", "Marketing")], default="marketing", max_length=14)),
                ("source", models.CharField(choices=[("keyword", "SMS keyword"), ("contact_form", "Contact form"), ("checkout", "Checkout"), ("account", "Account settings"), ("admin", "Admin override"), ("import", "Import")], default="keyword", max_length=14)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, default="", max_length=300)),
                ("note", models.CharField(blank=True, default="", max_length=300)),
                ("message_sid", models.CharField(blank=True, default="", max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("site", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sms_consents", to="stores.site")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="SmsKeywordEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("e164", models.CharField(db_index=True, max_length=20)),
                ("keyword", models.CharField(max_length=20)),
                ("raw_body", models.CharField(blank=True, default="", max_length=300)),
                ("receiving_number", models.CharField(blank=True, default="", max_length=20)),
                ("message_sid", models.CharField(blank=True, default="", max_length=64)),
                ("reply_sent", models.BooleanField(default=False)),
                ("reply_text", models.CharField(blank=True, default="", max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("site", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sms_keyword_events", to="stores.site")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ComplianceConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("business_name", models.CharField(default="325 BioLabs", max_length=120)),
                ("stop_reply", models.CharField(default="You're unsubscribed and won't get further messages. Reply START to opt back in.", max_length=300)),
                ("help_reply", models.CharField(default="SmashFat BioLabs support. Msg&data rates may apply. Reply STOP to opt out.", max_length=300)),
                ("start_reply", models.CharField(default="You're re-subscribed. Reply STOP to opt out at any time.", max_length=300)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="TwilioVerificationTracker",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("toll_free", "Toll-free verification"), ("a2p_10dlc", "A2P 10DLC")], default="toll_free", max_length=12)),
                ("number", models.CharField(blank=True, default="", max_length=20)),
                ("status", models.CharField(choices=[("not_started", "Not started"), ("pending", "Pending"), ("submitted", "Submitted"), ("in_review", "In review"), ("approved", "Approved"), ("rejected", "Rejected")], default="not_started", max_length=12)),
                ("notes", models.CharField(blank=True, default="", max_length=300)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["kind"]},
        ),
    ]
