"""
Template context processors for the security app.

Exposes a live unread-notification count so the header bell badge reflects
reality instead of a hard-coded number. Kept intentionally cheap (a single
COUNT query, and only for authenticated users).
"""


def notifications(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {'nav_unread_count': 0}

    try:
        from .services import unread_count
        return {'nav_unread_count': unread_count()}
    except Exception:
        # Never let a context processor break page rendering (e.g. before the
        # security tables have been migrated).
        return {'nav_unread_count': 0}
