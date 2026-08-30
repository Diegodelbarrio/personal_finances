from django.test import TestCase

from knowledge.templatetags.knowledge_security import sanitize_article_html


class KnowledgeSecurityTest(TestCase):
    def test_article_html_removes_scripts_event_handlers_and_unsafe_urls(self):
        value = (
            '<p onclick="steal()">Safe text</p>'
            '<script>alert("xss")</script>'
            '<a href="javascript:steal()">Unsafe link</a>'
            '<a href="https://example.com">Safe link</a>'
        )

        cleaned = str(sanitize_article_html(value))

        self.assertIn("Safe text", cleaned)
        self.assertIn('href="https://example.com"', cleaned)
        self.assertNotIn("<script", cleaned)
        self.assertNotIn("onclick", cleaned)
        self.assertNotIn("javascript:", cleaned)
