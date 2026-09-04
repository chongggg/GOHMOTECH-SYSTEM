from django.db import migrations


INDEX_NAME = "gohmotech_unique_account_email"
TABLE_NAME = "account_emailaddress"


def add_unique_email_index(apps, schema_editor):
    """Enforce one normalized allauth email identity at the database level.

    django-allauth uses conditional unique constraints for verified addresses,
    which MySQL does not support. GoHMotech uses ACCOUNT_UNIQUE_EMAIL, so a full
    unique index is both stricter and consistent with the application policy.
    """
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, TABLE_NAME)
        if INDEX_NAME in constraints:
            return
    quote = schema_editor.quote_name
    schema_editor.execute(
        f"CREATE UNIQUE INDEX {quote(INDEX_NAME)} "
        f"ON {quote(TABLE_NAME)} ({quote('email')})"
    )


def remove_unique_email_index(apps, schema_editor):
    connection = schema_editor.connection
    quote = schema_editor.quote_name
    if connection.vendor == "mysql":
        sql = (
            f"DROP INDEX {quote(INDEX_NAME)} "
            f"ON {quote(TABLE_NAME)}"
        )
    else:
        sql = f"DROP INDEX {quote(INDEX_NAME)}"
    schema_editor.execute(sql)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("marketplace", "0003_seed_allauth_email_addresses"),
    ]

    operations = [
        migrations.RunPython(add_unique_email_index, remove_unique_email_index),
    ]
