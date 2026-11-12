from django import forms
from django.contrib.auth.password_validation import validate_password
from .models import User, TeamInvitation
from organizations.models import Organization

class SignupForm(forms.Form):
    business_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control form-control-lg", "placeholder": "Acme Inc.", "required": True}),
        label="Business Name",
    )
    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={"class": "form-control form-control-lg", "placeholder": "Jane", "required": True}),
        label="First Name",
    )
    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={"class": "form-control form-control-lg", "placeholder": "Doe", "required": True}),
        label="Last Name",
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-control form-control-lg", "placeholder": "jane@example.com", "required": True}),
        label="Work Email",
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control form-control-lg", "placeholder": "••••••••", "required": True}),
        label="Password",
    )

    def clean_email(self):
        email = self.cleaned_data.get("email", "").lower().strip()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get("password")
        validate_password(password)
        return password


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-control form-control-lg", "placeholder": "you@example.com", "required": True}),
        label="Email Address",
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control form-control-lg", "placeholder": "••••••••", "required": True}),
        label="Password",
    )


class TeamInviteForm(forms.ModelForm):
    class Meta:
        model = TeamInvitation
        fields = ["email", "role"]
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "colleague@example.com", "required": True}),
            "role": forms.Select(attrs={"class": "form-select", "required": True}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization

    def clean_email(self):
        email = self.cleaned_data.get("email", "").lower().strip()
        if self.organization and User.objects.filter(organization=self.organization, email=email).exists():
            raise forms.ValidationError("This user is already a member of your organization.")
        return email


class AcceptInviteForm(forms.Form):
    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={"class": "form-control form-control-lg", "placeholder": "Alex", "required": True}),
        label="First Name",
    )
    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={"class": "form-control form-control-lg", "placeholder": "Taylor", "required": True}),
        label="Last Name",
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control form-control-lg", "placeholder": "••••••••", "required": True}),
        label="Set Password",
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control form-control-lg", "placeholder": "••••••••", "required": True}),
        label="Confirm Password",
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm = cleaned_data.get("confirm_password")
        if password and confirm and password != confirm:
            self.add_error("confirm_password", "Passwords do not match.")
        if password:
            validate_password(password)
        return cleaned_data
