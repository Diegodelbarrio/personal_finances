from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from core.forms import CSVUploadForm
from core.services.csv_import import _read_csv_rows


class CSVImportLimitsTest(SimpleTestCase):
    @override_settings(CSV_IMPORT_MAX_BYTES=20)
    def test_upload_form_rejects_file_above_size_limit(self):
        upload = SimpleUploadedFile("large.csv", b"x" * 21, content_type="text/csv")

        form = CSVUploadForm(files={"csv_file": upload})

        self.assertFalse(form.is_valid())
        self.assertIn("csv_file", form.errors)

    @override_settings(
        CSV_IMPORT_MAX_BYTES=1000,
        CSV_IMPORT_MAX_ROWS=2,
        CSV_IMPORT_MAX_FIELD_LENGTH=100,
    )
    def test_reader_rejects_rows_above_limit(self):
        upload = SimpleUploadedFile(
            "rows.csv",
            b"date,amount\n2026-01-01,1\n2026-01-02,2\n2026-01-03,3\n",
            content_type="text/csv",
        )

        rows, errors = _read_csv_rows(
            upload,
            required_columns=["date", "amount"],
            optional_columns=[],
        )

        self.assertIsNone(rows)
        self.assertEqual(errors, ["CSV file exceeds the configured row limit."])

    @override_settings(
        CSV_IMPORT_MAX_BYTES=1000,
        CSV_IMPORT_MAX_ROWS=10,
        CSV_IMPORT_MAX_FIELD_LENGTH=8,
    )
    def test_reader_rejects_field_above_limit(self):
        upload = SimpleUploadedFile(
            "field.csv",
            b"date,x\n2026-01-01,123456789\n",
            content_type="text/csv",
        )

        rows, errors = _read_csv_rows(
            upload,
            required_columns=["date", "x"],
            optional_columns=[],
        )

        self.assertIsNone(rows)
        self.assertEqual(
            errors,
            ["CSV contains a field that exceeds the configured limit."],
        )
