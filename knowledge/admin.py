from django.contrib import admin
from .models import Article

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'read_time_minutes', 'is_published', 'updated_at')
    list_filter = ('category', 'is_published')
    search_fields = ('title', 'summary')
    prepopulated_fields = {'slug': ('title',)}
    
    fieldsets = (
        ('Main Content', {'fields': ('title', 'slug', 'summary', 'content')}),
        ('Metadatos', {'fields': ('category', 'icon', 'read_time_minutes', 'is_published')}),
    )