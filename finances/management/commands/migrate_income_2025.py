import csv
import os
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from finances.models import Category, SubCategory, Transaction

class Command(BaseCommand):
    help = 'Migra todos los ingresos de 2025 (Salary y Edenred)'

    def handle(self, *args, **options):
        User = get_user_model()
        user = User.objects.filter(is_superuser=True).first()
        
        if not user:
            self.stdout.write(self.style.ERROR('Error: Usuario admin no encontrado.'))
            return

        months_en = {
            1: "January", 2: "February", 3: "March", 4: "April", 
            5: "May", 6: "June", 7: "July", 8: "August", 
            9: "September", 10: "October", 11: "November", 12: "December"
        }

        income_cat, _ = Category.objects.get_or_create(
            user=user,
            name="Income",
            defaults={'transaction_type': 'INCOME', 'expense_type': 'N/A'}
        )

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        file_path = os.path.join(base_dir, 'income_2025.csv')

        try:
            with open(file_path, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=';')
                created_count = 0
                
                for row in reader:
                    if not row or len(row) < 2: continue
                    
                    raw_name = row[0].strip().lower()
                    
                    # Identificación flexible de la fila
                    if 'salario' in raw_name:
                        sub_name = 'Salary'
                        display_name = 'Salary Deloitte'
                    elif 'tarjeta' in raw_name or 'edenred' in raw_name:
                        sub_name = 'Edenred Card'
                        display_name = 'Edenred Card'
                    else:
                        continue # Ignorar filas que no coincidan
                    
                    subcat, _ = SubCategory.objects.get_or_create(
                        user=user,
                        parent_category=income_cat,
                        name=sub_name
                    )

                    monthly_values = row[1:13]
                    for month_idx, value_str in enumerate(monthly_values, start=1):
                        val = value_str.strip()
                        if not val or val in ["0", "0,0", "0.0", ""]: continue
                        
                        try:
                            # Reemplazo de coma por punto y conversión
                            clean_val = val.replace(',', '.')
                            amount = Decimal(str(float(clean_val))).quantize(
                                Decimal('0.00'), rounding=ROUND_HALF_UP
                            )
                            
                            month_name = months_en[month_idx]
                            desc = f"{display_name}: {month_name}" if sub_name == 'Salary' else f"{display_name} {month_name}"

                            Transaction.objects.create(
                                user=user,
                                date=date(2025, month_idx, 25),
                                amount=amount,
                                description=desc,
                                subcategory=subcat
                            )
                            created_count += 1
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(f"Error en {raw_name} mes {month_idx}: {e}"))

            self.stdout.write(self.style.SUCCESS(f'Éxito: Se han migrado {created_count} registros de ingresos.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error crítico: {str(e)}'))