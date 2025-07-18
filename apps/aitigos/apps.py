from django.apps import AppConfig


class AitigosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.aitigos'

    def ready(self):
        import apps.aitigos.signals