# Generated by Django 4.0.5 on 2022-09-12 19:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0006_transactionset_transactiontag_vehicle_property_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='csv_columns',
            field=models.CharField(max_length=1024, null=True),
        ),
    ]