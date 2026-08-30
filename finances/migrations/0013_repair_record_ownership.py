from django.db import migrations


def repair_record_ownership(apps, schema_editor):
    subcategory_model = apps.get_model("finances", "SubCategory")
    transaction_model = apps.get_model("finances", "Transaction")

    for subcategory in subcategory_model.objects.select_related(
        "parent_category"
    ).iterator():
        expected_user_id = subcategory.parent_category.user_id
        if subcategory.user_id != expected_user_id:
            subcategory_model.objects.filter(pk=subcategory.pk).update(
                user_id=expected_user_id
            )

    for transaction in transaction_model.objects.select_related(
        "subcategory", "location"
    ).iterator():
        expected_user_id = transaction.subcategory.user_id
        updates = {}
        if transaction.user_id != expected_user_id:
            updates["user_id"] = expected_user_id
        if transaction.location_id and transaction.location.user_id != expected_user_id:
            updates["location_id"] = None
        if updates:
            transaction_model.objects.filter(pk=transaction.pk).update(**updates)


class Migration(migrations.Migration):
    dependencies = [
        ("finances", "0012_alter_transaction_amount"),
    ]

    operations = [
        migrations.RunPython(repair_record_ownership, migrations.RunPython.noop),
    ]
