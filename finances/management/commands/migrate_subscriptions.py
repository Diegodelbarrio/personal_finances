import csv
import os
from datetime import date
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from finances.models import Category, SubCategory, Transaction

class Command(BaseCommand):
    help = 'Migra gastos de suscripciones desde un archivo CSV con delimitador ";" y decimales ","'

    def handle(self, *args, **options):
        User = get_user_model()
        user = User.objects.filter(is_superuser=True).first()
        
        if not user:
            self.stdout.write(self.style.ERROR('Error: No se encontró usuario admin.'))
            return

        # Mapeo según tus especificaciones
        mapping = {
            'adobe': 'Software & Media',
            'spotify': 'Software & Media',
            'chatgpt': 'Software & Media',
            'runna': 'Health & Fitness',
            'amazon premium': 'Software & Media',
            'icloud': 'Software & Media',
            'ing cuenta belga': 'Bank',
            'partenamut': 'Insurance',
            'inversión fondos': 'Other'
        }

        # Asegurar Categoría Principal
        main_cat, _ = Category.objects.get_or_create(
            user=user,
            name="Subscriptions",
            defaults={'transaction_type': 'EXPENSE', 'expense_type': 'FIXED'}
        )

        # Ruta al archivo CSV en la raíz del proyecto
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        file_path = os.path.join(base_dir, 'subscription_expenses_2025.csv')

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'CSV no encontrado en: {file_path}'))
            return

        try:
            # Abrimos especificando el delimitador punto y coma
            with open(file_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.reader(f, delimiter=';')
                count = 0
                
                for row in reader:
                    if not row or len(row) < 2:
                        continue
                    
                    raw_name = row[0].strip()
                    clean_name_key = raw_name.lower()
                    sub_name = mapping.get(clean_name_key, 'Other')
                    
                    # Asegurar Subcategoría
                    subcat, _ = SubCategory.objects.get_or_create(
                        user=user,
                        parent_category=main_cat,
                        name=sub_name
                    )

                    # Procesar meses (1 a 12)
                    monthly_values = row[1:13]
                    for month_idx, value_str in enumerate(monthly_values, start=1):
                        val = value_str.strip()
                        
                        if not val or val in ["0", "0,0", "0,00", ""]:
                            continue
                        
                        try:
                            # Reemplazamos coma por punto para que Decimal lo entienda
                            amount = Decimal(val.replace(',', '.'))
                            if amount <= 0:
                                continue

                            Transaction.objects.create(
                                user=user,
                                date=date(2025, month_idx, 1),
                                amount=amount,
                                description=f"Subscription: {raw_name}",
                                subcategory=subcat
                            )
                            count += 1
                        except (InvalidOperation, ValueError):
                            continue

            self.stdout.write(self.style.SUCCESS(f'Éxito: Se crearon {count} transacciones.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))