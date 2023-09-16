# Generated by Django 4.0.5 on 2023-09-15 06:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0063_alter_recordmeta_accounted_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='record',
            name='record_type',
            field=models.CharField(choices=[['unknown', 'Unknown'], ['refund', 'Refund'], ['income', 'Income'], ['expense', 'Expense'], ['penalty', 'Penalty'], ['internal', 'Internal']], default='unknown', max_length=15),
        ),
    ]