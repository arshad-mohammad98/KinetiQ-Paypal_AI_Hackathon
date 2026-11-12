from django.db.models.signals import post_save
from django.dispatch import receiver
from organizations.models import Organization
from .models import Stage

DEFAULT_STAGES = [
    {"name": "New", "order": 1, "is_won": False, "is_lost": False},
    {"name": "Contacted", "order": 2, "is_won": False, "is_lost": False},
    {"name": "Proposal", "order": 3, "is_won": False, "is_lost": False},
    {"name": "Won", "order": 4, "is_won": True, "is_lost": False},
    {"name": "Lost", "order": 5, "is_won": False, "is_lost": True},
]

def create_default_stages_for_org(org):
    stages = []
    for stage_data in DEFAULT_STAGES:
        stage, _ = Stage.all_objects.get_or_create(
            organization=org,
            name=stage_data["name"],
            defaults=stage_data,
        )
        stages.append(stage)
    return stages

@receiver(post_save, sender=Organization)
def organization_created_handler(sender, instance, created, **kwargs):
    if created:
        create_default_stages_for_org(instance)

