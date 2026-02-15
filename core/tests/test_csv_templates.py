from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class CSVTemplateDownloadViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="diego", password="test1234")

    def test_requires_login(self):
        response = self.client.get(
            reverse("core:download_csv_template", args=["finance-transactions"])
        )
        self.assertEqual(response.status_code, 302)

    def test_download_finance_template(self):
        self.client.login(username="diego", password="test1234")
        response = self.client.get(
            reverse("core:download_csv_template", args=["finance-transactions"])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn("finance_transactions_template.csv", response["Content-Disposition"])
        self.assertIn(
            "date,amount,category,subcategory,description,location",
            response.content.decode("utf-8"),
        )
        self.assertIn(
            "2026-02-10,45.90,Food,Groceries,Weekly groceries,Madrid",
            response.content.decode("utf-8"),
        )
