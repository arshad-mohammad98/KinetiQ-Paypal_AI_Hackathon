from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("verification-sent/", views.verification_sent_view, name="verification_sent"),
    path("resend-verification/", views.resend_verification_view, name="resend_verification"),
    path("verify-email/<str:uidb64>/<str:token>/", views.verify_email_view, name="verify_email"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("team/", views.team_list_view, name="team_list"),
    path("invites/accept/<str:token>/", views.accept_invite_view, name="accept_invite"),

    # Password Reset Views
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset.html",
            email_template_name="accounts/password_reset_email.html",
            html_email_template_name="accounts/password_reset_email_html.html",
            subject_template_name="accounts/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset-confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset-complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]
