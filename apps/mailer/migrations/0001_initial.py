import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("stores", "__first__"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("order", "Order confirmation"), ("lead", "Contact / lead alert"), ("voicemail", "Voicemail alert"), ("sms", "SMS alert"), ("invite", "Staff invite / reset"), ("customer", "Customer message"), ("other", "Other")], default="other", max_length=12)),
                ("status", models.CharField(choices=[("stub", "Stub (email not live)"), ("sent", "Sent"), ("failed", "Failed")], default="stub", max_length=8)),
                ("to_email", models.CharField(max_length=254)),
                ("from_email", models.CharField(blank=True, max_length=254)),
                ("subject", models.CharField(max_length=255)),
                ("provider_id", models.CharField(blank=True, max_length=140)),
                ("error", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("site", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="emails", to="stores.site")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
