from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError

class Category(models.Model):
    # Cada usuario es dueño de su estructura de categorías
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='categories'
    )
    
    class TransactionType(models.TextChoices):
        INCOME = "INCOME", "Income"
        EXPENSE = "EXPENSE", "Expense"

    class ExpenseType(models.TextChoices):
        FIXED = "FIXED", "Fixed"
        VARIABLE = "VARIABLE", "Variable"
        NOT_APPLICABLE = "N/A", "Not Applicable"

    TRANSACTION_TYPES = TransactionType.choices
    EXPENSE_TYPES = ExpenseType.choices

    name = models.CharField(max_length=100) # Quitamos unique=True global
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    expense_type = models.CharField(max_length=10, choices=EXPENSE_TYPES, default='VARIABLE')
    is_housing = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Categories"
        # Importante: El nombre solo debe ser único PARA ESE USUARIO
        unique_together = ('user', 'name')

    def __str__(self):
        return f"{self.name} ({self.user.username})"
    
    def clean(self):
        super().clean()
        # Validación de negocio para tipos de gasto e ingreso
        if self.transaction_type == self.TransactionType.EXPENSE and self.expense_type == self.ExpenseType.NOT_APPLICABLE:
            raise ValidationError({'expense_type': "Expense must be Fixed or Variable."})
        if self.transaction_type == self.TransactionType.INCOME and self.expense_type != self.ExpenseType.NOT_APPLICABLE:
            raise ValidationError({'expense_type': "Income must be 'Not Applicable'."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class SubCategory(models.Model):
    SAVINGS_BUDGET_KEYWORDS = (
        "saving",
        "savings",
        "investment",
        "investing",
        "index",
        "retirement",
        "emergency fund",
        "debt",
        "loan",
        "credit card",
        "stock",
        "brokerage",
        "etf",
        "fondos",
        "inversión",
        "inversion",
    )
    NEEDS_BUDGET_KEYWORDS = (
        "insurance",
        "internet",
        "wifi",
        "rent",
        "mortgage",
        "utilities",
        "utility",
        "medical",
        "pharmacy",
        "groceries",
        "grocery",
        "supermarket",
        "market",
        "mercado",
        "supermercado",
        "public transport",
        "metro",
        "bus",
        "train",
        "fuel",
    )
    NEEDS_CATEGORY_KEYWORDS = (
        "rent",
        "mortgage",
        "housing",
        "utilities",
        "utility",
        "internet",
        "wifi",
        "insurance",
    )

    class BudgetGroup(models.TextChoices):
        NEEDS = "NEEDS", "Needs"
        WANTS = "WANTS", "Wants"
        SAVINGS = "SAVINGS", "Savings"
        NOT_APPLICABLE = "N/A", "Not Applicable"

    class ExpenseNature(models.TextChoices):
        FIXED = "FIXED", "Fixed"
        VARIABLE = "VARIABLE", "Variable"
        NOT_APPLICABLE = "N/A", "Not Applicable"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='subcategories',
    )
    parent_category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100)
    budget_group = models.CharField(
        max_length=10,
        choices=BudgetGroup.choices,
        default=BudgetGroup.NOT_APPLICABLE,
    )
    expense_nature = models.CharField(
        max_length=10,
        choices=ExpenseNature.choices,
        default=ExpenseNature.NOT_APPLICABLE,
    )
    is_essential = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Subcategories"
        constraints = [
            models.UniqueConstraint(fields=['parent_category', 'name'], name='unique_subcategory_per_category')
        ]

    def __str__(self):
        return f"{self.parent_category.name} -> {self.name}"

    @staticmethod
    def _contains_any(value, keywords):
        return any(keyword in value for keyword in keywords)

    @classmethod
    def infer_budget_group(cls, category, name="", is_essential=False):
        if category.transaction_type == Category.TransactionType.INCOME:
            return cls.BudgetGroup.NOT_APPLICABLE

        category_text = (category.name or "").casefold()
        subcategory_text = (name or "").casefold()
        combined = f"{category_text} {subcategory_text}"
        if cls._contains_any(combined, cls.SAVINGS_BUDGET_KEYWORDS):
            return cls.BudgetGroup.SAVINGS
        if (
            is_essential
            or category.is_housing
            or cls._contains_any(category_text, cls.NEEDS_CATEGORY_KEYWORDS)
            or cls._contains_any(subcategory_text, cls.NEEDS_BUDGET_KEYWORDS)
        ):
            return cls.BudgetGroup.NEEDS
        return cls.BudgetGroup.WANTS

    def apply_budget_defaults(self):
        try:
            category = self.parent_category
        except Category.DoesNotExist:
            return

        if category.transaction_type == Category.TransactionType.INCOME:
            self.budget_group = self.BudgetGroup.NOT_APPLICABLE
            self.expense_nature = self.ExpenseNature.NOT_APPLICABLE
            return

        if self.budget_group == self.BudgetGroup.NOT_APPLICABLE:
            self.budget_group = self.infer_budget_group(
                category=category,
                name=self.name,
                is_essential=self.is_essential,
            )

        if self.expense_nature == self.ExpenseNature.NOT_APPLICABLE:
            self.expense_nature = (
                self.ExpenseNature.FIXED
                if category.expense_type == Category.ExpenseType.FIXED
                else self.ExpenseNature.VARIABLE
            )

    def clean(self):
        super().clean()
        self.apply_budget_defaults()

        if not self.parent_category_id:
            return
        if self.parent_category.transaction_type == Category.TransactionType.INCOME:
            return

        if self.budget_group == self.BudgetGroup.NOT_APPLICABLE:
            raise ValidationError({"budget_group": "Expense subcategories need a budget group."})
        if self.expense_nature == self.ExpenseNature.NOT_APPLICABLE:
            raise ValidationError({"expense_nature": "Expense subcategories need an expense nature."})

    def save(self, *args, **kwargs):
        self.apply_budget_defaults()
        super().save(*args, **kwargs)

class Location(models.Model):
    # Ahora las ubicaciones también son privadas
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='locations',
    )
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ['name']
        unique_together = ('user', 'name')

    def __str__(self):
        return f"{self.name} ({self.user.username})"

class Transaction(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='finances_transactions'
    )
    date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    description = models.TextField(blank=True)
    
    subcategory = models.ForeignKey(SubCategory, on_delete=models.PROTECT, related_name='transactions')
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-date']

    def save(self, *args, **kwargs):
        category_type = self.subcategory.parent_category.transaction_type
        self.amount = -abs(self.amount) if category_type == Category.TransactionType.EXPENSE else abs(self.amount)
        super().save(*args, **kwargs)
