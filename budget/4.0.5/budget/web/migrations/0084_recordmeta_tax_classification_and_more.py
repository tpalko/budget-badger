# Generated by Django 4.0.5 on 2024-02-16 14:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0083_account_comments_creditcard_comments_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='recordmeta',
            name='tax_classification',
            field=models.CharField(choices=[['deductible-expense', 'Deductible-expense'], ['property-county', 'Property-county'], ['property-borough', 'Property-borough'], ['property-school', 'Property-school'], ['income-federal', 'Income-federal'], ['income-state', 'Income-state'], ['income-city', 'Income-city'], ['income-local', 'Income-local'], ['transfer', 'Transfer'], ['capital-gains', 'Capital-gains']], max_length=30, null=True),
        ),
        migrations.AlterField(
            model_name='prototransaction',
            name='criticality',
            field=models.CharField(choices=[['taxes', 'Taxes'], ['necessary', 'Necessary'], ['flexible', 'Flexible'], ['optional', 'Optional']], default='optional', max_length=20),
        ),
    ]
