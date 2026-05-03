import re

from django import forms
from django.utils import timezone

from .models import Category, Location, SubCategory, Transaction
from .services.default_categories import get_default_category_blueprints


class CategoryForm(forms.ModelForm):
    subcategory_names = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "One subcategory per line (or separated by commas)",
            }
        ),
    )

    class Meta:
        model = Category
        fields = ["name", "transaction_type", "expense_type", "is_housing"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Category name",
                    "maxlength": "100",
                }
            ),
            "transaction_type": forms.Select(attrs={"class": "form-select"}),
            "expense_type": forms.Select(attrs={"class": "form-select"}),
            "is_housing": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, user, lock_name=False, allow_subcategories=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.lock_name = lock_name
        self.allow_subcategories = allow_subcategories
        self._parsed_subcategory_names = []
        self.fields["name"].label = "Name"
        self.fields["transaction_type"].label = "Transaction Type"
        self.fields["expense_type"].label = "Expense Type"
        self.fields["is_housing"].label = "Housing Category"
        if self.allow_subcategories:
            self.fields["subcategory_names"].label = "Initial Subcategories"
            self.fields["subcategory_names"].help_text = (
                "Optional. Add as many as needed now; you can edit or add more later."
            )
        else:
            self.fields.pop("subcategory_names", None)

        if self.lock_name and self.instance.pk:
            self.fields["name"].disabled = True
            self.fields["name"].help_text = "Name cannot be edited."

    def clean_name(self):
        if self.lock_name and self.instance.pk:
            return self.instance.name

        name = self.cleaned_data["name"].strip()
        duplicated_name = Category.objects.filter(
            user=self.user, name__iexact=name
        ).exclude(pk=self.instance.pk)

        if duplicated_name.exists():
            raise forms.ValidationError("You already have a category with this name.")
        return name

    def clean(self):
        cleaned_data = super().clean()
        tx_type = cleaned_data.get("transaction_type")
        expense_type = cleaned_data.get("expense_type")
        is_housing = cleaned_data.get("is_housing")

        if tx_type == "INCOME":
            cleaned_data["expense_type"] = "N/A"
            cleaned_data["is_housing"] = False
        elif tx_type == "EXPENSE" and expense_type == "N/A":
            self.add_error("expense_type", "Expense categories must be Fixed or Variable.")

        if tx_type != "EXPENSE" and is_housing:
            self.add_error("is_housing", "Only expense categories can be marked as housing.")

        return cleaned_data

    def clean_subcategory_names(self):
        if not self.allow_subcategories:
            return ""

        raw_value = self.cleaned_data.get("subcategory_names", "") or ""
        parsed_names = []
        seen = set()

        for chunk in re.split(r"[\n,;]+", raw_value):
            name = chunk.strip()
            if not name:
                continue
            if len(name) > 100:
                raise forms.ValidationError("Subcategory names must be 100 characters or less.")

            normalized = name.casefold()
            if normalized in seen:
                raise forms.ValidationError("Remove duplicated subcategory names in this list.")
            seen.add(normalized)
            parsed_names.append(name)

        self._parsed_subcategory_names = parsed_names
        return "\n".join(parsed_names)

    def get_subcategory_names(self):
        return list(self._parsed_subcategory_names)

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.user = self.user
        if commit:
            instance.save()
        return instance


class DefaultCategoryPresetForm(forms.Form):
    category_keys = forms.MultipleChoiceField(
        required=False,
        choices=(),
        widget=forms.CheckboxSelectMultiple,
    )
    subcategory_keys = forms.MultipleChoiceField(
        required=False,
        choices=(),
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.blueprints = get_default_category_blueprints()
        self.category_map = {item["key"]: item for item in self.blueprints}
        self.required_category_keys = {
            item["key"] for item in self.blueprints if item.get("required")
        }
        self.existing_categories_by_name = self._get_existing_categories_by_name()
        self.locked_category_keys = self._get_locked_category_keys()
        self.subcategory_to_category = {}
        self.existing_subcategory_names_by_category_key = (
            self._get_existing_subcategory_names_by_category_key()
        )

        category_choices = []
        subcategory_choices = []
        for category in self.blueprints:
            category_choices.append((category["key"], category["name"]))
            for subcategory in category["subcategories"]:
                subcategory_choices.append(
                    (
                        subcategory["key"],
                        f'{category["name"]} -> {subcategory["name"]}',
                    )
                )
                self.subcategory_to_category[subcategory["key"]] = category["key"]

        self.fields["category_keys"].choices = category_choices
        self.fields["subcategory_keys"].choices = subcategory_choices

    def _get_existing_categories_by_name(self):
        if not self.user or not getattr(self.user, "is_authenticated", False):
            return {}

        return {
            category.name.casefold(): category
            for category in Category.objects.filter(user=self.user)
        }

    def _get_locked_category_keys(self):
        locked = set()
        for category in self.blueprints:
            if not category.get("required"):
                continue
            if category["name"].casefold() not in self.existing_categories_by_name:
                locked.add(category["key"])
        return locked

    def _get_existing_subcategory_names_by_category_key(self):
        if not self.user or not getattr(self.user, "is_authenticated", False):
            return {}

        data = {}
        for category in self.blueprints:
            existing_category = self.existing_categories_by_name.get(category["name"].casefold())
            if not existing_category:
                data[category["key"]] = set()
                continue
            data[category["key"]] = {
                name.casefold()
                for name in SubCategory.objects.filter(
                    user=self.user,
                    parent_category=existing_category,
                ).values_list("name", flat=True)
            }
        return data

    def get_initial_selection(self):
        selected_categories = set()
        selected_subcategories = set()

        for category in self.blueprints:
            category_key = category["key"]
            existing_category = self.existing_categories_by_name.get(category["name"].casefold())
            existing_subcategory_names = self.existing_subcategory_names_by_category_key.get(
                category_key,
                set(),
            )
            category_selected = category.get("selected_by_default", True) or (
                category_key in self.locked_category_keys
            )
            selected_category_subcategories = []

            for subcategory in category["subcategories"]:
                if not subcategory.get("selected_by_default", True):
                    continue
                if existing_category and subcategory["name"].casefold() in existing_subcategory_names:
                    continue
                selected_category_subcategories.append(subcategory["key"])

            if category_selected and (selected_category_subcategories or not existing_category):
                selected_categories.add(category_key)
                selected_subcategories.update(selected_category_subcategories)

        return selected_categories, selected_subcategories

    def clean_category_keys(self):
        selected = self.cleaned_data.get("category_keys", [])
        if not selected:
            raise forms.ValidationError("Select at least one default category.")

        selected_set = set(selected)
        missing_required = self.locked_category_keys - selected_set
        if missing_required:
            raise forms.ValidationError("The category Income is required.")
        return selected

    def clean(self):
        cleaned_data = super().clean()
        selected_categories = set(cleaned_data.get("category_keys", []))
        selected_subcategories = cleaned_data.get("subcategory_keys", [])

        filtered_subcategories = [
            key
            for key in selected_subcategories
            if self.subcategory_to_category.get(key) in selected_categories
        ]
        cleaned_data["subcategory_keys"] = filtered_subcategories
        return cleaned_data

    def get_creation_payload(self):
        selected_categories = set(self.cleaned_data.get("category_keys", []))
        selected_subcategories = set(self.cleaned_data.get("subcategory_keys", []))
        payload = []

        for category in self.blueprints:
            if category["key"] not in selected_categories:
                continue

            payload.append(
                {
                    "name": category["name"],
                    "transaction_type": category["transaction_type"],
                    "expense_type": category["expense_type"],
                    "is_housing": category["is_housing"],
                    "subcategories": [
                        subcategory
                        for subcategory in category["subcategories"]
                        if subcategory["key"] in selected_subcategories
                    ],
                }
            )

        return payload


class SubCategoryForm(forms.ModelForm):
    class Meta:
        model = SubCategory
        fields = ["parent_category", "name", "budget_group", "expense_nature", "is_essential"]
        widgets = {
            "parent_category": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Subcategory name",
                    "maxlength": "100",
                }
            ),
            "budget_group": forms.Select(attrs={"class": "form-select"}),
            "expense_nature": forms.Select(attrs={"class": "form-select"}),
            "is_essential": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, user, lock_name=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.lock_name = lock_name
        self.fields["parent_category"].queryset = Category.objects.filter(user=user).order_by(
            "name"
        )
        self.fields["parent_category"].label_from_instance = lambda obj: obj.name
        self.fields["parent_category"].label = "Parent Category"
        self.fields["name"].label = "Name"
        self.fields["budget_group"].label = "Budget Group"
        self.fields["expense_nature"].label = "Expense Nature"
        self.fields["is_essential"].label = "Essential Subcategory"
        self.fields["budget_group"].required = False
        self.fields["expense_nature"].required = False
        if self.lock_name and self.instance.pk:
            self.fields["name"].disabled = True
            self.fields["name"].help_text = "Name cannot be edited."

    def clean_name(self):
        if self.lock_name and self.instance.pk:
            name = self.instance.name
        else:
            name = self.cleaned_data["name"].strip()

        parent = self.cleaned_data.get("parent_category")
        if not parent:
            return name

        duplicated_name = SubCategory.objects.filter(
            parent_category=parent,
            name__iexact=name,
        ).exclude(pk=self.instance.pk)
        if duplicated_name.exists():
            raise forms.ValidationError(
                "This subcategory already exists in the selected category."
            )
        return name

    def clean_parent_category(self):
        parent_category = self.cleaned_data["parent_category"]
        if parent_category.user_id != self.user.id:
            raise forms.ValidationError("Invalid parent category.")
        return parent_category

    def clean(self):
        cleaned_data = super().clean()
        parent = cleaned_data.get("parent_category")
        if not parent:
            return cleaned_data

        if parent.transaction_type == Category.TransactionType.INCOME:
            cleaned_data["budget_group"] = SubCategory.BudgetGroup.NOT_APPLICABLE
            cleaned_data["expense_nature"] = SubCategory.ExpenseNature.NOT_APPLICABLE
            return cleaned_data

        if (
            not cleaned_data.get("budget_group")
            or cleaned_data.get("budget_group") == SubCategory.BudgetGroup.NOT_APPLICABLE
        ):
            cleaned_data["budget_group"] = SubCategory.infer_budget_group(
                category=parent,
                name=cleaned_data.get("name", ""),
                is_essential=cleaned_data.get("is_essential", False),
            )

        if (
            not cleaned_data.get("expense_nature")
            or cleaned_data.get("expense_nature") == SubCategory.ExpenseNature.NOT_APPLICABLE
        ):
            cleaned_data["expense_nature"] = (
                SubCategory.ExpenseNature.FIXED
                if parent.expense_type == Category.ExpenseType.FIXED
                else SubCategory.ExpenseNature.VARIABLE
            )

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.user = self.user
        if commit:
            instance.save()
        return instance


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Location name",
                    "maxlength": "100",
                }
            ),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["name"].label = "Name"

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        duplicated_name = Location.objects.filter(
            user=self.user,
            name__iexact=name,
        ).exclude(pk=self.instance.pk)
        if duplicated_name.exists():
            raise forms.ValidationError("You already have a location with this name.")
        return name

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.user = self.user
        if commit:
            instance.save()
        return instance


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["date", "amount", "description", "subcategory", "location"]
        widgets = {
            "date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
            "amount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "0.00",
                    "step": "0.01",
                    "min": "0.01",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Optional details...",
                }
            ),
            "subcategory": forms.Select(attrs={"class": "form-select"}),
            "location": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["date"].label = "Date"
        self.fields["amount"].label = "Amount"
        self.fields["description"].label = "Description"
        self.fields["subcategory"].label = "Subcategory"
        self.fields["location"].label = "Location"
        self.fields["subcategory"].queryset = (
            SubCategory.objects.filter(user=user)
            .select_related("parent_category")
            .order_by("parent_category__name", "name")
        )
        self.fields["subcategory"].label_from_instance = (
            lambda obj: f"{obj.parent_category.name} -> {obj.name}"
        )
        self.fields["location"].queryset = Location.objects.filter(user=user).order_by("name")
        self.fields["location"].label_from_instance = lambda obj: obj.name
        self.fields["location"].empty_label = "No location"
        if not self.instance.pk:
            self.initial.setdefault("date", timezone.localdate())

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount is None or amount <= 0:
            raise forms.ValidationError("Amount must be greater than zero.")
        return amount

    def clean_subcategory(self):
        subcategory = self.cleaned_data["subcategory"]
        if subcategory.user_id != self.user.id:
            raise forms.ValidationError("Invalid subcategory.")
        return subcategory

    def clean_location(self):
        location = self.cleaned_data.get("location")
        if location and location.user_id != self.user.id:
            raise forms.ValidationError("Invalid location.")
        return location

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.user = self.user
        if commit:
            instance.save()
        return instance
