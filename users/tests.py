from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
import re

from users.forms import ProfileForm, ProfilePreferencesForm

User = get_user_model()


class ProfileViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="diego",
            password="test1234",
            email="diego@example.com",
            first_name="Diego",
            last_name="Del Barrio",
        )
        self.other_user = User.objects.create_user(
            username="other",
            password="test1234",
            email="other@example.com",
        )

    def test_profile_requires_login(self):
        response = self.client.get(reverse("users:profile"))
        self.assertEqual(response.status_code, 302)

    def test_profile_get_renders(self):
        self.client.login(username="diego", password="test1234")
        response = self.client.get(reverse("users:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Personal Information")
        self.assertContains(response, "Workspace Usage")
        self.assertContains(response, "Account Readiness")

    def test_profile_post_updates_basic_fields(self):
        self.client.login(username="diego", password="test1234")
        response = self.client.post(
            reverse("users:profile"),
            {
                "profile-username": "diego-updated",
                "profile-first_name": " Diego ",
                "profile-last_name": "Updated ",
                "profile-email": "new.email@example.com",
                "prefs-language_code": "es",
                "prefs-timezone": "America/New_York",
            },
        )

        self.assertRedirects(response, reverse("users:profile"))
        self.user.refresh_from_db()
        self.user.settings.refresh_from_db()
        self.assertEqual(self.user.username, "diego-updated")
        self.assertEqual(self.user.first_name, "Diego")
        self.assertEqual(self.user.last_name, "Updated")
        self.assertEqual(self.user.email, "new.email@example.com")
        self.assertEqual(self.user.settings.language_code, "es")
        self.assertEqual(self.user.settings.timezone, "America/New_York")

    def test_profile_post_rejects_duplicate_email(self):
        self.client.login(username="diego", password="test1234")
        response = self.client.post(
            reverse("users:profile"),
            {
                "profile-username": "diego",
                "profile-first_name": "Diego",
                "profile-last_name": "Del Barrio",
                "profile-email": "other@example.com",
                "prefs-language_code": "en-us",
                "prefs-timezone": "Europe/Madrid",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already in use")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "diego@example.com")

    def test_profile_post_rejects_duplicate_username(self):
        self.client.login(username="diego", password="test1234")
        response = self.client.post(
            reverse("users:profile"),
            {
                "profile-username": "other",
                "profile-first_name": "Diego",
                "profile-last_name": "Del Barrio",
                "profile-email": "diego@example.com",
                "prefs-language_code": "en-us",
                "prefs-timezone": "Europe/Madrid",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already in use")
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "diego")

    def test_profile_post_rejects_invalid_timezone(self):
        self.client.login(username="diego", password="test1234")
        response = self.client.post(
            reverse("users:profile"),
            {
                "profile-username": "diego",
                "profile-first_name": "Diego",
                "profile-last_name": "Del Barrio",
                "profile-email": "diego@example.com",
                "prefs-language_code": "en-us",
                "prefs-timezone": "Not/AZone",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose a valid time zone.")

    def test_profile_post_uploads_and_removes_avatar(self):
        self.client.login(username="diego", password="test1234")

        avatar = SimpleUploadedFile(
            "avatar.png",
            b"fake-image-content",
            content_type="image/png",
        )
        upload_response = self.client.post(
            reverse("users:profile"),
            {
                "profile-username": "diego",
                "profile-first_name": "Diego",
                "profile-last_name": "Del Barrio",
                "profile-email": "diego@example.com",
                "prefs-language_code": "en-us",
                "prefs-timezone": "Europe/Madrid",
                "profile-remove_avatar": "",
                "profile-avatar": avatar,
            },
        )
        self.assertRedirects(upload_response, reverse("users:profile"))
        self.user.refresh_from_db()
        self.assertTrue(bool(self.user.avatar))

        remove_response = self.client.post(
            reverse("users:profile"),
            {
                "profile-username": "diego",
                "profile-first_name": "Diego",
                "profile-last_name": "Del Barrio",
                "profile-email": "diego@example.com",
                "prefs-language_code": "en-us",
                "prefs-timezone": "Europe/Madrid",
                "profile-remove_avatar": "on",
            },
        )
        self.assertRedirects(remove_response, reverse("users:profile"))
        self.user.refresh_from_db()
        self.assertFalse(bool(self.user.avatar))

    def test_profile_form_rejects_upload_and_remove_avatar_together(self):
        avatar = SimpleUploadedFile(
            "avatar.png",
            b"fake-image-content",
            content_type="image/png",
        )
        form = ProfileForm(
            data={
                "username": "diego",
                "first_name": "Diego",
                "last_name": "Del Barrio",
                "email": "diego@example.com",
                "remove_avatar": "on",
            },
            files={"avatar": avatar},
            instance=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("avatar", form.errors)

    def test_preferences_form_rejects_invalid_timezone(self):
        form = ProfilePreferencesForm(
            data={
                "language_code": "en-us",
                "timezone": "Not/AZone",
            },
            instance=self.user.settings,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("timezone", form.errors)

    def test_account_pages_use_custom_templates(self):
        self.client.login(username="diego", password="test1234")

        password_response = self.client.get(reverse("account_change_password"))
        self.assertEqual(password_response.status_code, 200)
        self.assertContains(password_response, "Change Password")

        email_response = self.client.get(reverse("account_email"))
        self.assertEqual(email_response.status_code, 200)
        self.assertContains(email_response, "Manage Email Addresses")

    def test_account_email_defaults_to_selected_address(self):
        self.client.login(username="diego", password="test1234")
        EmailAddress.objects.filter(user=self.user).delete()
        EmailAddress.objects.create(
            user=self.user,
            email="diego@example.com",
            verified=False,
            primary=False,
        )

        response = self.client.get(reverse("account_email"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="diego@example.com"')
        html = response.content.decode()
        self.assertRegex(
            html,
            re.compile(
                r'name="email"\s+value="diego@example\.com"\s+checked',
                re.IGNORECASE,
            ),
        )

    @override_settings(
        ACCOUNT_EMAIL_VERIFICATION="optional",
        ACCOUNT_RATE_LIMITS=False,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_account_email_resend_verification_sends_email(self):
        self.client.login(username="diego", password="test1234")
        EmailAddress.objects.filter(user=self.user).delete()
        EmailAddress.objects.create(
            user=self.user,
            email="diego@example.com",
            verified=False,
            primary=False,
        )

        response = self.client.post(
            reverse("account_email"),
            {
                "email": "diego@example.com",
                "action_send": "1",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(mail.outbox), 1)
