# Generated by Django 4.0.5 on 2023-08-31 23:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0050_remove_record_record_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='recordmeta',
            name='detailed_description',
            field=models.TextField(blank=True),
        ),
    ]
