from django.urls import path
from . import views

urlpatterns = [
    path("billing/", views.billing_view, name="billing"),
    path("invoices/", views.invoice_list_view, name="invoice_list"),
    path("deals/<int:deal_id>/invoice/send/", views.invoice_send_view, name="invoice_send"),
    path("invoices/<int:invoice_id>/refresh/", views.invoice_refresh_view, name="invoice_refresh"),
]
