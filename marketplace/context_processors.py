from .auth import is_marketplace_buyer


def marketplace_role(request):
    return {"is_marketplace_buyer": is_marketplace_buyer(request.user)}

