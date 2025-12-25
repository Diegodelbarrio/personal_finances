import csv
import os
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

# Django imports
from django.core.management.base import BaseCommand
from investments.models import Asset, Transaction

class Command(BaseCommand):
    help = 'Importa transacciones de inversión desde un archivo CSV'

    def add_arguments(self, parser):
        # Permitimos pasar la ruta del archivo como argumento opcional
        parser.add_argument(
            '--file', 
            type=str, 
            help='Ruta al archivo CSV', 
            default='migracion_inversiones.csv'
        )

    def handle(self, *args, **options):
        file_path = options['file']

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"Archivo no encontrado: {file_path}"))
            return

        # Mapeo de activos (lo mantenemos igual)
        ASSET_MAPPING = {
            'Vanguard Emerging Markets Stock Index Fund EUR Acc': {'name': 'Vanguard Emerging Markets', 'cat': 'INDEX_FUND'},
            'Physical Gold USD (Acc)': {'name': 'Physical Gold USD', 'cat': 'COMMODITY'},
            'Fidelity MSCI World Index Fund P-ACC-EUR': {'name': 'Fidelity MSCI World Index', 'cat': 'INDEX_FUND'},
            'Bitcoin (BTC)': {'name': 'Bitcoin', 'cat': 'CRYPTO'}
        }

        imported = 0
        skipped_duplicates = 0
        skipped_invalid_date = 0

        with open(file_path, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            # Limpiar espacios en los nombres de las columnas
            reader.fieldnames = [h.strip() for h in reader.fieldnames]

            for row in reader:
                line_num = reader.line_num

                if self.is_empty_row(row):
                    self.stdout.write(f"Fin de datos detectado en la fila {line_num}")
                    break

                # ---- Fecha ----
                tx_date = self.excel_date_to_python(row.get('Fecha'))
                if tx_date is None:
                    skipped_invalid_date += 1
                    continue

                # ---- Activo ----
                orig_name = row['Nombre Fondo/Activo'].strip()
                info = ASSET_MAPPING.get(orig_name, {'name': orig_name, 'cat': 'INDEX_FUND'})

                asset, _ = Asset.objects.get_or_create(
                    name=info['name'],
                    defaults={
                        'category': info['cat'],
                        'platform': row['Entidad'].strip(),
                        'isin': row['ISIN'].strip()
                    }
                )

                # ---- Datos de transacción ----
                action = row['Compra/Venta'].strip().upper()
                shares = self.clean_decimal(row['Participaciones'])
                amount = self.clean_decimal(row['Cantidad'])
                price = self.clean_decimal(row['Valor liquidativo'])
                notes = str(row['Comentarios']).strip() if row['Comentarios'] else ''

                # ---- Anti-duplicados ----
                exists = Transaction.objects.filter(
                    asset=asset,
                    date=tx_date,
                    action=action,
                    shares=shares,
                    amount=amount
                ).exists()

                if exists:
                    skipped_duplicates += 1
                    continue

                Transaction.objects.create(
                    asset=asset,
                    date=tx_date,
                    action=action,
                    shares=shares,
                    price_per_share=price,
                    amount=amount,
                    notes=notes
                )
                imported += 1

        # ---- Informe Final ----
        self.stdout.write("\n" + self.style.SUCCESS("========== INFORME DE IMPORTACIÓN =========="))
        self.stdout.write(f"✔ Transacciones importadas: {imported}")
        self.stdout.write(self.style.WARNING(f"⏭ Duplicados omitidos: {skipped_duplicates}"))
        self.stdout.write(self.style.WARNING(f"⚠ Fechas inválidas omitidas: {skipped_invalid_date}"))
        self.stdout.write(self.style.SUCCESS("============================================"))

    # --- Métodos auxiliares ahora dentro de la clase ---
    def excel_date_to_python(self, serial):
        if serial is None or str(serial).strip() == '':
            return None
        try:
            return date(1899, 12, 30) + timedelta(days=int(float(serial)))
        except (TypeError, ValueError):
            return None

    def clean_decimal(self, value):
        if value is None or str(value).strip() == '':
            return Decimal('0')
        try:
            return Decimal(str(value).replace(',', '.'))
        except InvalidOperation:
            return Decimal('0')

    def is_empty_row(self, row):
        return all(value is None or str(value).strip() == '' for value in row.values())