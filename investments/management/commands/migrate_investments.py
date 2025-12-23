import csv
import os
from django.core.management.base import BaseCommand
from investments.models import Asset, AssetHistory
from datetime import date
from decimal import Decimal

class Command(BaseCommand):
    help = 'Migrates investment history from migrate_investments.csv to existing Assets'

    def handle(self, *args, **options):
        file_path = 'migrate_investments.csv'
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File not found at: {file_path}'))
            return

        # Mapeo exacto basado en tus nombres de base de datos
        # Índice columna CSV : Nombre exacto en DB
        asset_mapping = {
            1: "Fidelity MSCI World Index",
            2: "Vanguard Emerging Markets",
            3: "Physical Gold USD",
            4: "Bitcoin"
        }

        months_map = {
            'Enero': 1, 'Febrero': 2, 'Marzo': 3, 'Abril': 4, 'Mayo': 5, 'Junio': 6,
            'Julio': 7, 'Agosto': 8, 'Septiembre': 9, 'Octubre': 10, 'Noviembre': 11, 'Diciembre': 12
        }

        current_year = 2025 
        processed_count = 0

        self.stdout.write(self.style.MIGRATE_LABEL(f"--- Iniciando migración de Inversiones ---"))

        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.reader(f, delimiter=';')
            next(reader) # Saltar cabecera
            
            for row in reader:
                if not row or not any(row): continue
                
                # Gestión de año
                first_val = row[0].strip()
                if first_val in ['2024', '2025', '2026']:
                    current_year = int(first_val)
                    self.stdout.write(self.style.WARNING(f">> Año detectado: {current_year}"))
                    continue

                if first_val not in months_map:
                    continue
                
                month_num = months_map[first_val]
                # Usamos el día 28 para que coincida con la lógica de los bancos (mismo mes)
                snapshot_date = date(current_year, month_num, 28)

                for col_idx, asset_name in asset_mapping.items():
                    # Limpieza de valor numérico del CSV
                    raw_val = row[col_idx].replace('.', '').replace(',', '.')
                    try:
                        value = Decimal(raw_val) if raw_val and raw_val != '-' else Decimal('0.00')
                    except:
                        value = Decimal('0.00')

                    # 1. Obtener el Activo (debe existir previamente)
                    try:
                        asset = Asset.objects.get(name=asset_name)
                    except Asset.DoesNotExist:
                        # Si no existe, lo creamos para evitar que el script falle
                        asset = Asset.objects.create(name=asset_name, asset_type='OTHERS')
                        self.stdout.write(self.style.SUCCESS(f"   [NUEVO] Activo creado: {asset_name}"))

                    # 2. Registrar en el historial
                    # Usamos update_or_create para que si lo vuelves a lanzar solo actualice datos
                    history, created = AssetHistory.objects.update_or_create(
                        asset=asset,
                        date=snapshot_date,
                        defaults={'total_value': value}
                    )
                    
                self.stdout.write(f"   Procesado: {first_val} {current_year}")
                processed_count += 1

        self.stdout.write(self.style.SUCCESS(f"--- Migración finalizada: {processed_count} meses registrados ---"))