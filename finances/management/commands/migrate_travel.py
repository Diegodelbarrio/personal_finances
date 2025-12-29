import csv
import os
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils.timezone import datetime
from django.contrib.auth import get_user_model
from finances.models import Transaction, Category, SubCategory, Location

User = get_user_model()

# ==============================================================
# CONFIGURACIÓN DEL VIAJE (Modifica estos valores)
# ==============================================================
CONFIG = {
    'csv_path': 'scripts/data_imports/viaje_bcn.csv',  # Nombre o ruta del archivo
    'trip_name': 'Barcelona',        # Nombre de la localización
    'date': '2025-02-15',               # Fecha (Año-Mes-Día)
    'username': 'diegodelbarrio',                # Tu usuario de Django
}
# ==============================================================

class Command(BaseCommand):
    help = 'Import transactions from a trip by editing the CONFIG dictionary.'

    def handle(self, *args, **options):
        csv_path = CONFIG['csv_path']
        trip_name = CONFIG['trip_name']
        date_str = CONFIG['date']
        username = CONFIG['username']
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Error: Usuario '{username}' no encontrado."))
            return

        # 1. User-linked location
        location, _ = Location.objects.get_or_create(user=user, name=trip_name)

        # 2. Obtain necessary subcategories
        try:
            sub_travel = SubCategory.objects.get(
                user=user, 
                name="Travel", 
                parent_category__name="Leisure"
            )
            sub_bizum = SubCategory.objects.get(
                user=user, 
                name="Bizum", 
                parent_category__name="Income"
            )
        except SubCategory.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"Error: The user {username} does not have subcategories "
                f"'Travel' (Leisure) o 'Bizum' (Income) creadas."
            ))
            return

        # 3. Process the file
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.ERROR(f"File not found in: {os.path.abspath(csv_path)}"))
            return

        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';')
            
            count = 0
            for row in reader:
                if not row or len(row) < 2:
                    continue
                
                desc = row[0]
                raw_amount_str = row[1].replace(',', '.')
                raw_amount = Decimal(raw_amount_str)

                if raw_amount < 0:
                    current_sub = sub_bizum
                else:
                    current_sub = sub_travel

                Transaction.objects.create(
                    user=user,
                    date=datetime.strptime(date_str, '%Y-%m-%d').date(),
                    description=f"[{trip_name}] {desc}",
                    amount=abs(raw_amount),
                    subcategory=current_sub,
                    location=location
                )
                count += 1

        self.stdout.write(self.style.SUCCESS(
            f"✅ Success: Imported {count} transactions of'{trip_name}'."
        ))