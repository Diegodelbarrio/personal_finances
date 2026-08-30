from django import forms
from django.conf import settings


class CSVUploadForm(forms.Form):
    csv_file = forms.FileField(
        label="CSV File",
        widget=forms.ClearableFileInput(
            attrs={
                "class": "form-control",
                "accept": ".csv,text/csv",
            }
        ),
    )

    def clean_csv_file(self):
        uploaded_file = self.cleaned_data["csv_file"]
        file_name = (uploaded_file.name or "").lower()

        if not file_name.endswith(".csv"):
            raise forms.ValidationError("Only .csv files are allowed.")
        if uploaded_file.size == 0:
            raise forms.ValidationError("The uploaded CSV file is empty.")
        if uploaded_file.size > settings.CSV_IMPORT_MAX_BYTES:
            max_megabytes = settings.CSV_IMPORT_MAX_BYTES / (1024 * 1024)
            raise forms.ValidationError(
                f"CSV file must be {max_megabytes:g} MB or smaller."
            )

        return uploaded_file
