# Generated by Django 4.0.5 on 2023-10-10 19:16

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0078_remove_prototransaction_monthly_earn_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='prototransaction',
            name='is_active',
        ),
    ]
