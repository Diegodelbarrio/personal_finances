from django.contrib.auth import get_user_model
from django.test import TestCase

from finances.forms import DefaultCategoryPresetForm
from finances.models import Category, SubCategory
from finances.services.default_categories import get_default_category_blueprints
from finances.views import _create_default_categories


User = get_user_model()


class DefaultCategoryPresetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="preset-user", password="testpass123")

    def test_default_blueprints_cover_common_personal_finance_categories(self):
        blueprints = get_default_category_blueprints()
        keys = {category["key"] for category in blueprints}

        self.assertTrue(
            {
                "income",
                "housing",
                "utilities",
                "food",
                "transport",
                "health",
                "insurance",
                "debt",
                "savings",
                "personal_care",
                "shopping",
                "leisure",
                "travel",
                "taxes_fees",
                "misc",
            }.issubset(keys)
        )

    def test_default_food_subcategories_split_needs_and_wants(self):
        food = next(
            category
            for category in get_default_category_blueprints()
            if category["key"] == "food"
        )
        subcategories = {
            subcategory["key"]: subcategory
            for subcategory in food["subcategories"]
        }

        self.assertEqual(subcategories["food_grocery"]["budget_group"], SubCategory.BudgetGroup.NEEDS)
        self.assertEqual(subcategories["food_grocery"]["expense_nature"], SubCategory.ExpenseNature.VARIABLE)
        self.assertTrue(subcategories["food_grocery"]["is_essential"])
        self.assertEqual(subcategories["food_restaurants"]["budget_group"], SubCategory.BudgetGroup.WANTS)
        self.assertEqual(subcategories["food_delivery"]["budget_group"], SubCategory.BudgetGroup.WANTS)
        self.assertEqual(subcategories["food_treats"]["budget_group"], SubCategory.BudgetGroup.WANTS)

    def test_income_is_not_required_when_user_already_has_income(self):
        Category.objects.create(
            user=self.user,
            name="Income",
            transaction_type=Category.TransactionType.INCOME,
            expense_type=Category.ExpenseType.NOT_APPLICABLE,
        )

        form = DefaultCategoryPresetForm(
            {
                "category_keys": ["food"],
                "subcategory_keys": ["food_grocery"],
            },
            user=self.user,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_create_default_categories_completes_existing_category(self):
        food_category = Category.objects.create(
            user=self.user,
            name="Food",
            transaction_type=Category.TransactionType.EXPENSE,
            expense_type=Category.ExpenseType.VARIABLE,
        )
        SubCategory.objects.create(
            user=self.user,
            parent_category=food_category,
            name="Groceries",
            budget_group=SubCategory.BudgetGroup.NEEDS,
            expense_nature=SubCategory.ExpenseNature.VARIABLE,
            is_essential=True,
        )
        food = next(
            category
            for category in get_default_category_blueprints()
            if category["key"] == "food"
        )
        payload = [
            {
                "name": food["name"],
                "transaction_type": food["transaction_type"],
                "expense_type": food["expense_type"],
                "is_housing": food["is_housing"],
                "subcategories": [
                    subcategory
                    for subcategory in food["subcategories"]
                    if subcategory["key"] in {"food_grocery", "food_restaurants"}
                ],
            }
        ]

        result = _create_default_categories(self.user, payload)

        self.assertEqual(result["created_categories"], 0)
        self.assertEqual(result["updated_categories"], 1)
        self.assertEqual(result["created_subcategories"], 1)
        self.assertEqual(Category.objects.filter(user=self.user, name="Food").count(), 1)
        self.assertTrue(
            SubCategory.objects.filter(
                user=self.user,
                parent_category=food_category,
                name="Restaurants",
                budget_group=SubCategory.BudgetGroup.WANTS,
                expense_nature=SubCategory.ExpenseNature.VARIABLE,
            ).exists()
        )
