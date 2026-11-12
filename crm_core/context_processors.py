from django.utils import timezone
from .models import Task

def task_reminders(request):
    """
    Supplies the count of incomplete tasks assigned to the current user
    that are overdue or due today for the top navigation reminder badge.
    """
    if hasattr(request, "user") and request.user.is_authenticated and hasattr(request.user, "organization") and request.user.organization:
        today = timezone.localdate()
        reminders_count = Task.objects.filter(
            organization=request.user.organization,
            assigned_to=request.user,
            is_completed=False,
            due_date__isnull=False,
            due_date__lte=today,
        ).count()
        return {"my_reminders_count": reminders_count}
    return {"my_reminders_count": 0}

