import uuid

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('iot', '0015_bletrackingsettings_blebeacon_blereceiver_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='GoatWeightMeasurement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('weight_kg', models.DecimalField(decimal_places=2, help_text='Confirmed goat weight in kilograms (0.1 to 300 kg)', max_digits=6, validators=[django.core.validators.MinValueValidator(0.1), django.core.validators.MaxValueValidator(300)])),
                ('source', models.CharField(choices=[('load_cell', 'Load Cell'), ('manual', 'Manual')], max_length=20)),
                ('measured_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('recorded_at', models.DateTimeField(auto_now_add=True)),
                ('device_id', models.CharField(blank=True, max_length=100)),
                ('request_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('goat', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='weight_measurements', to='iot.goat')),
                ('recorded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recorded_goat_weights', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-measured_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='goatweightmeasurement',
            index=models.Index(fields=['goat', '-measured_at'], name='iot_goatwei_goat_id_a91172_idx'),
        ),
        migrations.AddIndex(
            model_name='goatweightmeasurement',
            index=models.Index(fields=['source', '-measured_at'], name='iot_goatwei_source_f0bb39_idx'),
        ),
    ]
