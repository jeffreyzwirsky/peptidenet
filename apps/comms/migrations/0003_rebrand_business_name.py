"""Data migration: scrub the scrap-business legal name from the SMS-compliance
config. Any existing ComplianceConfig row that still carries the old
"SmashFat BioLabs (SmashScrap.ca LTD)" default (or any value mentioning
SmashScrap) is rebranded to the peptide entity so the portal + CASL disclosures
show no tie to the scrap business. Idempotent + safe to re-run."""
from django.db import migrations

NEW_NAME = "325 BioLabs"


def rebrand(apps, schema_editor):
    ComplianceConfig = apps.get_model("comms", "ComplianceConfig")
    for cfg in ComplianceConfig.objects.all():
        name = cfg.business_name or ""
        if "smashscrap" in name.lower() or name.strip() == "":
            cfg.business_name = NEW_NAME
            cfg.save(update_fields=["business_name"])


def noop(apps, schema_editor):
    # Non-reversible by design (we don't restore the scrap name).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("comms", "0002_compliance_and_triage"),
    ]

    operations = [
        migrations.RunPython(rebrand, noop),
    ]
