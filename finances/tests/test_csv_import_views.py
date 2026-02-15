from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from finances.models import Category, Location, SubCategory, Transaction

User = get_user_model()


class FinanceCSVImportViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="diego", password="test1234")
        self.category = Category.objects.create(
            user=self.user,
            name="Food",
            transaction_type="EXPENSE",
            expense_type="VARIABLE",
        )
        self.subcategory = SubCategory.objects.create(
            user=self.user,
            parent_category=self.category,
            name="Groceries",
        )
        self.location = Location.objects.create(user=self.user, name="Madrid")

    def test_import_finance_transactions_csv_creates_transactions(self):
        self.client.login(username="diego", password="test1234")
        csv_content = (
            "date,amount,category,subcategory,description,location\n"
            "2026-02-10,45.90,Food,Groceries,Weekly groceries,Madrid\n"
        )
        csv_file = SimpleUploadedFile(
            "finance_transactions.csv",
            csv_content.encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("import_transactions_csv"),
            {
                "csv_file": csv_file,
                "next": "/home/",
            },
        )

        self.assertRedirects(response, "/home/")
        transaction = Transaction.objects.get(user=self.user, description="Weekly groceries")
        self.assertEqual(transaction.date, date(2026, 2, 10))
        self.assertEqual(transaction.subcategory, self.subcategory)
        self.assertEqual(transaction.location, self.location)
        self.assertEqual(transaction.amount, Decimal("-45.90"))

    def test_import_finance_transactions_csv_rejects_invalid_header(self):
        self.client.login(username="diego", password="test1234")
        csv_content = (
            "date,total,subcategory\n"
            "2026-02-10,45.90,Groceries\n"
        )
        csv_file = SimpleUploadedFile(
            "invalid_finance_transactions.csv",
            csv_content.encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("import_transactions_csv"),
            {"csv_file": csv_file},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Missing required columns")
        self.assertFalse(Transaction.objects.filter(user=self.user).exists())
