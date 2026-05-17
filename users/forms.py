from django import forms
from django.contrib.auth import get_user_model
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from settings.models import UserSettings

User = get_user_model()


class ProfileForm(forms.ModelForm):
    remove_avatar = forms.BooleanField(required=False, label="Remove current avatar")

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "avatar"]
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Username",
                    "maxlength": "150",
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "First name",
                    "maxlength": "150",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Last name",
                    "maxlength": "150",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Email address",
                    "maxlength": "254",
                }
            ),
            "avatar": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": "image/png,image/jpeg,image/webp,image/gif",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["avatar"].required = False
        self.fields["avatar"].widget.attrs.update(
            {
                "data-profile-avatar-input": "true",
                "aria-describedby": "avatar-help-text",
            }
        )
        self.fields["remove_avatar"].widget.attrs.update(
            {
                "class": "form-check-input",
                "data-profile-remove-avatar": "true",
            }
        )
        self.fields["remove_avatar"].initial = False

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise forms.ValidationError("Username is required.")
        if User.objects.filter(username__iexact=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This username is already in use.")
        return username

    def clean_first_name(self):
        return (self.cleaned_data.get("first_name") or "").strip()

    def clean_last_name(self):
        return (self.cleaned_data.get("last_name") or "").strip()

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        if not email:
            return email

        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This email is already in use by another account.")
        return email

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        uploaded_avatar = self.files.get(self.add_prefix("avatar"))
        if not avatar or not uploaded_avatar:
            return avatar

        content_type = (getattr(avatar, "content_type", "") or "").lower()
        allowed_content_types = {
            "image/png",
            "image/jpeg",
            "image/jpg",
            "image/webp",
            "image/gif",
        }
        if content_type and content_type not in allowed_content_types:
            raise forms.ValidationError("Avatar must be PNG, JPG, WEBP or GIF.")

        lower_name = (avatar.name or "").lower()
        allowed_extensions = (".png", ".jpg", ".jpeg", ".webp", ".gif")
        if not lower_name.endswith(allowed_extensions):
            raise forms.ValidationError("Avatar file extension must be PNG, JPG, WEBP or GIF.")

        max_size = 3 * 1024 * 1024
        if avatar.size > max_size:
            raise forms.ValidationError("Avatar size must be 3MB or less.")

        return avatar

    def clean(self):
        cleaned_data = super().clean()
        uploaded_avatar = self.files.get(self.add_prefix("avatar"))
        if uploaded_avatar and cleaned_data.get("remove_avatar"):
            self.add_error("avatar", "Choose either a new avatar or remove the current one, not both.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        remove_avatar = self.cleaned_data.get("remove_avatar")
        if remove_avatar and instance.avatar:
            instance.avatar.delete(save=False)
            instance.avatar = None

        if commit:
            instance.save()
        return instance


class ProfilePreferencesForm(forms.ModelForm):
    COMMON_TIMEZONE_CHOICES = [
        ("Europe/Brussels", "Europe/Brussels"),
        ("Europe/Madrid", "Europe/Madrid"),
        ("Europe/London", "Europe/London"),
        ("UTC", "UTC"),
        ("America/New_York", "America/New_York"),
        ("America/Chicago", "America/Chicago"),
        ("America/Denver", "America/Denver"),
        ("America/Los_Angeles", "America/Los_Angeles"),
        ("America/Mexico_City", "America/Mexico_City"),
        ("America/Bogota", "America/Bogota"),
        ("America/Lima", "America/Lima"),
        ("America/Sao_Paulo", "America/Sao_Paulo"),
        ("Asia/Dubai", "Asia/Dubai"),
        ("Asia/Singapore", "Asia/Singapore"),
        ("Asia/Tokyo", "Asia/Tokyo"),
    ]

    timezone = forms.ChoiceField(
        choices=COMMON_TIMEZONE_CHOICES,
        error_messages={"invalid_choice": "Choose a valid time zone."},
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = UserSettings
        fields = ["language_code", "timezone"]
        widgets = {
            "language_code": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_timezone = (self.instance.timezone or "").strip()
        available_values = {choice[0] for choice in self.fields["timezone"].choices}
        if current_timezone and current_timezone not in available_values:
            self.fields["timezone"].choices = [
                (current_timezone, current_timezone),
                *self.fields["timezone"].choices,
            ]

    def clean_timezone(self):
        timezone_name = (self.cleaned_data.get("timezone") or "").strip()
        if not timezone_name:
            raise forms.ValidationError("Time zone is required.")

        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise forms.ValidationError("Choose a valid time zone.") from exc

        return timezone_name
