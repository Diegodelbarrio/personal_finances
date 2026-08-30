from django.db import migrations


def repair_snapshot_ownership(apps, schema_editor):
    snapshot_model = apps.get_model("holdings", "AccountBalanceSnapshot")
    for snapshot in snapshot_model.objects.select_related("account").iterator():
        if snapshot.user_id != snapshot.account.user_id:
            snapshot_model.objects.filter(pk=snapshot.pk).update(
                user_id=snapshot.account.user_id
            )


class Migration(migrations.Migration):
    dependencies = [
        ("holdings", "0006_alter_accountbalancesnapshot_user"),
    ]

    operations = [
        migrations.RunPython(repair_snapshot_ownership, migrations.RunPython.noop),
    ]
