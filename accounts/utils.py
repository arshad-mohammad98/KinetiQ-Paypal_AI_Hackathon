from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

def send_verification_email(request, user):
    """
    Sends an email verification link to a newly registered user.
    Prints to console in development.
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    verify_url = request.build_absolute_uri(
        reverse("verify_email", kwargs={"uidb64": uid, "token": token})
    )

    subject = "Verify your email for KinetiQ"
    message = (
        f"Hi {user.first_name},\n\n"
        f"Welcome to KinetiQ! Please verify your email address by clicking the link below:\n\n"
        f"{verify_url}\n\n"
        f"This link will expire in 24 hours.\n\n"
        f"— The KinetiQ Team"
    )
    html_message = (
        f'<div style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif; max-width: 540px; margin: 0 auto; padding: 32px 24px; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0;">'
        f'  <div style="margin-bottom: 24px;">'
        f'    <span style="font-size: 26px; font-weight: 700; color: #0f172a; text-decoration: none; letter-spacing: -0.5px;">Kineti<span style="font-size: 36px; font-weight: 800; color: #4f46e5; vertical-align: -2px; line-height: 0.85;">Q</span></span>'
        f'  </div>'
        f'  <h2 style="font-size: 20px; font-weight: 700; color: #0f172a; margin-bottom: 16px;">Verify your email address</h2>'
        f'  <p style="font-size: 15px; color: #475569; line-height: 1.6; margin-bottom: 24px;">'
        f'    Hi {user.first_name}, welcome to KinetiQ! Please verify your email address to activate your account and start your 14-day free trial.'
        f'  </p>'
        f'  <div style="margin-bottom: 24px;">'
        f'    <a href="{verify_url}" style="background-color: #4f46e5; color: #ffffff; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; display: inline-block;">'
        f'      Verify Email Address'
        f'    </a>'
        f'  </div>'
        f'  <p style="font-size: 13px; color: #94a3b8; line-height: 1.5; margin-bottom: 24px;">'
        f'    This link will expire in 24 hours. If the button above doesn\'t work, copy and paste this link into your browser:<br>'
        f'    <a href="{verify_url}" style="color: #4f46e5; word-break: break-all;">{verify_url}</a>'
        f'  </p>'
        f'  <div style="border-top: 1px solid #f1f5f9; padding-top: 16px; font-size: 13px; color: #64748b;">'
        f'    — The KinetiQ Team'
        f'  </div>'
        f'</div>'
    )

    send_mail(
        subject=subject,
        message=message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
    return verify_url


def send_invitation_email(request, invitation):
    """
    Sends a team invitation link to the invited user.
    """
    invite_url = request.build_absolute_uri(
        reverse("accept_invite", kwargs={"token": invitation.token})
    )

    subject = f"You have been invited to join {invitation.organization.name} on KinetiQ"
    message = (
        f"Hello,\n\n"
        f"You have been invited to join {invitation.organization.name} as a {invitation.get_role_display()}.\n\n"
        f"Click the link below to accept the invitation and set up your account:\n\n"
        f"{invite_url}\n\n"
        f"This invitation will expire in 7 days.\n\n"
        f"— The KinetiQ Team"
    )
    html_message = (
        f'<div style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif; max-width: 540px; margin: 0 auto; padding: 32px 24px; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0;">'
        f'  <div style="margin-bottom: 24px;">'
        f'    <span style="font-size: 26px; font-weight: 700; color: #0f172a; text-decoration: none; letter-spacing: -0.5px;">Kineti<span style="font-size: 36px; font-weight: 800; color: #4f46e5; vertical-align: -2px; line-height: 0.85;">Q</span></span>'
        f'  </div>'
        f'  <h2 style="font-size: 20px; font-weight: 700; color: #0f172a; margin-bottom: 16px;">Team Invitation</h2>'
        f'  <p style="font-size: 15px; color: #475569; line-height: 1.6; margin-bottom: 24px;">'
        f'    Hello, you have been invited to join <strong>{invitation.organization.name}</strong> on KinetiQ as a {invitation.get_role_display()}.'
        f'  </p>'
        f'  <div style="margin-bottom: 24px;">'
        f'    <a href="{invite_url}" style="background-color: #4f46e5; color: #ffffff; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; display: inline-block;">'
        f'      Accept Invitation'
        f'    </a>'
        f'  </div>'
        f'  <p style="font-size: 13px; color: #94a3b8; line-height: 1.5; margin-bottom: 24px;">'
        f'    This invitation will expire in 7 days. If the button above doesn\'t work, copy and paste this link into your browser:<br>'
        f'    <a href="{invite_url}" style="color: #4f46e5; word-break: break-all;">{invite_url}</a>'
        f'  </p>'
        f'  <div style="border-top: 1px solid #f1f5f9; padding-top: 16px; font-size: 13px; color: #64748b;">'
        f'    — The KinetiQ Team'
        f'  </div>'
        f'</div>'
    )

    send_mail(
        subject=subject,
        message=message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.email],
        fail_silently=False,
    )
    return invite_url
