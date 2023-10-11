# Generated by Django 4.0.5 on 2023-10-05 14:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0073_prototransaction_monthly_earn_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='record',
            name='raw_data_line',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='record',
            name='raw_data_line_hash',
            field=models.CharField(max_length=32, null=True),
        ),
        migrations.AddField(
            model_name='recordmeta',
            name='raw_data_line_hash',
            field=models.CharField(max_length=32, null=True),
        ),
    ]
