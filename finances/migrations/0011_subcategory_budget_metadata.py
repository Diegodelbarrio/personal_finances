from django.db import migrations, models


NEEDS = "NEEDS"
WANTS = "WANTS"
SAVINGS = "SAVINGS"
NOT_APPLICABLE = "N/A"
FIXED = "FIXED"
VARIABLE = "VARIABLE"

NEEDS_KEYWORDS = (
    "insurance",
    "internet",
    "wifi",
    "rent",
    "mortgage",
    "utilities",
    "utility",
    "medical",
    "pharmacy",
    "groceries",
    "grocery",
    "supermarket",
    "market",
    "mercado",
    "supermercado",
    "public transport",
    "metro",
    "bus",
    "train",
    "fuel",
)
NEEDS_CATEGORY_KEYWORDS = (
    "rent",
    "mortgage",
    "housing",
    "utilities",
    "utility",
    "internet",
    "wifi",
    "insurance",
)


def _contains_any(value, keywords):
    return any(keyword in value for keyword in keywords)


def _infer_budget_group(category, subcategory):
    if category.transaction_type == "INCOME":
        return NOT_APPLICABLE

    category_name = (category.name or "").casefold()
    subcategory_name = (subcategory.name or "").casefold()
    combined = f"{category_name} {subcategory_name}"

    if _contains_any(
        combined,
        (
            "saving",
            "savings",
            "investment",
            "investing",
            "index",
            "retirement",
            "emergency fund",
            "debt",
            "loan",
            "credit card",
            "stock",
            "brokerage",
            "etf",
            "fondos",
            "inversión",
            "inversion",
        ),
    ):
        return SAVINGS

    if subcategory.is_essential or category.is_housing:
        return NEEDS

    if (
        _contains_any(category_name, NEEDS_CATEGORY_KEYWORDS)
        or _contains_any(subcategory_name, NEEDS_KEYWORDS)
    ):
        return NEEDS

    return WANTS


def _infer_expense_nature(category):
    if category.transaction_type == "INCOME":
        return NOT_APPLICABLE
    if category.expense_type == FIXED:
        return FIXED
    return VARIABLE


def populate_budget_metadata(apps, schema_editor):
    SubCategory = apps.get_model("finances", "SubCategory")

    for subcategory in SubCategory.objects.select_related("parent_category").iterator():
        category = subcategory.parent_category
        subcategory.budget_group = _infer_budget_group(category, subcategory)
        subcategory.expense_nature = _infer_expense_nature(category)
        subcategory.save(update_fields=["budget_group", "expense_nature"])


class Migration(migrations.Migration):

    dependencies = [
        ("finances", "0010_alter_subcategory_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="subcategory",
            name="budget_group",
            field=models.CharField(
                choices=[
                    ("NEEDS", "Needs"),
                    ("WANTS", "Wants"),
                    ("SAVINGS", "Savings"),
                    ("N/A", "Not Applicable"),
                ],
                default="N/A",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="subcategory",
            name="expense_nature",
            field=models.CharField(
                choices=[
                    ("FIXED", "Fixed"),
                    ("VARIABLE", "Variable"),
                    ("N/A", "Not Applicable"),
                ],
                default="N/A",
                max_length=10,
            ),
        ),
        migrations.RunPython(populate_budget_metadata, migrations.RunPython.noop),
    ]
