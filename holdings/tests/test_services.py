from django.test import TestCase
from django.contrib.auth import get_user_model
from datetime import date

from holdings.models import BankAccount, AccountBalanceSnapshot
from holdings.services.api import get_current_value

User = get_user_model()


class HoldingsServiceTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="test", password="1234")

        account = BankAccount.objects.create(
            user=self.user,
            name="Cuenta Principal",
            institution="Test Bank",
            account_type="CHECKING",
        )

        AccountBalanceSnapshot.objects.create(
            user=self.user,
            account=account,
            date=date(2024, 1, 31),
            balance=1000,
        )

    def test_get_current_value(self):
        value, dates = get_current_value(self.user)

        self.assertEqual(value, 1000)
        self.assertEqual(len(dates), 1)
