import csv
import os
from datetime import date
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from finances.models import Category, SubCategory, Transaction

class Command(BaseCommand):
    help = 'Migra gastos de transporte, comida y housing desde expenses_2025.csv'

    def handle(self, *args, **options):
        User = get_user_model()
        user = User.objects.filter(is_superuser=True).first()
        
        if not user:
            self.stdout.write(self.style.ERROR('Error: No se encontró usuario admin.'))
            return

        # Definición de mapeo: Nombre en CSV -> (Categoría, Subcategoría)
        mapping = {
            # Food & Dinning
            'deloitte': ('Food & Dinning', 'Work'),
            'prozis': ('Food & Dinning', 'Groceries'),
            'delhaize': ('Food & Dinning', 'Groceries'),
            'edenred': ('Food & Dinning', 'Market'),
            'mercado': ('Food & Dinning', 'Market'),
            
            # Transportation
            'ticket stib': ('Transportation', 'Public Transport'),
            'uber': ('Transportation', 'Taxi'),
            'patinete/bici': ('Transportation', 'Public Transport'),
            'tren': ('Transportation', 'Train'),
            
            # Housing
            'alquiler piso': ('Housing', 'Rent'),
            'gastos a leit': ('Housing', 'Utilities'),
            'wifi': ('Housing', 'Telecom'),
        }

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        file_path = os.path.join(base_dir, 'expenses_2025.csv')

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'Archivo no encontrado en: {file_path}'))
            return

        try:
            with open(file_path, mode='r', encoding='utf-8-sig') as f:
                # El archivo usa punto y coma como delimitador
                reader = csv.reader(f, delimiter=';')
                created_count = 0
                
                for row in reader:
                    if not row:
                        continue
                    
                    raw_item_name = row[0].strip()
                    item_key = raw_item_name.lower()

                    # Si el nombre no está en nuestro mapeo, saltamos la fila (como las cabeceras "Comida", etc.)
                    if item_key not in mapping:
                        continue
                    
                    cat_name, sub_name = mapping[item_key]

                    # 1. Asegurar Categoría
                    category, _ = Category.objects.get_or_create(
                        user=user,
                        name=cat_name,
                        defaults={'transaction_type': 'EXPENSE', 'expense_type': 'VARIABLE'}
                    )
                    # Forzar tipo fijo para Housing
                    if cat_name == 'Housing':
                        category.expense_type = 'FIXED'
                        category.save()

                    # 2. Asegurar Subcategoría
                    subcat, _ = SubCategory.objects.get_or_create(
                        user=user,
                        parent_category=category,
                        name=sub_name
                    )

                    # 3. Procesar meses (columnas 1 a 12)
                    monthly_values = row[1:13]
                    for month_idx, value_str in enumerate(monthly_values, start=1):
                        val = value_str.strip()
                        
                        # Saltamos celdas vacías o con puntos suspensivos
                        if not val or val in ["0", "0,0", "0,00", "", "..."]:
                            continue
                        
                        try:
                            # Limpiar y convertir a Decimal
                            amount = Decimal(val.replace(',', '.'))
                            
                            # Usamos el valor absoluto porque el modelo ya se encarga del signo
                            amount = abs(amount)
                            
                            if amount == 0:
                                continue

                            Transaction.objects.create(
                                user=user,
                                date=date(2025, month_idx, 2),
                                amount=amount,
                                description=raw_item_name,
                                subcategory=subcat
                            )
                            created_count += 1
                        except (InvalidOperation, ValueError):
                            continue

            self.stdout.write(self.style.SUCCESS(f'Éxito: Se crearon {created_count} transacciones de Gastos Variados.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))