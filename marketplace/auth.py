BUYER_GROUP_NAME = "Marketplace Buyers"


def is_marketplace_buyer(user):
    return bool(
        getattr(user, "is_authenticated", False)
        and user.groups.filter(name=BUYER_GROUP_NAME).exists()
    )

