from django import forms
from django.contrib.auth import get_user_model
from .models import Company, Contact, ContactNote, Deal, Stage, Task

User = get_user_model()

class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ["name", "industry", "website", "city", "phone"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control form-control-lg", "placeholder": "e.g. Acme Corp", "required": True}),
            "industry": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Technology, Retail"}),
            "website": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://example.com"}),
            "city": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. New York, London"}),
            "phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "+1 555-0199"}),
        }


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ["first_name", "last_name", "email", "phone", "job_title", "company", "status", "owner"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "First Name", "required": True}),
            "last_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Last Name"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "name@company.com", "required": True}),
            "phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "+1 555-0199"}),
            "job_title": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. VP of Sales"}),
            "company": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        if organization:
            # Strictly scope dropdowns to current organization only
            self.fields["company"].queryset = Company.objects.filter(organization=organization)
            self.fields["company"].empty_label = "-- No Company (Individual) --"
            self.fields["owner"].queryset = User.objects.filter(organization=organization, is_active=True)
            self.fields["owner"].empty_label = "-- Unassigned --"

    def clean_company(self):
        company = self.cleaned_data.get("company")
        if company and self.organization and company.organization_id != self.organization.id:
            raise forms.ValidationError("A contact can only be linked to a company in its own business.")
        return company

    def clean_owner(self):
        owner = self.cleaned_data.get("owner")
        if owner and self.organization and owner.organization_id != self.organization.id:
            raise forms.ValidationError("A contact can only be assigned to a team member in its own business.")
        return owner


class DealForm(forms.ModelForm):
    class Meta:
        model = Deal
        fields = ["title", "value", "contact", "stage", "expected_close_date", "owner"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control form-control-lg", "placeholder": "e.g. Enterprise License Deal", "required": True}),
            "value": forms.NumberInput(attrs={"class": "form-control", "placeholder": "0.00", "step": "0.01", "min": "0"}),
            "contact": forms.Select(attrs={"class": "form-select", "required": True}),
            "stage": forms.Select(attrs={"class": "form-select", "required": True}),
            "expected_close_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
        }
        labels = {
            "value": "Value ($ USD)",
            "expected_close_date": "Expected Close Date",
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        if organization:
            contact_qs = Contact.objects.filter(organization=organization).select_related("company")
            self.fields["contact"].queryset = contact_qs
            if not contact_qs.exists():
                self.fields["contact"].empty_label = "-- No Contacts in Business (Add Contact First) --"
            else:
                self.fields["contact"].empty_label = "-- Select Contact (Required) --"
            self.fields["stage"].queryset = Stage.objects.filter(organization=organization).order_by("order")
            self.fields["stage"].empty_label = "-- Select Stage (Required) --"
            self.fields["owner"].queryset = User.objects.filter(organization=organization, is_active=True).order_by("first_name", "last_name")
            self.fields["owner"].empty_label = "-- Unassigned --"

    def clean_contact(self):
        contact = self.cleaned_data.get("contact")
        if not contact:
            raise forms.ValidationError("Contact is required.")
        if self.organization and contact.organization_id != self.organization.id:
            raise forms.ValidationError("A deal can only use a contact from its own business.")
        return contact

    def clean_stage(self):
        stage = self.cleaned_data.get("stage")
        if not stage:
            raise forms.ValidationError("Stage is required.")
        if self.organization and stage.organization_id != self.organization.id:
            raise forms.ValidationError("A deal can only use stages from its own business.")
        return stage

    def clean_owner(self):
        owner = self.cleaned_data.get("owner")
        if owner and self.organization and owner.organization_id != self.organization.id:
            raise forms.ValidationError("A deal can only be assigned to a team member in its own business.")
        return owner


class ContactNoteForm(forms.ModelForm):
    class Meta:
        model = ContactNote
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Add a note regarding this contact (call summary, meeting notes, etc.)...",
                "required": True,
            }),
        }
        labels = {
            "content": "Add Note",
        }


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "task_type", "due_date", "due_time", "contact", "deal", "assigned_to", "notes"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control form-control-lg",
                "placeholder": "e.g. Follow-up phone call regarding proposal",
                "required": True,
            }),
            "task_type": forms.Select(attrs={"class": "form-select", "required": True}),
            "due_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "due_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "contact": forms.Select(attrs={"class": "form-select"}),
            "deal": forms.Select(attrs={"class": "form-select"}),
            "assigned_to": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Context, agenda, discussion points, or next steps...",
            }),
        }
        labels = {
            "title": "Task Title",
            "task_type": "Type",
            "due_date": "Due Date",
            "due_time": "Due Time (Optional)",
            "contact": "Linked Contact (Optional)",
            "deal": "Linked Deal (Optional)",
            "assigned_to": "Assigned To",
            "notes": "Notes",
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        if organization:
            self.fields["contact"].queryset = Contact.objects.filter(organization=organization).order_by("first_name", "last_name")
            self.fields["contact"].empty_label = "-- Select Contact (Optional) --"
            self.fields["deal"].queryset = Deal.objects.filter(organization=organization).order_by("title")
            self.fields["deal"].empty_label = "-- Select Deal (Optional) --"
            self.fields["assigned_to"].queryset = User.objects.filter(organization=organization, is_active=True).order_by("first_name", "last_name")
            self.fields["assigned_to"].empty_label = "-- Unassigned --"

    def clean_contact(self):
        contact = self.cleaned_data.get("contact")
        if contact and self.organization and contact.organization_id != self.organization.id:
            raise forms.ValidationError("A task can only link to contacts from its own business.")
        return contact

    def clean_deal(self):
        deal = self.cleaned_data.get("deal")
        if deal and self.organization and deal.organization_id != self.organization.id:
            raise forms.ValidationError("A task can only link to deals from its own business.")
        return deal

    def clean_assigned_to(self):
        assigned_to = self.cleaned_data.get("assigned_to")
        if assigned_to and self.organization and assigned_to.organization_id != self.organization.id:
            raise forms.ValidationError("A task can only be assigned to a team member in its own business.")
        return assigned_to

    def clean(self):
        cleaned_data = super().clean()
        deal = cleaned_data.get("deal")
        # If task is linked to a deal, its contact is taken from the deal
        if deal and deal.contact:
            cleaned_data["contact"] = deal.contact
        return cleaned_data
