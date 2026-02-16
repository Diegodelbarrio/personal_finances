from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from finances.models import Category, SubCategory, Transaction
from holdings.models import AccountBalanceSnapshot, BankAccount
from settings.services.api import SettingsService

User = get_user_model()


class SettingsPhase3InsightsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="settings-user",
            password="test1234",
            email="settings@example.com",
        )

        self.user.settings.net_worth_target = Decimal("15000")
        self.user.settings.annual_savings_target = Decimal("6000")
        self.user.settings.monthly_budget = Decimal("1800")
        self.user.settings.savings_rate_target = Decimal("25")
        self.user.settings.emergency_fund_months = 6
        self.user.settings.financial_profile = "BALANCED"
        self.user.settings.save()

        income_category = Category.objects.create(
            user=self.user,
            name="Salary",
            transaction_type="INCOME",
            expense_type="N/A",
        )
        expense_category = Category.objects.create(
            user=self.user,
            name="Living",
            transaction_type="EXPENSE",
            expense_type="VARIABLE",
        )
        income_subcategory = SubCategory.objects.create(
            user=self.user,
            parent_category=income_category,
            name="Main salary",
        )
        expense_subcategory = SubCategory.objects.create(
            user=self.user,
            parent_category=expense_category,
            name="General expenses",
        )

        today = date.today()
        Transaction.objects.create(
            user=self.user,
            date=today.replace(day=5),
            amount=Decimal("3500"),
            subcategory=income_subcategory,
        )
        Transaction.objects.create(
            user=self.user,
            date=today.replace(day=10),
            amount=Decimal("2200"),
            subcategory=expense_subcategory,
        )

        account = BankAccount.objects.create(
            user=self.user,
            name="Emergency",
            institution="Main Bank",
            account_type="SAVINGS",
            currency="EUR",
        )
        AccountBalanceSnapshot.objects.create(
            user=self.user,
            account=account,
            date=today,
            balance=Decimal("9000"),
        )

    def test_phase3_insights_returns_expected_sections(self):
        insights = SettingsService.get_phase3_insights(self.user)

        self.assertIn("score", insights)
        self.assertIn("recommendations", insights)
        self.assertIn("simulator", insights)
        self.assertIn("snapshot", insights)

        self.assertGreaterEqual(insights["score"]["value"], 0)
        self.assertLessEqual(insights["score"]["value"], 100)
        self.assertEqual(len(insights["recommendations"]), 3)
        self.assertGreaterEqual(insights["snapshot"]["months_sampled"], 1)
        self.assertGreater(insights["simulator"]["remaining_gap"], 0)

    def test_goal_simulator_marks_target_reached_when_gap_is_zero(self):
        self.user.settings.net_worth_target = Decimal("5000")
        self.user.settings.save()

        insights = SettingsService.get_phase3_insights(self.user)
        simulator = insights["simulator"]

        self.assertTrue(simulator["is_target_reached"])
        self.assertEqual(simulator["months_to_goal"], 0)

    def test_trailing_window_uses_nominal_one_year_when_data_is_older(self):
        old_date = date.today() - timedelta(days=420)
        income_subcategory = SubCategory.objects.get(
            user=self.user,
            parent_category__transaction_type="INCOME",
        )
        Transaction.objects.create(
            user=self.user,
            date=old_date,
            amount=Decimal("1000"),
            subcategory=income_subcategory,
        )

        insights = SettingsService.get_phase3_insights(self.user)

        self.assertEqual(
            insights["snapshot"]["window_start"],
            SettingsService._subtract_one_year(date.today()),
        )

    def test_trailing_window_uses_oldest_available_when_user_has_less_than_year(self):
        Transaction.objects.filter(user=self.user).delete()

        recent_date = date.today() - timedelta(days=40)
        income_subcategory = SubCategory.objects.get(
            user=self.user,
            parent_category__transaction_type="INCOME",
        )
        Transaction.objects.create(
            user=self.user,
            date=recent_date,
            amount=Decimal("2500"),
            subcategory=income_subcategory,
        )

        insights = SettingsService.get_phase3_insights(self.user)

        self.assertEqual(insights["snapshot"]["window_start"], recent_date)

    def test_financial_profile_changes_weighted_score_and_recommendations(self):
        self.user.settings.financial_profile = "SECURITY"
        self.user.settings.save()
        security = SettingsService.get_phase3_insights(self.user)

        self.user.settings.financial_profile = "GROWTH"
        self.user.settings.save()
        growth = SettingsService.get_phase3_insights(self.user)

        self.assertNotEqual(security["score"]["value"], growth["score"]["value"])
        self.assertGreaterEqual(
            security["recommendations"][2]["suggested_value"],
            growth["recommendations"][2]["suggested_value"],
        )


class SettingsHomeViewPhase3Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="viewer",
            password="test1234",
            email="viewer@example.com",
        )

    def test_settings_home_renders_phase3_modules(self):
        self.client.login(username="viewer", password="test1234")
        response = self.client.get(reverse("settings:settings_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Financial Health Score")
        self.assertContains(response, "Smart Recommendations")
        self.assertContains(response, "Goal Simulator")
