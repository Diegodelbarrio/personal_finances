from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date
from decimal import Decimal

from ..models import Transaction, Category, SubCategory
from ..services import queries, metrics

class FinancesServicesTest(TestCase):

    def setUp(self):
        # 1. Configuración de Usuario
        self.user = User.objects.create_user(username="testuser", password="password123")
        
        # 2. Configuración de Categorías
        self.cat_income = Category.objects.create(
            name="Salary", 
            transaction_type='INCOME'
        )
        self.cat_expense_fixed = Category.objects.create(
            name="Rent", 
            transaction_type='EXPENSE', 
            expense_type='FIXED',
            is_housing=True
        )
        self.cat_expense_var = Category.objects.create(
            name="Groceries", 
            transaction_type='EXPENSE', 
            expense_type='VARIABLE',
            is_housing=False
        )

        # 3. Subcategorías
        self.sub_salary = SubCategory.objects.create(name="Main Job", parent_category=self.cat_income)
        self.sub_rent = SubCategory.objects.create(name="Apartment", parent_category=self.cat_expense_fixed)
        self.sub_food = SubCategory.objects.create(name="Supermarket", parent_category=self.cat_expense_var)

    def test_queries_isolation(self):
        """Verifica que un usuario no puede acceder a transacciones de otros"""
        other_user = User.objects.create_user(username="other", password="123")
        Transaction.objects.create(
            user=self.user, amount=100, SubCategory=self.sub_salary, date=date(2024, 1, 1)
        )
        
        user_qs = queries.get_base_transaction_qs(self.user)
        other_qs = queries.get_base_transaction_qs(other_user)
        
        self.assertEqual(user_qs.count(), 1)
        self.assertEqual(other_qs.count(), 0)

    def test_metrics_calculation(self):
        """Valida que los cálculos de KPIs sean correctos y manejen valores absolutos"""
        # Datos del periodo: Enero 2024
        Transaction.objects.create(user=self.user, amount=5000, SubCategory=self.sub_salary, date=date(2024, 1, 1)) # Ingreso
        Transaction.objects.create(user=self.user, amount=-1500, SubCategory=self.sub_rent, date=date(2024, 1, 5)) # Gasto Fijo
        Transaction.objects.create(user=self.user, amount=-500, SubCategory=self.sub_food, date=date(2024, 1, 10)) # Gasto Variable

        qs = Transaction.objects.filter(user=self.user, date__year=2024, date__month=1)
        stats = metrics.get_period_metrics(qs)

        self.assertEqual(stats['income'], 5000)
        self.assertEqual(stats['expenses'], 2000)  # |-1500| + |-500|
        self.assertEqual(stats['savings'], 3000)   # 5000 - 2000
        self.assertEqual(stats['fixed'], 1500)
        self.assertEqual(stats['variable'], 500)
        self.assertEqual(stats['no_housing'], 500) # El alquiler (housing) se excluye
        self.assertFalse(stats['is_incomplete'])

    def test_previous_month_income_logic(self):
        """Valida que el cálculo de ingresos del mes anterior funcione entre años (Enero -> Diciembre)"""
        # Ingreso en Diciembre 2023
        Transaction.objects.create(
            user=self.user, amount=4000, SubCategory=self.sub_salary, date=date(2023, 12, 15)
        )
        # Ingreso en Enero 2024
        Transaction.objects.create(
            user=self.user, amount=4500, SubCategory=self.sub_salary, date=date(2024, 1, 15)
        )

        base_qs = queries.get_base_transaction_qs(self.user)
        
        # Si consultamos Enero 2024, el prev_income debe ser el de Diciembre 2023
        prev_inc = metrics.get_previous_month_income(base_qs, 2024, 1)
        self.assertEqual(prev_inc, 4000)

    def test_metrics_empty_data(self):
        """Verifica que el sistema no rompa si no hay datos en un mes"""
        qs = Transaction.objects.filter(user=self.user, date__year=2020) # Mes sin datos
        stats = metrics.get_period_metrics(qs)
        
        self.assertEqual(stats['income'], 0)
        self.assertEqual(stats['expenses'], 0)
        self.assertEqual(stats['savings'], 0)
        # El flag is_incomplete debería ser False porque no hay ahorros negativos
        self.assertFalse(stats['is_incomplete'])

    def test_expense_distribution_chart(self):
        """Valida el formato de los datos para los gráficos"""
        Transaction.objects.create(user=self.user, amount=-1000, SubCategory=self.sub_rent, date=date(2024, 1, 1))
        Transaction.objects.create(user=self.user, amount=-200, SubCategory=self.sub_food, date=date(2024, 1, 2))

        qs = Transaction.objects.filter(user=self.user, date__year=2024)
        chart_data = metrics.get_expense_distribution_chart(qs)

        # Verificar que los labels existen y los datos son floats positivos
        self.assertIn("Rent", chart_data['labels'])
        self.assertIn("Groceries", chart_data['labels'])
        self.assertEqual(chart_data['data'][0], 1000.0)