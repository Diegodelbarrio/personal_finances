from datetime import date
from decimal import Decimal

from django.contrib.messages import get_messages
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from finances.models import Category, SubCategory, Transaction


User = get_user_model()


class ManageCategoriesViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="diego", password="testpass123")
        self.other_user = User.objects.create_user(username="other", password="testpass123")
        self.manage_url = reverse("manage_categories")
        self.create_category_url = reverse("create_category")
        self.create_subcategory_url = reverse("create_subcategory")

        self.my_category = Category.objects.create(
            user=self.user,
            name="Food",
            transaction_type="EXPENSE",
            expense_type="VARIABLE",
            is_housing=False,
        )
        self.other_category = Category.objects.create(
            user=self.other_user,
            name="Salary",
            transaction_type="INCOME",
            expense_type="N/A",
            is_housing=False,
        )

    def test_requires_login(self):
        response = self.client.get(self.manage_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_shows_only_logged_user_categories_and_subcategories(self):
        SubCategory.objects.create(
            user=self.user,
            parent_category=self.my_category,
            name="Groceries",
            is_essential=False,
        )
        other_sub = SubCategory.objects.create(
            user=self.other_user,
            parent_category=self.other_category,
            name="Main Job",
            is_essential=True,
        )

        self.client.login(username="diego", password="testpass123")
        response = self.client.get(self.manage_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Food")
        self.assertContains(response, "Groceries")
        self.assertNotContains(response, "Salary")
        self.assertNotContains(response, other_sub.name)

    def test_create_category_in_separate_view(self):
        self.client.login(username="diego", password="testpass123")
        payload = {
            "name": "Transport",
            "transaction_type": "EXPENSE",
            "expense_type": "FIXED",
        }
        response = self.client.post(self.create_category_url, payload, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Category.objects.filter(user=self.user, name="Transport", expense_type="FIXED").exists()
        )
        self.assertContains(response, "Category created successfully.")

    def test_create_category_can_include_inline_subcategories(self):
        self.client.login(username="diego", password="testpass123")
        payload = {
            "name": "Transport",
            "transaction_type": "EXPENSE",
            "expense_type": "VARIABLE",
            "subcategory_names": "Taxi\nPublic Transport\nParking",
        }

        response = self.client.post(self.create_category_url, payload, follow=True)

        self.assertEqual(response.status_code, 200)
        created_category = Category.objects.get(user=self.user, name="Transport")
        created_subcategories = list(
            SubCategory.objects.filter(user=self.user, parent_category=created_category).order_by("name")
        )
        self.assertEqual(len(created_subcategories), 3)
        self.assertContains(response, "Category created successfully with 3 subcategories.")

    def test_create_category_rejects_duplicated_inline_subcategories(self):
        self.client.login(username="diego", password="testpass123")
        payload = {
            "name": "Transport",
            "transaction_type": "EXPENSE",
            "expense_type": "VARIABLE",
            "subcategory_names": "Taxi\n taxi ",
        }

        response = self.client.post(self.create_category_url, payload, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Remove duplicated subcategory names in this list.")
        self.assertFalse(Category.objects.filter(user=self.user, name="Transport").exists())

    def test_create_subcategory_in_separate_view(self):
        self.client.login(username="diego", password="testpass123")
        payload = {
            "parent_category": self.my_category.id,
            "name": "Restaurants",
            "is_essential": "on",
        }
        response = self.client.post(self.create_subcategory_url, payload, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            SubCategory.objects.filter(
                user=self.user,
                parent_category=self.my_category,
                name="Restaurants",
            ).exists()
        )
        self.assertContains(response, "Subcategory created successfully.")

    def test_edit_category_prepopulates_and_locks_name(self):
        self.client.login(username="diego", password="testpass123")
        response = self.client.get(
            reverse("edit_category", kwargs={"category_id": self.my_category.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["name"], "Food")
        self.assertTrue(response.context["form"].fields["name"].disabled)

    def test_edit_subcategory_prepopulates_and_locks_name(self):
        subcategory = SubCategory.objects.create(
            user=self.user,
            parent_category=self.my_category,
            name="Groceries",
            is_essential=False,
        )
        self.client.login(username="diego", password="testpass123")
        response = self.client.get(
            reverse("edit_subcategory", kwargs={"subcategory_id": subcategory.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["name"], "Groceries")
        self.assertTrue(response.context["form"].fields["name"].disabled)

    def test_edit_category_name_is_not_mutable(self):
        self.client.login(username="diego", password="testpass123")
        response = self.client.post(
            reverse("edit_category", kwargs={"category_id": self.my_category.id}),
            {
                "name": "Renamed Category",
                "transaction_type": "EXPENSE",
                "expense_type": "FIXED",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.my_category.refresh_from_db()
        self.assertEqual(self.my_category.name, "Food")
        self.assertEqual(self.my_category.expense_type, "FIXED")
        self.assertContains(response, "Category updated successfully.")

    def test_edit_subcategory_name_is_not_mutable(self):
        subcategory = SubCategory.objects.create(
            user=self.user,
            parent_category=self.my_category,
            name="Groceries",
            is_essential=False,
        )
        self.client.login(username="diego", password="testpass123")
        response = self.client.post(
            reverse("edit_subcategory", kwargs={"subcategory_id": subcategory.id}),
            {
                "parent_category": self.my_category.id,
                "name": "Renamed Subcategory",
                "is_essential": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        subcategory.refresh_from_db()
        self.assertEqual(subcategory.name, "Groceries")
        self.assertTrue(subcategory.is_essential)
        self.assertContains(response, "Subcategory updated successfully.")

    def test_parent_category_selector_shows_only_category_name(self):
        self.client.login(username="diego", password="testpass123")
        response = self.client.get(self.create_subcategory_url)

        self.assertEqual(response.status_code, 200)
        field_choices = dict(response.context["form"].fields["parent_category"].choices)
        self.assertEqual(field_choices[self.my_category.id], "Food")
        self.assertNotIn(self.user.username, field_choices[self.my_category.id])

    def test_categories_default_order_is_alphabetical(self):
        category_two = Category.objects.create(
            user=self.user,
            name="Utilities",
            transaction_type="EXPENSE",
            expense_type="FIXED",
            is_housing=False,
        )
        SubCategory.objects.create(
            user=self.user,
            parent_category=self.my_category,
            name="One",
            is_essential=False,
        )
        SubCategory.objects.create(
            user=self.user,
            parent_category=category_two,
            name="Two",
            is_essential=False,
        )
        SubCategory.objects.create(
            user=self.user,
            parent_category=category_two,
            name="Three",
            is_essential=False,
        )

        self.client.login(username="diego", password="testpass123")
        response = self.client.get(self.manage_url)

        self.assertEqual(response.status_code, 200)
        categories = list(response.context["categories"])
        self.assertEqual([c.name for c in categories], ["Food", category_two.name])

    def test_subcategories_queryset_contains_all_user_subcategories(self):
        category_two = Category.objects.create(
            user=self.user,
            name="Utilities",
            transaction_type="EXPENSE",
            expense_type="FIXED",
            is_housing=False,
        )
        sub_one = SubCategory.objects.create(
            user=self.user,
            parent_category=self.my_category,
            name="Groceries",
            is_essential=False,
        )
        sub_two = SubCategory.objects.create(
            user=self.user,
            parent_category=category_two,
            name="Electricity",
            is_essential=True,
        )

        self.client.login(username="diego", password="testpass123")
        response = self.client.get(self.manage_url)

        self.assertEqual(response.status_code, 200)
        subcategories = list(response.context["subcategories"])
        self.assertEqual(len(subcategories), 2)
        self.assertSetEqual({x.id for x in subcategories}, {sub_one.id, sub_two.id})

    def test_partial_categories_param_keeps_full_page_render(self):
        self.client.login(username="diego", password="testpass123")
        response = self.client.get(self.manage_url, {"partial": "categories"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Category Manager")
        self.assertContains(response, "Your Categories")
        self.assertContains(response, "Your Subcategories")

    def test_partial_subcategories_param_keeps_full_page_render(self):
        self.client.login(username="diego", password="testpass123")
        response = self.client.get(self.manage_url, {"partial": "subcategories"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Category Manager")
        self.assertContains(response, "Your Categories")
        self.assertContains(response, "Your Subcategories")

    def test_manage_categories_includes_client_side_table_controls(self):
        self.client.login(username="diego", password="testpass123")
        response = self.client.get(self.manage_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="categoriesTableBody"')
        self.assertContains(response, 'id="subcategoriesTableBody"')
        self.assertContains(response, 'id="categoryNameFilter"')
        self.assertContains(response, 'id="subcategoryNameFilter"')
        self.assertContains(response, 'data-table="categories"')
        self.assertContains(response, 'data-table="subcategories"')

    def test_manage_categories_shows_setup_options_when_user_has_no_categories(self):
        Category.objects.filter(user=self.user).delete()
        self.client.login(username="diego", password="testpass123")

        response = self.client.get(self.manage_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Start Your Category Setup")
        self.assertContains(response, 'id="defaultCategoriesForm"')
        self.assertContains(response, "Option 1: Build Manually")
        self.assertContains(response, "Option 2: Use Default Categories")

    def test_default_categories_can_be_created_from_setup_with_multi_selection(self):
        Category.objects.filter(user=self.user).delete()
        self.client.login(username="diego", password="testpass123")

        response = self.client.post(
            self.manage_url,
            {
                "action": "create_default_categories",
                "category_keys": ["income", "food"],
                "subcategory_keys": ["income_salary", "income_bonus", "food_grocery"],
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        income_category = Category.objects.get(user=self.user, name="Income")
        food_category = Category.objects.get(user=self.user, name="Food")
        self.assertEqual(income_category.transaction_type, "INCOME")
        self.assertEqual(income_category.expense_type, "N/A")
        self.assertEqual(food_category.transaction_type, "EXPENSE")
        self.assertEqual(food_category.expense_type, "VARIABLE")
        self.assertTrue(
            SubCategory.objects.filter(
                user=self.user,
                parent_category=income_category,
                name="Salary",
            ).exists()
        )
        self.assertTrue(
            SubCategory.objects.filter(
                user=self.user,
                parent_category=income_category,
                name="Bonus",
            ).exists()
        )
        self.assertFalse(
            SubCategory.objects.filter(
                user=self.user,
                parent_category=income_category,
                name="Freelance",
            ).exists()
        )
        self.assertTrue(
            SubCategory.objects.filter(
                user=self.user,
                parent_category=food_category,
                name="Groceries",
            ).exists()
        )
        groceries = SubCategory.objects.get(
            user=self.user,
            parent_category=food_category,
            name="Groceries",
        )
        self.assertEqual(groceries.budget_group, SubCategory.BudgetGroup.NEEDS)
        self.assertEqual(groceries.expense_nature, SubCategory.ExpenseNature.VARIABLE)
        self.assertTrue(groceries.is_essential)
        self.assertContains(response, "Default categories created successfully")

    def test_default_categories_setup_requires_income_category(self):
        Category.objects.filter(user=self.user).delete()
        self.client.login(username="diego", password="testpass123")

        response = self.client.post(
            self.manage_url,
            {
                "action": "create_default_categories",
                "category_keys": ["food"],
                "subcategory_keys": ["food_grocery"],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The category Income is required.")
        self.assertFalse(Category.objects.filter(user=self.user, name="Food").exists())

    def test_default_categories_setup_completes_existing_categories(self):
        self.client.login(username="diego", password="testpass123")

        response = self.client.post(
            self.manage_url,
            {
                "action": "create_default_categories",
                "category_keys": ["income", "food"],
                "subcategory_keys": ["income_salary", "food_grocery", "food_restaurants"],
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Category.objects.filter(user=self.user, name="Food").count(), 1)
        self.assertTrue(Category.objects.filter(user=self.user, name="Income").exists())
        self.assertTrue(
            SubCategory.objects.filter(
                user=self.user,
                parent_category=self.my_category,
                name="Groceries",
            ).exists()
        )
        self.assertTrue(
            SubCategory.objects.filter(
                user=self.user,
                parent_category=self.my_category,
                name="Restaurants",
            ).exists()
        )
        self.assertContains(response, "Default categories applied")

    def test_edit_rejects_foreign_category(self):
        self.client.login(username="diego", password="testpass123")
        response = self.client.get(reverse("edit_category", kwargs={"category_id": self.other_category.id}))
        self.assertEqual(response.status_code, 404)

    def test_edit_rejects_foreign_subcategory(self):
        other_sub = SubCategory.objects.create(
            user=self.other_user,
            parent_category=self.other_category,
            name="Bonuses",
            is_essential=False,
        )
        self.client.login(username="diego", password="testpass123")
        response = self.client.get(
            reverse("edit_subcategory", kwargs={"subcategory_id": other_sub.id})
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_category_fails_when_it_has_transactions(self):
        subcategory = SubCategory.objects.create(
            user=self.user,
            parent_category=self.my_category,
            name="Groceries",
            is_essential=False,
        )
        Transaction.objects.create(
            user=self.user,
            date=date(2025, 1, 10),
            amount=100,
            description="Supermarket",
            subcategory=subcategory,
        )

        self.client.login(username="diego", password="testpass123")
        response = self.client.post(
            self.manage_url,
            {"action": "delete_category", "category_id": self.my_category.id},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Category.objects.filter(id=self.my_category.id).exists())
        self.assertContains(
            response,
            "This category cannot be deleted because it has subcategories with linked transactions.",
        )

    def test_delete_subcategory_fails_when_it_has_transactions(self):
        subcategory = SubCategory.objects.create(
            user=self.user,
            parent_category=self.my_category,
            name="Groceries",
            is_essential=False,
        )
        Transaction.objects.create(
            user=self.user,
            date=date(2025, 1, 10),
            amount=100,
            description="Supermarket",
            subcategory=subcategory,
        )

        self.client.login(username="diego", password="testpass123")
        response = self.client.post(
            self.manage_url,
            {"action": "delete_subcategory", "subcategory_id": subcategory.id},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(SubCategory.objects.filter(id=subcategory.id).exists())
        self.assertContains(
            response,
            "This subcategory cannot be deleted because it has linked transactions.",
        )

    def test_batch_delete_categories_deletes_only_current_user_selection(self):
        utilities = Category.objects.create(
            user=self.user,
            name="Utilities",
            transaction_type="EXPENSE",
            expense_type="FIXED",
        )
        self.client.login(username="diego", password="testpass123")

        response = self.client.post(
            self.manage_url,
            {
                "action": "delete_categories_batch",
                "category_ids": [self.my_category.id, utilities.id, self.other_category.id],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Category.objects.filter(id=self.my_category.id).exists())
        self.assertFalse(Category.objects.filter(id=utilities.id).exists())
        self.assertTrue(Category.objects.filter(id=self.other_category.id).exists())

    def test_batch_delete_categories_skips_protected_categories(self):
        protected_subcategory = SubCategory.objects.create(
            user=self.user,
            parent_category=self.my_category,
            name="Groceries",
        )
        Transaction.objects.create(
            user=self.user,
            date=date(2025, 1, 10),
            amount=100,
            description="Supermarket",
            subcategory=protected_subcategory,
        )
        utilities = Category.objects.create(
            user=self.user,
            name="Utilities",
            transaction_type="EXPENSE",
            expense_type="FIXED",
        )
        self.client.login(username="diego", password="testpass123")

        response = self.client.post(
            self.manage_url,
            {
                "action": "delete_categories_batch",
                "category_ids": [self.my_category.id, utilities.id],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Category.objects.filter(id=self.my_category.id).exists())
        self.assertFalse(Category.objects.filter(id=utilities.id).exists())
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertTrue(any("Deleted 1 category." in message for message in messages))
        self.assertTrue(any("Skipped 1 protected category" in message for message in messages))

    def test_batch_delete_subcategories_deletes_only_current_user_selection(self):
        groceries = SubCategory.objects.create(
            user=self.user,
            parent_category=self.my_category,
            name="Groceries",
        )
        restaurants = SubCategory.objects.create(
            user=self.user,
            parent_category=self.my_category,
            name="Restaurants",
        )
        other_subcategory = SubCategory.objects.create(
            user=self.other_user,
            parent_category=self.other_category,
            name="Main Job",
        )
        self.client.login(username="diego", password="testpass123")

        response = self.client.post(
            self.manage_url,
            {
                "action": "delete_subcategories_batch",
                "subcategory_ids": [groceries.id, restaurants.id, other_subcategory.id],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(SubCategory.objects.filter(id=groceries.id).exists())
        self.assertFalse(SubCategory.objects.filter(id=restaurants.id).exists())
        self.assertTrue(SubCategory.objects.filter(id=other_subcategory.id).exists())

    def test_batch_delete_subcategories_skips_protected_subcategories(self):
        groceries = SubCategory.objects.create(
            user=self.user,
            parent_category=self.my_category,
            name="Groceries",
        )
        restaurants = SubCategory.objects.create(
            user=self.user,
            parent_category=self.my_category,
            name="Restaurants",
        )
        Transaction.objects.create(
            user=self.user,
            date=date(2025, 1, 10),
            amount=100,
            description="Supermarket",
            subcategory=groceries,
        )
        self.client.login(username="diego", password="testpass123")

        response = self.client.post(
            self.manage_url,
            {
                "action": "delete_subcategories_batch",
                "subcategory_ids": [groceries.id, restaurants.id],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(SubCategory.objects.filter(id=groceries.id).exists())
        self.assertFalse(SubCategory.objects.filter(id=restaurants.id).exists())
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertTrue(any("Deleted 1 subcategory." in message for message in messages))
        self.assertTrue(any("Skipped 1 protected subcategory" in message for message in messages))

    def test_change_category_transaction_type_updates_related_transactions(self):
        subcategory = SubCategory.objects.create(
            user=self.user,
            parent_category=self.my_category,
            name="Groceries",
            is_essential=False,
        )
        transaction = Transaction.objects.create(
            user=self.user,
            date=date(2025, 1, 10),
            amount=100,
            description="Supermarket",
            subcategory=subcategory,
        )
        self.assertEqual(transaction.amount, Decimal("-100.00"))

        self.client.login(username="diego", password="testpass123")
        response = self.client.post(
            reverse("edit_category", kwargs={"category_id": self.my_category.id}),
            {
                "name": "Food",
                "transaction_type": "INCOME",
                "expense_type": "N/A",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.my_category.refresh_from_db()
        transaction.refresh_from_db()
        self.assertEqual(self.my_category.transaction_type, "INCOME")
        self.assertEqual(transaction.amount, Decimal("100.00"))

    def test_moving_subcategory_to_income_category_updates_transactions(self):
        income_category = Category.objects.create(
            user=self.user,
            name="Salary",
            transaction_type="INCOME",
            expense_type="N/A",
            is_housing=False,
        )
        subcategory = SubCategory.objects.create(
            user=self.user,
            parent_category=self.my_category,
            name="Groceries",
            is_essential=False,
        )
        transaction = Transaction.objects.create(
            user=self.user,
            date=date(2025, 1, 10),
            amount=250,
            description="Transfer",
            subcategory=subcategory,
        )
        self.assertEqual(transaction.amount, Decimal("-250.00"))

        self.client.login(username="diego", password="testpass123")
        response = self.client.post(
            reverse("edit_subcategory", kwargs={"subcategory_id": subcategory.id}),
            {
                "parent_category": income_category.id,
                "name": "Groceries",
                "is_essential": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        subcategory.refresh_from_db()
        transaction.refresh_from_db()
        self.assertEqual(subcategory.parent_category_id, income_category.id)
        self.assertEqual(transaction.amount, Decimal("250.00"))
