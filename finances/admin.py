from django.contrib import admin
from .models import Category, SubCategory, Location, Transaction

admin.site.register(Category)
admin.site.register(Location)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    # This defines which columns will be visible in the main list
    list_display = ('date', 'description', 'amount', 'subcategory', 'location')

    # This adds filters on the right side for quick navigation
    list_filter = ('date', 'subcategory__parent_category', 'location')

    # This adds a search bar to find expenses by name
    search_fields = ('description',)

@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    # Columns that will be visible in the list
    list_display = ('name', 'parent_category', 'is_essential')

    # The side filter you are looking for
    list_filter = ('parent_category', 'is_essential')

    # Allows searching by subcategory name or parent category
    search_fields = ('name', 'parent_category__name')