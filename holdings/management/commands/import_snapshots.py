import csv
import os
from django.core.management.base import BaseCommand
from holdings.models import BankAccount, AccountBalanceSnapshot
from datetime import date
from decimal import Decimal

class Command(BaseCommand):
    help = 'Imports snapshots from accounts_snapshot.csv with detailed tracking'

    def handle(self, *args, **options):
        file_path = 'accounts_snapshot.csv'
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File not found at: {file_path}'))
            return

        # Configuration mapping
        account_config = {
            'ING Esp': ('ING Spain Corriente', 'ING Spain', 'CHECKING'),
            'ING Bel': ('ING Belgium', 'ING Belgium', 'CHECKING'),
            'Revolut Corriente': ('Revolut Corriente', 'Revolut', 'CHECKING'),
            'Revolut Ahorro': ('Revolut Savings', 'Revolut', 'SAVINGS'),
            'MyInvestor (Corriente)': ('MyInvestor Corriente', 'MyInvestor', 'CHECKING'),
            'Trade Republic (Corriente)': ('Trade Republic', 'Trade Republic', 'SAVINGS'), 
        }

        months_map = {
            'Enero': 1, 'Febrero': 2, 'Marzo': 3, 'Abril': 4, 'Mayo': 5, 'Junio': 6,
            'Julio': 7, 'Agosto': 8, 'Septiembre': 9, 'Octubre': 10, 'Noviembre': 11, 'Diciembre': 12
        }

        current_year = 2024
        processed_count = 0

        self.stdout.write(self.style.MIGRATE_LABEL(f"--- Starting import from {file_path} ---"))

        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.reader(f, delimiter=';')
            header = next(reader)
            
            for row in reader:
                if not row or not any(row):
                    continue
                
                # Check for year change rows (e.g., "2025;;;;;;")
                first_val = row[0].strip()
                if first_val in ['2024', '2025', '2026']:
                    current_year = int(first_val)
                    self.stdout.write(self.style.WARNING(f">> Switched to year: {current_year}"))
                    continue

                # Get month
                month_name = first_val
                if month_name not in months_map:
                    self.stdout.write(f"   Skipping row: {first_val} (not a valid month)")
                    continue
                
                month_num = months_map[month_name]
                snapshot_date = date(current_year, month_num, 28)
                
                self.stdout.write(f"Processing: {month_name} {current_year}...")

                csv_columns = {
                    'ING Esp': 1,
                    'ING Bel': 2,
                    'Revolut Corriente': 3,
                    'Revolut Ahorro': 4,
                    'MyInvestor (Corriente)': 5,
                    'Trade Republic (Corriente)': 6
                }

                for csv_key, col_idx in csv_columns.items():
                    db_name, institution, acc_type = account_config[csv_key]
                    
                    # Numeric cleaning
                    raw_val = row[col_idx].replace('.', '').replace(',', '.')
                    if raw_val == '-' or not raw_val:
                        balance = Decimal('0.00')
                    else:
                        try:
                            balance = Decimal(raw_val)
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"   Error parsing {raw_val} for {db_name}: {e}"))
                            balance = Decimal('0.00')

                    # Get or Create Account
                    account, created = BankAccount.objects.get_or_create(
                        name=db_name,
                        defaults={
                            'institution': institution,
                            'account_type': acc_type,
                            'currency': 'EUR'
                        }
                    )
                    if created:
                        self.stdout.write(self.style.SUCCESS(f"   Created new account: {db_name}"))

                    # Create or Update Snapshot
                    obj, created_snap = AccountBalanceSnapshot.objects.update_or_create(
                        account=account,
                        date=snapshot_date,
                        defaults={
                            'balance': balance,
                            'interest_earned': Decimal('0.00')
                        }
                    )
                    
                    action = "Imported" if created_snap else "Updated"
                    # Opcional: print detallado por cada cuenta (puede generar mucho texto)
                    # self.stdout.write(f"      {action} {db_name}: {balance}€")

                processed_count += 1

        self.stdout.write(self.style.SUCCESS(f"--- Finished! Processed {processed_count} months of data ---"))