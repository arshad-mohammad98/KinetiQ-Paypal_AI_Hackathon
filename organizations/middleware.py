import threading

_thread_locals = threading.local()

def set_current_organization(organization):
    _thread_locals.organization = organization

def get_current_organization():
    return getattr(_thread_locals, "organization", None)

def clear_current_organization():
    if hasattr(_thread_locals, "organization"):
        del _thread_locals.organization

class TenantMiddleware:
    """
    Middleware that captures the current authenticated user's organization
    and assigns it to thread-local storage and the request object.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and hasattr(request.user, "organization"):
            organization = request.user.organization
            set_current_organization(organization)
            request.organization = organization
        else:
            set_current_organization(None)
            request.organization = None

        response = self.get_response(request)
        clear_current_organization()
        return response
