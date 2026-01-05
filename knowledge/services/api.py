from django.shortcuts import get_object_or_404
from ..models import Article

def get_knowledge_base_index():
    """Retorna todos los artículos publicados ordenados por fecha."""
    return Article.objects.filter(is_published=True)

def get_article_by_slug(slug):
    """Retorna un artículo específico o 404."""
    return get_object_or_404(Article, slug=slug, is_published=True)

def get_related_articles(article, limit=3):
    """Retorna artículos sugeridos de la misma categoría."""
    return Article.objects.filter(
        category=article.category, 
        is_published=True
    ).exclude(id=article.id)[:limit]