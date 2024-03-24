# Generated by Django 4.0.5 on 2024-03-21 04:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0084_recordmeta_tax_classification_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='recordmeta',
            name='tax_period',
            field=models.CharField(choices=[['Q1', 'Q1'], ['Q2', 'Q2'], ['Q3', 'Q3'], ['Q4', 'Q4']], max_length=10, null=True),
        ),
        migrations.AddField(
            model_name='recordmeta',
            name='tax_year',
            field=models.CharField(blank=True, max_length=10),
        ),
    ]