from django.urls import path
from . import views

urlpatterns = [
    # Companies
    path("companies/", views.company_list_view, name="company_list"),
    path("companies/add/", views.company_create_view, name="company_create"),
    path("companies/import/", views.company_import_view, name="company_import"),
    path("companies/sample-csv/", views.company_sample_csv_view, name="company_sample_csv"),
    path("companies/import/failed-csv/", views.company_import_failed_csv_view, name="company_import_failed_csv"),
    path("companies/export/", views.company_export_view, name="company_export"),
    path("companies/<int:pk>/", views.company_detail_view, name="company_detail"),
    path("companies/<int:pk>/edit/", views.company_update_view, name="company_update"),
    path("companies/<int:pk>/delete/", views.company_delete_view, name="company_delete"),

    # Contacts
    path("contacts/", views.contact_list_view, name="contact_list"),
    path("contacts/add/", views.contact_create_view, name="contact_create"),
    path("contacts/import/", views.contact_import_view, name="contact_import"),
    path("contacts/sample-csv/", views.contact_sample_csv_view, name="contact_sample_csv"),
    path("contacts/import/failed-csv/", views.contact_import_failed_csv_view, name="contact_import_failed_csv"),
    path("contacts/export/", views.contact_export_view, name="contact_export"),
    path("contacts/<int:pk>/", views.contact_detail_view, name="contact_detail"),
    path("contacts/<int:pk>/edit/", views.contact_update_view, name="contact_update"),
    path("contacts/<int:pk>/delete/", views.contact_delete_view, name="contact_delete"),

    # Deals Pipeline
    path("deals/", views.deal_board_view, name="deal_board"),
    path("deals/pipeline/", views.deal_board_view, name="deal_pipeline"),
    path("deals/export/", views.deal_export_view, name="deal_export"),
    path("deals/add/", views.deal_create_view, name="deal_create"),
    path("deals/<int:pk>/", views.deal_detail_view, name="deal_detail"),
    path("deals/<int:pk>/edit/", views.deal_update_view, name="deal_update"),
    path("deals/<int:pk>/delete/", views.deal_delete_view, name="deal_delete"),
    path("deals/<int:pk>/move/", views.deal_move_view, name="deal_move"),

    # Tasks & Reminders
    path("tasks/", views.task_list_view, name="task_list"),
    path("tasks/export/", views.task_export_view, name="task_export"),
    path("tasks/add/", views.task_create_view, name="task_create"),
    path("tasks/<int:pk>/edit/", views.task_update_view, name="task_update"),
    path("tasks/<int:pk>/toggle-done/", views.task_toggle_done_view, name="task_toggle_done"),
    path("tasks/<int:pk>/delete/", views.task_delete_view, name="task_delete"),

    # Settings & Data Backup (Owner Only)
    path("settings/", views.settings_view, name="settings"),
    path("settings/download-all/", views.download_all_data_view, name="download_all_data"),
]
