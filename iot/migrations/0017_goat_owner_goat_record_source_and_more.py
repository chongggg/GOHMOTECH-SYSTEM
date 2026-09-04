import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def assign_existing_farm_goat_owners(apps, schema_editor):
    Goat = apps.get_model("iot", "Goat")
    MarketplaceListing = apps.get_model("marketplace", "MarketplaceListing")
    SellerProfile = apps.get_model("marketplace", "SellerProfile")
    Group = apps.get_model("auth", "Group")

    listing_owners = dict(
        MarketplaceListing.objects.values_list("goat_id", "seller_id")
    )
    primary_seller = (
        MarketplaceListing.objects.values("seller_id")
        .annotate(total=models.Count("id"))
        .order_by("-total", "seller_id")
        .values_list("seller_id", flat=True)
        .first()
    )
    if primary_seller is None:
        primary_seller = (
            SellerProfile.objects.filter(status="approved")
            .order_by("approved_at", "id")
            .values_list("user_id", flat=True)
            .first()
        )
    if primary_seller is None:
        farm_group = Group.objects.filter(name="Farm Operators").first()
        if farm_group:
            primary_seller = farm_group.user_set.order_by("id").values_list("id", flat=True).first()

    unowned_goats = Goat.objects.filter(owner__isnull=True)
    if unowned_goats.exists() and primary_seller is None:
        raise RuntimeError(
            "Existing goats require an owner, but no marketplace seller or Farm Operator exists."
        )
    for goat in unowned_goats.iterator():
        goat.owner_id = listing_owners.get(goat.pk, primary_seller)
        goat.save(update_fields=["owner"])


class Migration(migrations.Migration):
    dependencies = [
        ("iot", "0016_goatweightmeasurement"),
        ("marketplace", "0005_seller_profile"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="goat",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                help_text="Account responsible for this goat record.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="owned_goats",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="goat",
            name="record_source",
            field=models.CharField(
                choices=[
                    ("smart_farm", "GoHMoTech Smart Farm"),
                    ("community", "Community Seller"),
                ],
                db_index=True,
                default="smart_farm",
                help_text="Separates IoT-integrated farm goats from manual community records.",
                max_length=20,
            ),
        ),
        migrations.RunPython(
            assign_existing_farm_goat_owners,
            migrations.RunPython.noop,
        ),
        migrations.AddIndex(
            model_name="goat",
            index=models.Index(
                fields=["owner", "record_source"],
                name="iot_goat_owner_i_49d7b2_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="goat",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("record_source", "smart_farm"),
                    ("owner__isnull", False),
                    _connector="OR",
                ),
                name="community_goat_requires_owner",
            ),
        ),
    ]
