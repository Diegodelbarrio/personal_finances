from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase

from ..models import Transaction, Category, SubCategory
from ..services import queries, metrics

User = get_user_model()


class FinancesServicesTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password123")

        self.cat_income = Category.objects.create(
            user=self.user,
            name="Salary",
            transaction_type="INCOME",
            expense_type="N/A",
        )
        self.cat_expense_fixed = Category.objects.create(
            user=self.user,
            name="Rent",
            transaction_type="EXPENSE",
            expense_type="FIXED",
            is_housing=True,
        )
        self.cat_expense_var = Category.objects.create(
            user=self.user,
            name="Groceries",
            transaction_type="EXPENSE",
            expense_type="VARIABLE",
            is_housing=False,
        )

        self.sub_salary = SubCategory.objects.create(
            user=self.user,
            name="Main Job",
            parent_category=self.cat_income,
        )
        self.sub_rent = SubCategory.objects.create(
            user=self.user,
            name="Apartment",
            parent_category=self.cat_expense_fixed,
        )
        self.sub_food = SubCategory.objects.create(
            user=self.user,
            name="Supermarket",
            parent_category=self.cat_expense_var,
        )

    def test_queries_isolation(self):
        other_user = User.objects.create_user(username="other", password="123")
        Transaction.objects.create(
            user=self.user, amount=100, subcategory=self.sub_salary, date=date(2024, 1, 1)
        )

        user_qs = queries.get_base_transaction_qs(self.user)
        other_qs = queries.get_base_transaction_qs(other_user)

        self.assertEqual(user_qs.count(), 1)
        self.assertEqual(other_qs.count(), 0)

    def test_metrics_calculation(self):
        Transaction.objects.create(
            user=self.user, amount=5000, subcategory=self.sub_salary, date=date(2024, 1, 1)
        )
        Transaction.objects.create(
            user=self.user, amount=-1500, subcategory=self.sub_rent, date=date(2024, 1, 5)
        )
        Transaction.objects.create(
            user=self.user, amount=-500, subcategory=self.sub_food, date=date(2024, 1, 10)
        )

        qs = Transaction.objects.filter(user=self.user, date__year=2024, date__month=1)
        stats = metrics.get_period_metrics(qs)

        self.assertEqual(stats["income"], 5000)
        self.assertEqual(stats["expenses"], 2000)
        self.assertEqual(stats["savings"], 3000)
        self.assertEqual(stats["fixed"], 1500)
        self.assertEqual(stats["variable"], 500)
        self.assertEqual(stats["no_housing"], 500)
        self.assertFalse(stats["is_incomplete"])

    def test_previous_month_income_logic(self):
        Transaction.objects.create(
            user=self.user, amount=4000, subcategory=self.sub_salary, date=date(2023, 12, 15)
        )
        Transaction.objects.create(
            user=self.user, amount=4500, subcategory=self.sub_salary, date=date(2024, 1, 15)
        )

        base_qs = queries.get_base_transaction_qs(self.user)

        prev_inc = metrics.get_previous_month_income(base_qs, 2024, 1)
        self.assertEqual(prev_inc, 4000)

    def test_metrics_empty_data(self):
        qs = Transaction.objects.filter(user=self.user, date__year=2020)
        stats = metrics.get_period_metrics(qs)

        self.assertEqual(stats["income"], 0)
        self.assertEqual(stats["expenses"], 0)
        self.assertEqual(stats["savings"], 0)
        self.assertFalse(stats["is_incomplete"])

    def test_expense_distribution_chart(self):
        Transaction.objects.create(
            user=self.user, amount=-1000, subcategory=self.sub_rent, date=date(2024, 1, 1)
        )
        Transaction.objects.create(
            user=self.user, amount=-200, subcategory=self.sub_food, date=date(2024, 1, 2)
        )

        qs = Transaction.objects.filter(user=self.user, date__year=2024)
        chart_data = metrics.get_expense_distribution_chart(qs)

        self.assertIn("Rent", chart_data["labels"])
        self.assertIn("Groceries", chart_data["labels"])
        values_by_label = dict(zip(chart_data["labels"], chart_data["data"]))
        self.assertEqual(values_by_label["Rent"], 1000.0)
        self.assertEqual(values_by_label["Groceries"], 200.0)
