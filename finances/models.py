from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError

class Category(models.Model):
    """
    Main financial categories (e.g., Leisure, Housing, Income).
    Used for high-level grouping and budget analysis.
    """
    TRANSACTION_TYPES = [
        ('INCOME', 'Income'),
        ('EXPENSE', 'Expense'),
    ]

    EXPENSE_TYPES = [
        ('FIXED', 'Fixed'),
        ('VARIABLE', 'Variable'),
        ('N/A', 'Not Applicable'), # Used for Income
    ]

    name = models.CharField(max_length=100, unique=True)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    expense_type = models.CharField(max_length=10, choices=EXPENSE_TYPES, default='VARIABLE')
    
    # Special flag to easily calculate "Expenses excluding Housing"
    is_housing = models.BooleanField(default=False)

    # Special flag to mark essential categories
    is_essential = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name
    
    def clean(self):
        # Validate the consistency between transaction_type and expense_type
        super().clean()

        if self.name:
            # Search for existing category by name (case-insensitive)
            # Exclude current object (self.pk) to allow updates without error
            exists = Category.objects.filter(
                name__iexact=self.name.strip()
            ).exclude(pk=self.pk).exists()

            if exists:
                raise ValidationError({
                    'name': f"There already exists a category called '{self.name}' (the name cannot be repeated even by changing uppercase letters)."
                })
        # 1. Error if it's an EXPENSE but marked as N/A
        if self.transaction_type == 'EXPENSE' and self.expense_type == 'N/A':
            raise ValidationError({
                'expense_type': "A category of expenses must be 'Fixed' or 'Variable', it cannot be 'Not applicable'."
            })

        # 2. Error if it's an INCOME but trying to save as Fixed or Variable
        if self.transaction_type == 'INCOME' and self.expense_type != 'N/A':
            raise ValidationError({
                'expense_type': "For income, the expense type must be 'Not Applicable'."
            })
        
        # 3. Nueva Validación: Essential solo para Fixed
        if self.is_essential and self.expense_type != 'FIXED':
            raise ValidationError({
                'is_essential': "Only 'Fixed' expenses can be marked as 'Essential'."
            })

    def save(self, *args, **kwargs):
        # Forzamos la ejecución de clean() antes de guardar, 
        # ya que save() por defecto no lo llama automáticamente.
        self.full_clean()
        super().save(*args, **kwargs)


class SubCategory(models.Model):
    """
    Detailed classification (e.g., Uber, Rent, Supermarket).
    Each subcategory belongs to a parent Category.
    """
    parent_category = models.ForeignKey(
        Category, 
        on_delete=models.CASCADE, 
        related_name='subcategories'
    )
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name_plural = "Subcategories"
        # This prevents having two subcategories with the same name within the same parent category.
        constraints = [
            models.UniqueConstraint(
                fields=['parent_category', 'name'], 
                name='unique_subcategory_per_category'
            )
        ]

    def clean(self):
        super().clean()
        if self.name and self.parent_category:
            # 🛡️ Validamos unicidad dentro de la misma categoría padre
            exists = SubCategory.objects.filter(
                parent_category=self.parent_category,
                name__iexact=self.name.strip()
            ).exclude(pk=self.pk).exists()

            if exists:
                raise ValidationError({
                    'name': f"There already exists a subcategory called '{self.name}' under the category {self.parent_category.name}."
                })

    def __str__(self):
        return f"{self.parent_category.name} -> {self.name}"


class Location(models.Model):
    """
    Lookup table for places (e.g., Madrid, Brussels, Online).
    Allows filtering expenses by geographic area.
    """
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class Transaction(models.Model):
    date = models.DateField()
    
    # The user always enters a positive number
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    
    description = models.TextField(
        blank=True, 
        help_text="Detailed notes (e.g., 'Groceries at Lidl')"
    )
    
    # Relationship: Transaction -> SubCategory -> Category
    subcategory = models.ForeignKey(
        'SubCategory', 
        on_delete=models.PROTECT, 
        related_name='transactions'
    )
    
    location = models.ForeignKey(
        'Location', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.date} | {self.subcategory.name} | {self.amount}"

    def save(self, *args, **kwargs):
        # 1. We look up the type from the related Category
        # Access path: self.subcategory (Foreign Key) -> category (Foreign Key)
        category_type = self.subcategory.parent_category.transaction_type

        # 2. Apply the sign automatically based on the Category's source of truth
        if category_type == 'EXPENSE':
            self.amount = -abs(self.amount)
        else:
            self.amount = abs(self.amount)
            
        super().save(*args, **kwargs)
