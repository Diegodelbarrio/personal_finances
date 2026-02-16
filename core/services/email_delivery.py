from dataclasses import dataclass
from typing import Iterable

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.utils.html import strip_tags


@dataclass
class EmailDeliveryResult:
    messages_sent: int
    recipients: int
    category: str
    backend: str


def _prefixed_subject(subject):
    prefix = (settings.EMAIL_SUBJECT_PREFIX or "").strip()
    return f"{prefix} {subject}".strip() if prefix else subject


def _connection_kwargs_for_backend(prefix):
    return {
        "host": getattr(settings, f"{prefix}_HOST", "localhost"),
        "port": getattr(settings, f"{prefix}_PORT", 25),
        "username": getattr(settings, f"{prefix}_HOST_USER", ""),
        "password": getattr(settings, f"{prefix}_HOST_PASSWORD", ""),
        "use_tls": getattr(settings, f"{prefix}_USE_TLS", False),
        "use_ssl": getattr(settings, f"{prefix}_USE_SSL", False),
        "timeout": getattr(settings, f"{prefix}_TIMEOUT", 10),
    }


def get_email_connection(category="transactional"):
    if category == "marketing":
        if not settings.EMAIL_MARKETING_ENABLED:
            raise RuntimeError(
                "Marketing email channel is disabled. Set EMAIL_MARKETING_ENABLED=True."
            )
        backend = settings.EMAIL_MARKETING_BACKEND
        if backend.endswith("smtp.EmailBackend"):
            return get_connection(
                backend=backend,
                fail_silently=settings.EMAIL_FAIL_SILENTLY,
                **_connection_kwargs_for_backend("EMAIL_MARKETING"),
            )
        return get_connection(
            backend=backend,
            fail_silently=settings.EMAIL_FAIL_SILENTLY,
        )

    backend = settings.EMAIL_BACKEND
    if backend.endswith("smtp.EmailBackend"):
        return get_connection(
            backend=backend,
            fail_silently=settings.EMAIL_FAIL_SILENTLY,
            **_connection_kwargs_for_backend("EMAIL"),
        )
    return get_connection(backend=backend, fail_silently=settings.EMAIL_FAIL_SILENTLY)


def _prepare_bodies(text_body, html_body, template_base, context):
    rendered_text = text_body
    rendered_html = html_body

    if template_base:
        context = context or {}
        if rendered_text is None:
            rendered_text = render_to_string(f"{template_base}.txt", context)
        if rendered_html is None:
            try:
                rendered_html = render_to_string(f"{template_base}.html", context)
            except Exception:
                rendered_html = None

    if rendered_text is None and rendered_html is not None:
        rendered_text = strip_tags(rendered_html)

    if rendered_text is None:
        rendered_text = ""

    return rendered_text, rendered_html


def send_transactional_email(
    *,
    subject,
    to,
    text_body=None,
    html_body=None,
    template_base=None,
    context=None,
    from_email=None,
    reply_to=None,
    headers=None,
):
    recipients = list(to)
    if not recipients:
        return EmailDeliveryResult(
            messages_sent=0,
            recipients=0,
            category="transactional",
            backend=settings.EMAIL_BACKEND,
        )

    text_body, html_body = _prepare_bodies(text_body, html_body, template_base, context)
    connection = get_email_connection(category="transactional")
    message = EmailMultiAlternatives(
        subject=_prefixed_subject(subject),
        body=text_body,
        from_email=from_email or settings.EMAIL_TRANSACTIONAL_FROM_EMAIL,
        to=recipients,
        reply_to=reply_to or settings.EMAIL_TRANSACTIONAL_REPLY_TO,
        headers=headers or {},
        connection=connection,
    )
    if html_body:
        message.attach_alternative(html_body, "text/html")
    sent = message.send()
    return EmailDeliveryResult(
        messages_sent=sent,
        recipients=len(recipients),
        category="transactional",
        backend=connection.__class__.__name__,
    )


def _chunked(iterable: Iterable[str], size: int):
    chunk = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def send_marketing_email(
    *,
    subject,
    recipients,
    text_body=None,
    html_body=None,
    template_base=None,
    context=None,
    from_email=None,
    reply_to=None,
    headers=None,
):
    recipient_list = list(recipients)
    if not recipient_list:
        return EmailDeliveryResult(
            messages_sent=0,
            recipients=0,
            category="marketing",
            backend=settings.EMAIL_MARKETING_BACKEND,
        )

    text_body, html_body = _prepare_bodies(text_body, html_body, template_base, context)
    connection = get_email_connection(category="marketing")
    batch_size = max(int(settings.EMAIL_MARKETING_BATCH_SIZE), 1)
    sent_messages = 0

    for batch in _chunked(recipient_list, batch_size):
        message_headers = dict(headers or {})
        message_headers.setdefault("X-Campaign", "marketing")
        message = EmailMultiAlternatives(
            subject=_prefixed_subject(subject),
            body=text_body,
            from_email=from_email or settings.EMAIL_MARKETING_FROM_EMAIL,
            to=batch,
            reply_to=reply_to or settings.EMAIL_MARKETING_REPLY_TO,
            headers=message_headers,
            connection=connection,
        )
        if html_body:
            message.attach_alternative(html_body, "text/html")
        sent_messages += message.send()

    return EmailDeliveryResult(
        messages_sent=sent_messages,
        recipients=len(recipient_list),
        category="marketing",
        backend=connection.__class__.__name__,
    )
