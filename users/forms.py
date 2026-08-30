from django import forms
from django.contrib.auth import get_user_model
from PIL import Image, UnidentifiedImageError
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from settings.models import UserSettings

User = get_user_model()

AVATAR_FORMAT_EXTENSIONS = {
    "PNG": {".png"},
    "JPEG": {".jpg", ".jpeg"},
    # Some phones store an additional depth/alternate image in an otherwise
    # browser-compatible JPEG. Pillow identifies those files as MPO.
    "MPO": {".jpg", ".jpeg"},
    "WEBP": {".webp"},
    "GIF": {".gif"},
}


def is_supported_avatar_format(image_format, filename):
    extensions = AVATAR_FORMAT_EXTENSIONS.get((image_format or "").upper())
    lower_name = (filename or "").lower()
    return bool(extensions and any(lower_name.endswith(ext) for ext in extensions))


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

        lower_name = (avatar.name or "").lower()
        allowed_extensions = (".png", ".jpg", ".jpeg", ".webp", ".gif")
        if not lower_name.endswith(allowed_extensions):
            raise forms.ValidationError("Avatar file extension must be PNG, JPG, WEBP or GIF.")

        max_size = 3 * 1024 * 1024
        if avatar.size > max_size:
            raise forms.ValidationError("Avatar size must be 3MB or less.")

        try:
            avatar.seek(0)
            image = Image.open(avatar)
            image.verify()
            if not is_supported_avatar_format(image.format, avatar.name):
                raise forms.ValidationError("Avatar must be PNG, JPG, WEBP or GIF.")

            avatar.seek(0)
            image = Image.open(avatar)
            if image.width > 4096 or image.height > 4096:
                raise forms.ValidationError("Avatar dimensions must not exceed 4096×4096 pixels.")
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise forms.ValidationError("Avatar is not a valid image file.") from exc
        finally:
            avatar.seek(0)

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


class AccountDeletionForm(forms.Form):
    password = forms.CharField(
        label="Current password",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "current-password"}),
    )
    confirmation = forms.CharField(
        label="Type your username to confirm",
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["confirmation"].help_text = f"Enter {user.username} exactly."

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("The password is incorrect.")
        return password

    def clean_confirmation(self):
        confirmation = self.cleaned_data["confirmation"].strip()
        if confirmation != self.user.username:
            raise forms.ValidationError("The username confirmation does not match.")
        return confirmation
