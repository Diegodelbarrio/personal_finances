import csv
import io
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction as db_transaction

from finances.models import Location, SubCategory, Transaction as FinanceTransaction
from holdings.models import AccountBalanceSnapshot, BankAccount
from investments.models import (
    Asset,
    AssetHistory,
    Transaction as InvestmentTransaction,
)

FINANCE_TRANSACTIONS_CSV_FORMAT = {
    "required_columns": ["date", "amount", "category", "subcategory"],
    "optional_columns": ["description", "location"],
    "sample_csv": (
        "date,amount,category,subcategory,description,location\n"
        "2026-02-10,45.90,Food,Groceries,Weekly groceries,Madrid\n"
        "2026-02-12,23.50,Transport,Public Transport,Metro card recharge,Madrid\n"
        "2026-02-15,2100.00,Salary,Main Job,February payroll,\n"
        "2026-02-18,12.80,Leisure,Coffee,Coffee with friend,Barcelona\n"
        "2026-02-21,79.99,Utilities,Internet,Monthly internet bill,Home"
    ),
    "columns_help": [
        ("date", "Yes", "Format: YYYY-MM-DD."),
        ("amount", "Yes", "Positive number. The system applies sign by category type."),
        ("category", "Yes", "Existing category name (user-owned)."),
        ("subcategory", "Yes", "Existing subcategory name under the category."),
        ("description", "No", "Transaction description."),
        ("location", "No", "Existing location name (user-owned)."),
    ],
}

INVESTMENT_TRANSACTIONS_CSV_FORMAT = {
    "required_columns": ["date", "asset", "action", "amount"],
    "optional_columns": ["shares", "price_per_share", "notes"],
    "sample_csv": (
        "date,asset,action,amount,shares,price_per_share,notes\n"
        "2026-02-14,MSCI World,BUY,250.00,2.5,100.00,Monthly buy\n"
        "2026-02-20,Bitcoin,BUY,150.00,0.0025,60000.00,Weekly DCA\n"
        "2026-02-24,MSCI World,BUY,300.00,3.0,100.00,Bonus contribution\n"
        "2026-02-26,Physical Gold,SELL,80.00,0.4,200.00,Partial rebalance\n"
        "2026-02-28,Vanguard EM,BUY,200.00,1.6,125.00,Month-end buy"
    ),
    "columns_help": [
        ("date", "Yes", "Format: YYYY-MM-DD."),
        ("asset", "Yes", "Existing asset name (user-owned)."),
        ("action", "Yes", "BUY or SELL."),
        ("amount", "Yes", "Positive number. SELL is stored as negative."),
        ("shares", "No", "Positive number."),
        ("price_per_share", "No", "Positive number."),
        ("notes", "No", "Comments."),
    ],
}

INVESTMENT_HISTORY_CSV_FORMAT = {
    "required_columns": ["date", "asset", "total_value"],
    "optional_columns": [],
    "sample_csv": (
        "date,asset,total_value\n"
        "2026-02-28,MSCI World,15420.35\n"
        "2026-02-28,Bitcoin,8920.10\n"
        "2026-02-28,Physical Gold,3400.50\n"
        "2026-02-28,Vanguard EM,6120.00\n"
        "2026-02-28,REIT Global,2750.40"
    ),
    "columns_help": [
        ("date", "Yes", "Format: YYYY-MM-DD."),
        ("asset", "Yes", "Existing asset name (user-owned)."),
        ("total_value", "Yes", "Snapshot market value (0 or higher)."),
    ],
}

HOLDING_SNAPSHOTS_CSV_FORMAT = {
    "required_columns": ["date", "account_name", "institution", "account_type", "balance"],
    "optional_columns": ["currency", "interest_earned"],
    "sample_csv": (
        "date,account_name,institution,account_type,currency,balance,interest_earned\n"
        "2026-02-28,Main Checking,ING,CHECKING,EUR,3050.75,2.20\n"
        "2026-02-28,Emergency Fund,MyInvestor,SAVINGS,EUR,8200.00,12.10\n"
        "2026-02-28,Daily Card,Revolut,CHECKING,EUR,640.32,0\n"
        "2026-02-28,Cash Wallet,Cash,CASH,EUR,180.00,0\n"
        "2026-02-28,Student Loan,Bank Loan,DEBT,EUR,-5200.00,0"
    ),
    "columns_help": [
        ("date", "Yes", "Format: YYYY-MM-DD."),
        ("account_name", "Yes", "Bank account display name."),
        ("institution", "Yes", "Bank or platform."),
        ("account_type", "Yes", "CHECKING, SAVINGS, CASH or DEBT."),
        ("currency", "No", "3-letter code. Default: EUR."),
        ("balance", "Yes", "Snapshot balance."),
        ("interest_earned", "No", "Monthly interest amount. Default: 0."),
    ],
}


@dataclass
class CSVImportResult:
    success: bool
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    details: dict[str, int] = field(default_factory=dict)


CSV_TEMPLATE_DEFINITIONS = {
    "finance-transactions": {
        "filename": "finance_transactions_template.csv",
        "sample_csv": FINANCE_TRANSACTIONS_CSV_FORMAT["sample_csv"],
    },
    "investment-transactions": {
        "filename": "investment_transactions_template.csv",
        "sample_csv": INVESTMENT_TRANSACTIONS_CSV_FORMAT["sample_csv"],
    },
    "investment-history": {
        "filename": "investment_history_template.csv",
        "sample_csv": INVESTMENT_HISTORY_CSV_FORMAT["sample_csv"],
    },
    "holding-snapshots": {
        "filename": "holding_snapshots_template.csv",
        "sample_csv": HOLDING_SNAPSHOTS_CSV_FORMAT["sample_csv"],
    },
}


def get_csv_template_payload(template_key):
    template = CSV_TEMPLATE_DEFINITIONS.get(template_key)
    if not template:
        return None

    sample_csv = template["sample_csv"]
    if not sample_csv.endswith("\n"):
        sample_csv = f"{sample_csv}\n"

    return {
        "filename": template["filename"],
        "content": sample_csv,
    }


def import_finance_transactions_csv(user, uploaded_file):
    rows, errors = _read_csv_rows(
        uploaded_file,
        required_columns=FINANCE_TRANSACTIONS_CSV_FORMAT["required_columns"],
        optional_columns=FINANCE_TRANSACTIONS_CSV_FORMAT["optional_columns"],
    )
    if errors:
        return CSVImportResult(success=False, errors=errors)

    subcategory_index = defaultdict(list)
    for subcategory in SubCategory.objects.filter(user=user).select_related("parent_category"):
        key = (
            subcategory.parent_category.name.casefold(),
            subcategory.name.casefold(),
        )
        subcategory_index[key].append(subcategory)

    location_index = defaultdict(list)
    for location in Location.objects.filter(user=user):
        location_index[location.name.casefold()].append(location)

    parsed_rows = []
    row_errors = []
    row_keys = set()

    for row_number, row in rows:
        category_name = row.get("category", "").strip()
        subcategory_name = row.get("subcategory", "").strip()
        description = row.get("description", "").strip()
        location_name = row.get("location", "").strip()

        parsed_date = _parse_date(row.get("date"), row_number, "date", row_errors)
        amount_value = _parse_decimal(
            row.get("amount"),
            row_number,
            "amount",
            row_errors,
            allow_zero=False,
        )
        if not category_name:
            row_errors.append(_row_error(row_number, "category is required."))
        if not subcategory_name:
            row_errors.append(_row_error(row_number, "subcategory is required."))
        if parsed_date is None or amount_value is None or not category_name or not subcategory_name:
            continue

        subcategory_candidates = subcategory_index.get(
            (category_name.casefold(), subcategory_name.casefold()),
            [],
        )
        if not subcategory_candidates:
            row_errors.append(
                _row_error(
                    row_number,
                    f"subcategory '{subcategory_name}' under category '{category_name}' was not found.",
                )
            )
            continue
        if len(subcategory_candidates) > 1:
            row_errors.append(
                _row_error(
                    row_number,
                    f"subcategory '{subcategory_name}' under category '{category_name}' is ambiguous.",
                )
            )
            continue
        subcategory = subcategory_candidates[0]

        location = None
        if location_name:
            location_candidates = location_index.get(location_name.casefold(), [])
            if not location_candidates:
                row_errors.append(
                    _row_error(row_number, f"location '{location_name}' was not found.")
                )
                continue
            if len(location_candidates) > 1:
                row_errors.append(
                    _row_error(row_number, f"location '{location_name}' is ambiguous.")
                )
                continue
            location = location_candidates[0]

        signed_amount = (
            -abs(amount_value)
            if subcategory.parent_category.transaction_type == "EXPENSE"
            else abs(amount_value)
        )
        row_key = (
            parsed_date,
            signed_amount,
            subcategory.id,
            location.id if location else None,
            description,
        )
        if row_key in row_keys:
            row_errors.append(_row_error(row_number, "duplicate transaction in CSV file."))
            continue
        row_keys.add(row_key)

        parsed_rows.append(
            {
                "date": parsed_date,
                "amount": signed_amount,
                "description": description,
                "subcategory": subcategory,
                "location": location,
            }
        )

    if row_errors:
        return CSVImportResult(success=False, errors=row_errors)

    created = 0
    skipped = 0
    with db_transaction.atomic():
        for item in parsed_rows:
            _, was_created = FinanceTransaction.objects.get_or_create(
                user=user,
                date=item["date"],
                amount=item["amount"],
                description=item["description"],
                subcategory=item["subcategory"],
                location=item["location"],
            )
            if was_created:
                created += 1
            else:
                skipped += 1

    return CSVImportResult(success=True, created=created, skipped=skipped)


def import_investment_transactions_csv(user, uploaded_file):
    rows, errors = _read_csv_rows(
        uploaded_file,
        required_columns=INVESTMENT_TRANSACTIONS_CSV_FORMAT["required_columns"],
        optional_columns=INVESTMENT_TRANSACTIONS_CSV_FORMAT["optional_columns"],
    )
    if errors:
        return CSVImportResult(success=False, errors=errors)

    asset_index = defaultdict(list)
    for asset in Asset.objects.filter(user=user):
        asset_index[asset.name.casefold()].append(asset)

    parsed_rows = []
    row_errors = []
    row_keys = set()

    for row_number, row in rows:
        asset_name = row.get("asset", "").strip()
        action = row.get("action", "").strip().upper()
        notes = row.get("notes", "").strip()

        parsed_date = _parse_date(row.get("date"), row_number, "date", row_errors)
        amount_value = _parse_decimal(
            row.get("amount"),
            row_number,
            "amount",
            row_errors,
            allow_zero=False,
        )
        shares_value = _parse_decimal(
            row.get("shares"),
            row_number,
            "shares",
            row_errors,
            required=False,
            allow_zero=False,
        )
        price_value = _parse_decimal(
            row.get("price_per_share"),
            row_number,
            "price_per_share",
            row_errors,
            required=False,
            allow_zero=False,
        )

        if not asset_name:
            row_errors.append(_row_error(row_number, "asset is required."))
        if action not in {"BUY", "SELL"}:
            row_errors.append(_row_error(row_number, "action must be BUY or SELL."))
        if parsed_date is None or amount_value is None or not asset_name or action not in {"BUY", "SELL"}:
            continue

        asset_candidates = asset_index.get(asset_name.casefold(), [])
        if not asset_candidates:
            row_errors.append(_row_error(row_number, f"asset '{asset_name}' was not found."))
            continue
        if len(asset_candidates) > 1:
            row_errors.append(_row_error(row_number, f"asset '{asset_name}' is ambiguous."))
            continue
        asset = asset_candidates[0]

        signed_amount = -abs(amount_value) if action == "SELL" else abs(amount_value)
        row_key = (
            parsed_date,
            asset.id,
            action,
            shares_value,
            price_value,
            signed_amount,
            notes,
        )
        if row_key in row_keys:
            row_errors.append(_row_error(row_number, "duplicate transaction in CSV file."))
            continue
        row_keys.add(row_key)

        parsed_rows.append(
            {
                "asset": asset,
                "date": parsed_date,
                "action": action,
                "shares": shares_value,
                "price_per_share": price_value,
                "amount": signed_amount,
                "notes": notes,
            }
        )

    if row_errors:
        return CSVImportResult(success=False, errors=row_errors)

    created = 0
    skipped = 0
    with db_transaction.atomic():
        for item in parsed_rows:
            _, was_created = InvestmentTransaction.objects.get_or_create(
                user=user,
                asset=item["asset"],
                date=item["date"],
                action=item["action"],
                shares=item["shares"],
                price_per_share=item["price_per_share"],
                amount=item["amount"],
                notes=item["notes"],
            )
            if was_created:
                created += 1
            else:
                skipped += 1

    return CSVImportResult(success=True, created=created, skipped=skipped)


def import_investment_history_csv(user, uploaded_file):
    rows, errors = _read_csv_rows(
        uploaded_file,
        required_columns=INVESTMENT_HISTORY_CSV_FORMAT["required_columns"],
        optional_columns=INVESTMENT_HISTORY_CSV_FORMAT["optional_columns"],
    )
    if errors:
        return CSVImportResult(success=False, errors=errors)

    asset_index = defaultdict(list)
    for asset in Asset.objects.filter(user=user):
        asset_index[asset.name.casefold()].append(asset)

    parsed_rows = []
    row_errors = []
    row_keys = set()

    for row_number, row in rows:
        asset_name = row.get("asset", "").strip()
        parsed_date = _parse_date(row.get("date"), row_number, "date", row_errors)
        total_value = _parse_decimal(
            row.get("total_value"),
            row_number,
            "total_value",
            row_errors,
            allow_zero=True,
        )

        if not asset_name:
            row_errors.append(_row_error(row_number, "asset is required."))
        if parsed_date is None or total_value is None or not asset_name:
            continue

        asset_candidates = asset_index.get(asset_name.casefold(), [])
        if not asset_candidates:
            row_errors.append(_row_error(row_number, f"asset '{asset_name}' was not found."))
            continue
        if len(asset_candidates) > 1:
            row_errors.append(_row_error(row_number, f"asset '{asset_name}' is ambiguous."))
            continue
        asset = asset_candidates[0]

        row_key = (parsed_date, asset.id)
        if row_key in row_keys:
            row_errors.append(_row_error(row_number, "duplicate asset/date row in CSV file."))
            continue
        row_keys.add(row_key)

        parsed_rows.append(
            {
                "asset": asset,
                "date": parsed_date,
                "total_value": total_value,
            }
        )

    if row_errors:
        return CSVImportResult(success=False, errors=row_errors)

    created = 0
    updated = 0
    skipped = 0
    with db_transaction.atomic():
        for item in parsed_rows:
            existing = (
                AssetHistory.objects.filter(
                    user=user,
                    asset=item["asset"],
                    date=item["date"],
                )
                .order_by("id")
                .first()
            )

            if not existing:
                AssetHistory.objects.create(
                    user=user,
                    asset=item["asset"],
                    date=item["date"],
                    total_value=item["total_value"],
                )
                created += 1
                continue

            if existing.total_value == item["total_value"]:
                skipped += 1
                continue

            existing.total_value = item["total_value"]
            existing.save(update_fields=["total_value"])
            updated += 1

    return CSVImportResult(success=True, created=created, updated=updated, skipped=skipped)


def import_holding_snapshots_csv(user, uploaded_file):
    rows, errors = _read_csv_rows(
        uploaded_file,
        required_columns=HOLDING_SNAPSHOTS_CSV_FORMAT["required_columns"],
        optional_columns=HOLDING_SNAPSHOTS_CSV_FORMAT["optional_columns"],
    )
    if errors:
        return CSVImportResult(success=False, errors=errors)

    account_type_choices = {choice for choice, _ in BankAccount.ACCOUNT_TYPES}

    account_index = defaultdict(list)
    for account in BankAccount.objects.filter(user=user):
        key = (account.name.casefold(), account.institution.casefold())
        account_index[key].append(account)

    parsed_rows = []
    row_errors = []
    row_keys = set()

    for row_number, row in rows:
        account_name = row.get("account_name", "").strip()
        institution = row.get("institution", "").strip()
        account_type = row.get("account_type", "").strip().upper()
        currency = (row.get("currency", "").strip().upper() or "EUR")

        parsed_date = _parse_date(row.get("date"), row_number, "date", row_errors)
        balance = _parse_decimal(
            row.get("balance"),
            row_number,
            "balance",
            row_errors,
            allow_negative=True,
        )
        interest_earned = _parse_decimal(
            row.get("interest_earned"),
            row_number,
            "interest_earned",
            row_errors,
            required=False,
            allow_negative=True,
            allow_zero=True,
        )
        if interest_earned is None:
            interest_earned = Decimal("0")

        if not account_name:
            row_errors.append(_row_error(row_number, "account_name is required."))
        if not institution:
            row_errors.append(_row_error(row_number, "institution is required."))
        if account_type not in account_type_choices:
            row_errors.append(
                _row_error(
                    row_number,
                    "account_type must be one of: CHECKING, SAVINGS, CASH, DEBT.",
                )
            )
        if len(currency) != 3:
            row_errors.append(_row_error(row_number, "currency must have 3 characters."))
        if (
            parsed_date is None
            or balance is None
            or not account_name
            or not institution
            or account_type not in account_type_choices
            or len(currency) != 3
        ):
            continue

        account_key = (account_name.casefold(), institution.casefold())
        account_candidates = account_index.get(account_key, [])
        if len(account_candidates) > 1:
            row_errors.append(
                _row_error(
                    row_number,
                    f"account '{account_name}' at '{institution}' is ambiguous.",
                )
            )
            continue
        if account_candidates:
            account = account_candidates[0]
            if account.account_type != account_type:
                row_errors.append(
                    _row_error(
                        row_number,
                        (
                            f"existing account '{account_name}' at '{institution}' has "
                            f"account_type='{account.account_type}', but CSV row has '{account_type}'."
                        ),
                    )
                )
                continue
            if account.currency.upper() != currency:
                row_errors.append(
                    _row_error(
                        row_number,
                        (
                            f"existing account '{account_name}' at '{institution}' has "
                            f"currency='{account.currency.upper()}', but CSV row has '{currency}'."
                        ),
                    )
                )
                continue

        row_key = (parsed_date, account_key)
        if row_key in row_keys:
            row_errors.append(_row_error(row_number, "duplicate account/date row in CSV file."))
            continue
        row_keys.add(row_key)

        parsed_rows.append(
            {
                "account_name": account_name,
                "institution": institution,
                "account_type": account_type,
                "currency": currency,
                "date": parsed_date,
                "balance": balance,
                "interest_earned": interest_earned,
                "account_key": account_key,
            }
        )

    if row_errors:
        return CSVImportResult(success=False, errors=row_errors)

    created = 0
    updated = 0
    created_accounts = 0

    with db_transaction.atomic():
        for item in parsed_rows:
            account = account_index.get(item["account_key"], [None])[0]
            if account is None:
                account = BankAccount.objects.create(
                    user=user,
                    name=item["account_name"],
                    institution=item["institution"],
                    account_type=item["account_type"],
                    currency=item["currency"],
                )
                account_index[item["account_key"]].append(account)
                created_accounts += 1

            _, was_created = AccountBalanceSnapshot.objects.update_or_create(
                user=user,
                account=account,
                date=item["date"],
                defaults={
                    "balance": item["balance"],
                    "interest_earned": item["interest_earned"],
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

    return CSVImportResult(
        success=True,
        created=created,
        updated=updated,
        details={"accounts_created": created_accounts},
    )


def _read_csv_rows(uploaded_file, *, required_columns, optional_columns):
    payload = uploaded_file.read()

    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None, ["CSV must be UTF-8 encoded."]

    if not text.strip():
        return None, ["CSV file is empty."]

    delimiter = _detect_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    fieldnames = reader.fieldnames or []
    normalized_headers = [_normalize_header(name) for name in fieldnames if name is not None]

    if not normalized_headers:
        return None, ["CSV header is missing."]

    duplicates = {
        header for header in normalized_headers if normalized_headers.count(header) > 1
    }
    if duplicates:
        duplicates_text = ", ".join(sorted(duplicates))
        return None, [f"Duplicate header columns: {duplicates_text}."]

    required_set = set(required_columns)
    optional_set = set(optional_columns)
    allowed_set = required_set | optional_set

    missing = [name for name in required_columns if name not in normalized_headers]
    unknown = [name for name in normalized_headers if name not in allowed_set]
    errors = []
    if missing:
        errors.append(f"Missing required columns: {', '.join(missing)}.")
    if unknown:
        errors.append(f"Unknown columns: {', '.join(unknown)}.")
    if errors:
        return None, errors

    rows = []
    for row_number, raw_row in enumerate(reader, start=2):
        normalized_row = {}
        for key, value in raw_row.items():
            normalized_key = _normalize_header(key)
            if not normalized_key:
                continue
            normalized_row[normalized_key] = (value or "").strip()

        if not any(normalized_row.values()):
            continue
        rows.append((row_number, normalized_row))

    if not rows:
        return None, ["CSV file has no data rows."]

    return rows, []


def _normalize_header(value):
    return str(value or "").strip().lower()


def _detect_delimiter(text):
    first_line = text.splitlines()[0] if text.splitlines() else ""
    semicolon_count = first_line.count(";")
    comma_count = first_line.count(",")
    return ";" if semicolon_count > comma_count else ","


def _parse_date(value, row_number, field_name, errors):
    raw_value = (value or "").strip()
    if not raw_value:
        errors.append(_row_error(row_number, f"{field_name} is required."))
        return None

    try:
        return datetime.strptime(raw_value, "%Y-%m-%d").date()
    except ValueError:
        errors.append(
            _row_error(row_number, f"{field_name} must use YYYY-MM-DD format.")
        )
        return None


def _normalize_decimal_value(value):
    raw = str(value).strip().replace(" ", "")
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            return raw.replace(".", "").replace(",", ".")
        return raw.replace(",", "")
    return raw.replace(",", ".")


def _parse_decimal(
    value,
    row_number,
    field_name,
    errors,
    *,
    required=True,
    allow_negative=False,
    allow_zero=True,
):
    raw_value = (value or "").strip()
    if not raw_value:
        if required:
            errors.append(_row_error(row_number, f"{field_name} is required."))
        return None

    try:
        parsed_value = Decimal(_normalize_decimal_value(raw_value))
    except InvalidOperation:
        errors.append(_row_error(row_number, f"{field_name} must be a valid number."))
        return None

    if not allow_negative and parsed_value < 0:
        errors.append(_row_error(row_number, f"{field_name} cannot be negative."))
        return None
    if not allow_zero and parsed_value == 0:
        errors.append(_row_error(row_number, f"{field_name} must be greater than zero."))
        return None

    return parsed_value


def _row_error(row_number, message):
    return f"Row {row_number}: {message}"
