from django.db import migrations


def include_family_assets(apps, schema_editor):
    asset_model = apps.get_model("investments", "Asset")
    asset_model.objects.filter(
        name__icontains="family",
        exclude_from_totals=True,
    ).update(exclude_from_totals=False)


def restore_legacy_family_exclusion(apps, schema_editor):
    asset_model = apps.get_model("investments", "Asset")
    asset_model.objects.filter(name__icontains="family").update(
        exclude_from_totals=True
    )


class Migration(migrations.Migration):
    dependencies = [
        ("investments", "0011_alter_assethistory_total_value_and_more"),
    ]

    operations = [
        migrations.RunPython(
            include_family_assets,
            restore_legacy_family_exclusion,
        ),
    ]
