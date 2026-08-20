from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("iot", "0013_alter_actuationlog_result_alter_actuationlog_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="sensorreading",
            name="light_raw",
            field=models.PositiveSmallIntegerField(blank=True, help_text="Raw ESP32 ADC reading from the indoor light sensor (0-4095)", null=True, validators=[MaxValueValidator(4095)]),
        ),
        migrations.AddField(
            model_name="sensorreading",
            name="light_level_percentage",
            field=models.FloatField(blank=True, help_text="Calibrated indoor light level percentage (0-100)", null=True, validators=[MinValueValidator(0), MaxValueValidator(100)]),
        ),
        migrations.AddField(
            model_name="sensorreading",
            name="air_quality_raw",
            field=models.PositiveSmallIntegerField(blank=True, help_text="Raw ESP32 ADC reading from the MQ-135 sensor (0-4095)", null=True, validators=[MaxValueValidator(4095)]),
        ),
        migrations.AddField(
            model_name="sensorreading",
            name="air_quality_voltage",
            field=models.FloatField(blank=True, help_text="Voltage measured by the ESP32 at the MQ-135 analog input", null=True, validators=[MinValueValidator(0)]),
        ),
        migrations.AddField(
            model_name="sensorreading",
            name="air_quality_ppm",
            field=models.FloatField(blank=True, help_text="Estimated MQ-135 gas concentration after device calibration", null=True, validators=[MinValueValidator(0)]),
        ),
        migrations.AddField(
            model_name="sensorreading",
            name="air_quality_calibrated",
            field=models.BooleanField(default=False, help_text="Whether air_quality_ppm was produced using a calibrated MQ-135 R0 value"),
        ),
    ]
