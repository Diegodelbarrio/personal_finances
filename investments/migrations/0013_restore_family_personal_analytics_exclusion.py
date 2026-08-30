from django.db import migrations


def exclude_family_from_personal_analytics(apps, schema_editor):
    asset_model = apps.get_model("investments", "Asset")
    asset_model.objects.filter(name__icontains="family").update(
        exclude_from_totals=True
    )


def include_family_in_personal_analytics(apps, schema_editor):
    asset_model = apps.get_model("investments", "Asset")
    asset_model.objects.filter(name__icontains="family").update(
        exclude_from_totals=False
    )


class Migration(migrations.Migration):
    dependencies = [
        ("investments", "0012_include_family_assets_in_totals"),
    ]

    operations = [
        migrations.RunPython(
            exclude_family_from_personal_analytics,
            include_family_in_personal_analytics,
        ),
    ]
