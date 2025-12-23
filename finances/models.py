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
    
    TRANSACTION_TYPES = [('INCOME', 'Income'), ('EXPENSE', 'Expense')]
    EXPENSE_TYPES = [('FIXED', 'Fixed'), ('VARIABLE', 'Variable'), ('N/A', 'Not Applicable')]

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
        if self.transaction_type == 'EXPENSE' and self.expense_type == 'N/A':
            raise ValidationError({'expense_type': "Expense must be Fixed or Variable."})
        if self.transaction_type == 'INCOME' and self.expense_type != 'N/A':
            raise ValidationError({'expense_type': "Income must be 'Not Applicable'."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class SubCategory(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='subcategories',
    )
    parent_category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100)
    is_essential = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Subcategories"
        constraints = [
            models.UniqueConstraint(fields=['parent_category', 'name'], name='unique_subcategory_per_category')
        ]

    def __str__(self):
        return f"{self.parent_category.name} -> {self.name}"

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
        self.amount = -abs(self.amount) if category_type == 'EXPENSE' else abs(self.amount)
        super().save(*args, **kwargs)