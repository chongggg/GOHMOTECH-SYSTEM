from django.apps import AppConfig


class SecurityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'security'
    verbose_name = 'Security & Notifications'

    def ready(self):
        # Register the Alert -> Notification bridge receivers. Import for the
        # side effect of connecting the post_save signals. Guarded so a signal
        # import problem can never prevent the app from starting.
        try:
            from importlib import import_module
            import_module('security.signals')
        except Exception:  # pragma: no cover
            import logging
            logging.getLogger(__name__).exception(
                "Failed to import security.signals; alert bridge inactive"
            )
