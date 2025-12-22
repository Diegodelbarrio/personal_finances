import csv
import os
import django
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

# --------------------------------------------------
# Django setup
# --------------------------------------------------
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from investments.models import Asset, Transaction


# --------------------------------------------------
# Helpers
# --------------------------------------------------
def excel_date_to_python(serial):
    """Convert Excel serial date to Python date."""
    if serial is None or str(serial).strip() == '':
        return None
    try:
        return date(1899, 12, 30) + timedelta(days=int(float(serial)))
    except (TypeError, ValueError):
        return None


def clean_decimal(value):
    """Convert European decimal format to Decimal."""
    if value is None or str(value).strip() == '':
        return Decimal('0')
    try:
        return Decimal(str(value).replace(',', '.'))
    except InvalidOperation:
        return Decimal('0')


def is_empty_row(row):
    """Detect end-of-data rows exported by Excel."""
    return all(
        value is None or str(value).strip() == ''
        for value in row.values()
    )


# --------------------------------------------------
# Asset mapping
# --------------------------------------------------
ASSET_MAPPING = {
    'Vanguard Emerging Markets Stock Index Fund EUR Acc': {
        'name': 'Vanguard Emerging Markets',
        'cat': 'INDEX_FUND'
    },
    'Physical Gold USD (Acc)': {
        'name': 'Physical Gold USD',
        'cat': 'COMMODITY'
    },
    'Fidelity MSCI World Index Fund P-ACC-EUR': {
        'name': 'Fidelity MSCI World Index',
        'cat': 'INDEX_FUND'
    },
    'Bitcoin (BTC)': {
        'name': 'Bitcoin',
        'cat': 'CRYPTO'
    }
}


# --------------------------------------------------
# Main import logic
# --------------------------------------------------
def run():
    file_path = 'migracion_inversiones.csv'

    if not os.path.exists(file_path):
        print("File not found: migracion_inversiones.csv")
        return

    imported = 0
    skipped_duplicates = 0
    skipped_invalid_date = 0

    with open(file_path, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        reader.fieldnames = [h.strip() for h in reader.fieldnames]

        for row in reader:
            line_num = reader.line_num

            # ---- End-of-data detection ----
            if is_empty_row(row):
                print(f"End of data detected at row {line_num}")
                break

            # ---- Date ----
            tx_date = excel_date_to_python(row.get('Fecha'))
            if tx_date is None:
                skipped_invalid_date += 1
                continue

            # ---- Asset ----
            orig_name = row['Nombre Fondo/Activo'].strip()
            info = ASSET_MAPPING.get(
                orig_name,
                {'name': orig_name, 'cat': 'INDEX_FUND'}
            )

            asset, _ = Asset.objects.get_or_create(
                name=info['name'],
                defaults={
                    'category': info['cat'],
                    'platform': row['Entidad'].strip(),
                    'isin': row['ISIN'].strip()
                }
            )

            # ---- Transaction data ----
            action = row['Compra/Venta'].strip().upper()
            shares = clean_decimal(row['Participaciones'])
            amount = clean_decimal(row['Cantidad'])
            price = clean_decimal(row['Valor liquidativo'])
            notes = '' if row['Comentarios'] is None else str(row['Comentarios']).strip()

            # ---- Anti-duplicates ----
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

    # --------------------------------------------------
    # Final report
    # --------------------------------------------------
    print("\n========== IMPORT REPORT ==========")
    print(f"✔ Transactions imported: {imported}")
    print(f"⏭ Skipped duplicates: {skipped_duplicates}")
    print(f"⚠ Skipped invalid dates: {skipped_invalid_date}")
    print("===================================")


# --------------------------------------------------
# Entrypoint
# --------------------------------------------------
if __name__ == '__main__':
    run()
