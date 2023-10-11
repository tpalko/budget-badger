# Generated by Django 4.0.5 on 2023-10-11 02:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0079_remove_prototransaction_is_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='prototransaction',
            name='criticality',
            field=models.CharField(choices=[['flexible', 'Flexible'], ['necessary', 'Necessary'], ['optional', 'Optional']], default='optional', max_length=20),
        ),
    ]
