from django.apps import AppConfig


class CrmCoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'crm_core'

    def ready(self):
        import crm_core.signals
