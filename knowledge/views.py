from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .services import api

@login_required
def index(request):
    articles = api.get_knowledge_base_index()
    context = {
        'articles': articles,
        'page_title': 'Financial Academy'
    }
    return render(request, 'index.html', context)

@login_required
def detail(request, slug):
    article = api.get_article_by_slug(slug)
    related = api.get_related_articles(article)
    context = {
        'article': article,
        'related_articles': related,
        'page_title': article.title
    }
    return render(request, 'detail.html', context)