from django.contrib import admin
from .models import Category, SubCategory, Location, Transaction

admin.site.register(Category)
admin.site.register(SubCategory)
admin.site.register(Location)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    # This defines which columns will be visible in the main list
    list_display = ('date', 'description', 'amount', 'subcategory', 'location')

    # This adds filters on the right side for quick navigation
    list_filter = ('date', 'subcategory', 'location')

    # This adds a search bar to find expenses by name
    search_fields = ('description',)