import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("security", "0002_securityevent_country"),
    ]

    operations = [
        migrations.CreateModel(
            name="RateLimitBucket",
            fields=[
                ("key", models.CharField(max_length=96, primary_key=True, serialize=False)),
                ("window_started_at", models.DateTimeField()),
                ("count", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="ConsoleMfaDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("secret", models.CharField(max_length=64)),
                ("confirmed", models.BooleanField(default=False)),
                ("last_counter", models.BigIntegerField(default=-1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="console_mfa_device", to="auth.user")),
            ],
        ),
    ]
