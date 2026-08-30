from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from finances.models import Category, Location, SubCategory, Transaction

User = get_user_model()


class TransactionViewsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="diego", password="test1234")
        self.other_user = User.objects.create_user(username="other", password="test1234")

        self.expense_category = Category.objects.create(
            user=self.user,
            name="Food",
            transaction_type="EXPENSE",
            expense_type="VARIABLE",
        )
        self.income_category = Category.objects.create(
            user=self.user,
            name="Salary",
            transaction_type="INCOME",
            expense_type="N/A",
        )
        self.sub_expense = SubCategory.objects.create(
            user=self.user,
            parent_category=self.expense_category,
            name="Groceries",
        )
        self.sub_income = SubCategory.objects.create(
            user=self.user,
            parent_category=self.income_category,
            name="Main Job",
        )
        self.location = Location.objects.create(user=self.user, name="Madrid")

        self.other_category = Category.objects.create(
            user=self.other_user,
            name="Other Food",
            transaction_type="EXPENSE",
            expense_type="VARIABLE",
        )
        self.other_sub = SubCategory.objects.create(
            user=self.other_user,
            parent_category=self.other_category,
            name="Other Groceries",
        )

    def test_create_transaction_sets_owner_and_negative_sign_for_expense(self):
        self.client.login(username="diego", password="test1234")

        response = self.client.post(
            reverse("create_transaction"),
            {
                "date": date(2026, 2, 10),
                "amount": "125.50",
                "description": "Weekly groceries",
                "subcategory": self.sub_expense.id,
                "location": self.location.id,
                "next": "/home/",
            },
        )

        self.assertRedirects(response, "/home/")
        tx = Transaction.objects.get(description="Weekly groceries")
        self.assertEqual(tx.user, self.user)
        self.assertEqual(tx.amount, Decimal("-125.50"))

    def test_create_transaction_sets_positive_sign_for_income(self):
        self.client.login(username="diego", password="test1234")

        self.client.post(
            reverse("create_transaction"),
            {
                "date": date(2026, 2, 10),
                "amount": "2100",
                "description": "Payroll",
                "subcategory": self.sub_income.id,
                "location": "",
            },
        )

        tx = Transaction.objects.get(description="Payroll")
        self.assertEqual(tx.amount, Decimal("2100.00"))

    def test_create_transaction_rejects_foreign_subcategory(self):
        self.client.login(username="diego", password="test1234")

        response = self.client.post(
            reverse("create_transaction"),
            {
                "date": date(2026, 2, 10),
                "amount": "50",
                "description": "Invalid",
                "subcategory": self.other_sub.id,
                "location": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("subcategory", response.context["form"].errors)
        self.assertFalse(Transaction.objects.filter(description="Invalid").exists())

    def test_edit_transaction_requires_owner(self):
        foreign_tx = Transaction.objects.create(
            user=self.other_user,
            date=date(2026, 2, 11),
            amount=20,
            description="Foreign tx",
            subcategory=self.other_sub,
        )
        self.client.login(username="diego", password="test1234")

        response = self.client.get(reverse("edit_transaction", args=[foreign_tx.id]))

        self.assertEqual(response.status_code, 404)

    def test_delete_transaction_requires_owner(self):
        foreign_tx = Transaction.objects.create(
            user=self.other_user,
            date=date(2026, 2, 11),
            amount=20,
            description="Foreign tx",
            subcategory=self.other_sub,
        )
        self.client.login(username="diego", password="test1234")

        response = self.client.post(reverse("delete_transaction", args=[foreign_tx.id]))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Transaction.objects.filter(id=foreign_tx.id).exists())

    def test_summary_handles_invalid_period_query_params(self):
        self.client.login(username="diego", password="test1234")

        response = self.client.get(reverse("summary"), {"year": "invalid", "month": "99"})

        now = timezone.now()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["sel_year"], now.year)
        self.assertEqual(response.context["sel_month"], now.month)
        self.assertEqual(len(response.context["months"]), 12)
        self.assertEqual(response.context["selected_month_name"], now.strftime("%B"))

    def test_summary_includes_requested_empty_year_and_all_months(self):
        self.client.login(username="diego", password="test1234")

        response = self.client.get(reverse("summary"), {"year": "2035", "month": "1"})

        self.assertEqual(response.status_code, 200)
        self.assertIn(2035, response.context["years"])
        self.assertEqual(response.context["sel_year"], 2035)
        self.assertEqual(response.context["sel_month"], 1)
        self.assertEqual(response.context["selected_month_name"], "January")
        self.assertEqual(len(response.context["months"]), 12)
