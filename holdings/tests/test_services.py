from django.test import TestCase
from django.contrib.auth.models import User
from datetime import date

from holdings.models import BankAccount, AccountBalanceSnapshot
from holdings.services.api import get_current_value


class HoldingsServiceTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="test", password="1234")

        account = BankAccount.objects.create(
            user=self.user,
            name="Cuenta Principal"
        )

        AccountBalanceSnapshot.objects.create(
            account=account,
            date=date(2024, 1, 31),
            balance=1000
        )

    def test_get_current_value(self):
        value, dates = get_current_value(self.user)

        self.assertEqual(value, 1000)
        self.assertEqual(len(dates), 1)
