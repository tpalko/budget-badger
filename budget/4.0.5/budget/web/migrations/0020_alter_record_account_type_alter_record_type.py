# Generated by Django 4.0.5 on 2022-09-14 04:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0019_record_post_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='record',
            name='account_type',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='record',
            name='type',
            field=models.CharField(max_length=255, null=True),
        ),
    ]
