# Generated by Django 4.0.5 on 2023-09-20 16:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0072_tracingresults'),
    ]

    operations = [
        migrations.AddField(
            model_name='prototransaction',
            name='monthly_earn',
            field=models.DecimalField(decimal_places=2, max_digits=20, null=True),
        ),
        migrations.AddField(
            model_name='prototransaction',
            name='monthly_spend',
            field=models.DecimalField(decimal_places=2, max_digits=20, null=True),
        ),
        migrations.AlterField(
            model_name='prototransaction',
            name='timing',
            field=models.CharField(choices=[['periodic', 'Periodic'], ['chaotic_frequent', 'Chaotic_frequent'], ['chaotic_rare', 'Chaotic_rare'], ['single', 'Single']], default='single', max_length=20),
        ),
        migrations.AlterField(
            model_name='recordmeta',
            name='record_type',
            field=models.CharField(choices=[['unknown', 'Unknown'], ['refund', 'Refund'], ['gift', 'Gift'], ['earnedinterest', 'Earnedinterest'], ['sale', 'Sale'], ['income', 'Income'], ['expense', 'Expense'], ['penalty', 'Penalty'], ['internal', 'Internal']], default='unknown', max_length=15),
        ),
    ]
