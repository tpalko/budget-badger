# Generated by Django 4.0.5 on 2022-09-14 05:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0020_alter_record_account_type_alter_record_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='account_number',
            field=models.CharField(max_length=50, null=True),
        ),
    ]