from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from finances.models import Category, SubCategory, Transaction as FinanceTransaction
from holdings.models import AccountBalanceSnapshot, BankAccount
from investments.models import Asset, AssetHistory

User = get_user_model()


@override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class ReportYearSelectionViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="diego", password="test1234")
        self.client.login(username="diego", password="test1234")

    def _create_finance_subcategory(self, name="Salary"):
        category = Category.objects.create(
            user=self.user,
            name=name,
            transaction_type="INCOME",
            expense_type="N/A",
        )
        return SubCategory.objects.create(
            user=self.user,
            parent_category=category,
            name=f"{name} Subcategory",
        )

    def test_investment_report_uses_investment_years_even_without_finance_transactions(self):
        current_year = timezone.now().year
        asset = Asset.objects.create(
            user=self.user,
            name="ETF World",
            category="INDEX_FUND",
            platform="Test Broker",
        )
        AssetHistory.objects.create(
            user=self.user,
            asset=asset,
            date=date(current_year - 2, 12, 31),
            total_value=Decimal("5000.00"),
        )

        response = self.client.get(reverse("reports:report_investments"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["years"],
            [current_year, current_year - 1, current_year - 2],
        )
        self.assertEqual(response.context["selected_year"], current_year)

    def test_holdings_report_uses_snapshot_years_even_without_finance_transactions(self):
        current_year = timezone.now().year
        account = BankAccount.objects.create(
            user=self.user,
            name="Main Account",
            institution="Test Bank",
            account_type="CHECKING",
        )
        AccountBalanceSnapshot.objects.create(
            user=self.user,
            account=account,
            date=date(current_year - 1, 1, 31),
            balance=Decimal("1250.00"),
        )

        response = self.client.get(reverse("reports:report_holdings"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["years"],
            [current_year, current_year - 1],
        )
        self.assertEqual(response.context["selected_year"], current_year)

    def test_financial_report_exposes_full_year_span_from_first_to_last_transaction(self):
        current_year = timezone.now().year
        subcategory = self._create_finance_subcategory()

        FinanceTransaction.objects.create(
            user=self.user,
            date=date(current_year - 2, 1, 15),
            amount=Decimal("1000.00"),
            description="Historic salary",
            subcategory=subcategory,
        )
        FinanceTransaction.objects.create(
            user=self.user,
            date=date(current_year + 1, 2, 15),
            amount=Decimal("1200.00"),
            description="Planned salary",
            subcategory=subcategory,
        )

        response = self.client.get(reverse("reports:report_finance"), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["years"],
            [current_year + 1, current_year, current_year - 1, current_year - 2],
        )
        self.assertEqual(response.context["selected_year"], current_year)
