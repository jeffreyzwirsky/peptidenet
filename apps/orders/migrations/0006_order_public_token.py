import secrets

import apps.orders.models
from django.db import migrations, models


def populate_tokens(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    for order in Order.objects.filter(public_token__isnull=True).iterator():
        order.public_token = secrets.token_urlsafe(24)
        order.save(update_fields=["public_token"])


class Migration(migrations.Migration):
    dependencies = [("orders", "0005_orderitem_pack_size")]

    operations = [
        migrations.AddField(
            model_name="order",
            name="public_token",
            field=models.CharField(editable=False, max_length=48, null=True, unique=True),
        ),
        migrations.RunPython(populate_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="order",
            name="public_token",
            field=models.CharField(default=apps.orders.models.new_order_public_token, editable=False, max_length=48, unique=True),
        ),
    ]
