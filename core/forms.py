from django import forms


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

        return uploaded_file
