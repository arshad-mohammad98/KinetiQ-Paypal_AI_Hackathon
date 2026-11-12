import django.db.models.deletion
from django.db import migrations, models


def create_default_stages_for_existing_organizations(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Stage = apps.get_model("crm_core", "Stage")
    DEFAULT_STAGES = [
        {"name": "New", "order": 1, "is_won": False, "is_lost": False},
        {"name": "Contacted", "order": 2, "is_won": False, "is_lost": False},
        {"name": "Proposal", "order": 3, "is_won": False, "is_lost": False},
        {"name": "Won", "order": 4, "is_won": True, "is_lost": False},
        {"name": "Lost", "order": 5, "is_won": False, "is_lost": True},
    ]
    for org in Organization.objects.all():
        for stage_info in DEFAULT_STAGES:
            Stage.objects.get_or_create(
                organization=org,
                name=stage_info["name"],
                defaults=stage_info,
            )


def reverse_create_default_stages(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0001_initial'),
        ('crm_core', '0002_company_city_contact_owner_alter_contact_last_name_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Stage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('order', models.PositiveIntegerField(default=0)),
                ('is_won', models.BooleanField(default=False)),
                ('is_lost', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='organizations.organization')),
            ],
            options={
                'ordering': ['order', 'id'],
            },
        ),
        migrations.RunPython(
            create_default_stages_for_existing_organizations,
            reverse_code=reverse_create_default_stages,
        ),
        migrations.RemoveField(
            model_name='deal',
            name='stage',
        ),
        migrations.AddField(
            model_name='deal',
            name='stage',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='deals', to='crm_core.stage'),
        ),
        migrations.AlterField(
            model_name='deal',
            name='contact',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='deals', to='crm_core.contact'),
        ),
        migrations.AddField(
            model_name='deal',
            name='closed_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.RemoveField(
            model_name='deal',
            name='probability',
        ),
        migrations.AlterField(
            model_name='auditlog',
            name='action_type',
            field=models.CharField(
                choices=[
                    ('LOGIN', 'User Login'),
                    ('LOGOUT', 'User Logout'),
                    ('CREATE', 'Record Created'),
                    ('UPDATE', 'Record Updated'),
                    ('MOVE', 'Record Moved Stage'),
                    ('DELETE', 'Record Deleted'),
                    ('EXPORT', 'Data Exported'),
                    ('INVITE', 'Team Member Invited'),
                ],
                max_length=50,
            ),
        ),
    ]

