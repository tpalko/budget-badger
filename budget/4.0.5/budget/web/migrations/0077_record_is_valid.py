# Generated by Django 4.0.5 on 2023-10-06 15:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0076_record_web_record_core_fi_26c0b3_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='record',
            name='is_valid',
            field=models.BooleanField(default=True),
        ),
    ]
