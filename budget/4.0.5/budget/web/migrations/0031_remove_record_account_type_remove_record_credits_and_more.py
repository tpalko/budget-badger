# Generated by Django 4.0.5 on 2022-09-29 02:09

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0030_transactionruleset_is_auto'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='record',
            name='account_type',
        ),
        migrations.RemoveField(
            model_name='record',
            name='credits',
        ),
        migrations.RemoveField(
            model_name='record',
            name='debits',
        ),
        migrations.RemoveField(
            model_name='record',
            name='ref',
        ),
        migrations.RemoveField(
            model_name='record',
            name='type',
        ),
    ]