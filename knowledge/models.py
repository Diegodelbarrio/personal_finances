from django.db import models
from django.utils.text import slugify
from django.urls import reverse

class ArticleCategory(models.TextChoices):
    FUNDAMENTALS = 'FUNDAMENTALS', 'Fundamentals'
    STRATEGY = 'STRATEGY', 'Strategy'
    PSYCHOLOGY = 'PSYCHOLOGY', 'Psychology'
    TUTORIAL = 'TUTORIAL', 'Tutorials'

class Article(models.Model):
    title = models.CharField(max_length=255, verbose_name="Title")
    slug = models.SlugField(unique=True, blank=True, max_length=255)
    
    category = models.CharField(
        max_length=50, 
        choices=ArticleCategory.choices, 
        default=ArticleCategory.FUNDAMENTALS
    )
    
    summary = models.TextField(help_text="Brief description for the preview card.")
    content = models.TextField(help_text="HTML content of the article.")
    
    # Metadatos visuales
    icon = models.CharField(max_length=50, default="bi-lightbulb", help_text="Bootstrap icon class (ej: bi-graph-up, bi-piggy-bank)")
    read_time_minutes = models.PositiveIntegerField(default=5, verbose_name="Reading time (min)")
    
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Article"
        verbose_name_plural = "Knowledge Base"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('knowledge:detail', kwargs={'slug': self.slug})

    def __str__(self):
        return self.title