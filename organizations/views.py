from django.shortcuts import render, redirect

def home_view(request):
    """
    Customer-facing landing page for Kinetiq.
    Redirects authenticated users directly to the Dashboard home page.
    """
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "home.html")

def terms_view(request):
    """
    Terms of Service for Kinetiq.
    """
    return render(request, "legal/terms.html")

def privacy_view(request):
    """
    Privacy Policy for Kinetiq.
    """
    return render(request, "legal/privacy.html")
