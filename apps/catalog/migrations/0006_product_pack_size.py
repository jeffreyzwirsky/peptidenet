from django.db import migrations, models


def supplies_sell_singly(apps, schema_editor):
    """Consumables are not vials and must not inherit the 10-vial pack.

    The AddField default of 10 is right for every compound but wrong for the
    Supplies category — bacteriostatic water is a bottle, and shipping someone
    ten of them because a default leaked across categories is the kind of error
    that only surfaces after the money has moved.
    """
    Product = apps.get_model("catalog", "Product")
    Product.objects.filter(category__name__iexact="Supplies").update(pack_size=1)


def restore_pack_size(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    Product.objects.filter(category__name__iexact="Supplies").update(pack_size=10)


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0005_product_gallery_product_image_product_image_alt_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="pack_size",
            field=models.PositiveIntegerField(
                default=10,
                help_text="Vials per sellable unit. Compounds ship in packs of 10 "
                          "and cannot be split. Set 1 for supplies (bacteriostatic "
                          "water, syringes) so they can still be bought singly.",
            ),
        ),
        migrations.RunPython(supplies_sell_singly, restore_pack_size),
    ]
