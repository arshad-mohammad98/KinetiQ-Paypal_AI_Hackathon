from .models import AuditLog

def log_audit(request, action_type, instance=None, target_model="", target_id="", description=""):
    """
    Records actions in the centralized AuditLog table, strictly isolated by organization_id.
    """
    ip = request.META.get("HTTP_X_FORWARDED_FOR")
    if ip:
        ip = ip.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "")

    if instance is not None:
        target_model = instance.__class__.__name__
        target_id = str(instance.pk)

    AuditLog.objects.create(
        organization=request.user.organization,
        user=request.user if request.user.is_authenticated else None,
        action_type=action_type,
        target_model=target_model,
        target_id=target_id,
        ip_address=ip or None,
        description=description or f"{action_type} {target_model}: {target_id}",
    )
