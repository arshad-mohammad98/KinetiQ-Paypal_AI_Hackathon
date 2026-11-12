from django.urls import path
from assistant import views

urlpatterns = [
    path("chat/", views.chat_view, name="assistant_chat"),
    path("clear/", views.clear_chat_view, name="assistant_clear"),
    path("logo-preview/", views.logo_preview_view, name="logo_preview"),
]

