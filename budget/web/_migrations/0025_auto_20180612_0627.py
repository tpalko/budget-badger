# -*- coding: utf-8 -*-
# Generated by Django 1.9 on 2018-06-12 06:27
from __future__ import unicode_literals

import autoslug.fields
from django.db import migrations


def migrate_data_forward(apps, schema_editor):
    Transaction = apps.get_model('web', 'Transaction')
    for instance in Transaction.objects.all():
        instance.save()


def migrate_data_backward(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('web', '0024_transaction_slug'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaction',
            name='slug',
            field=autoslug.fields.AutoSlugField(default=None, editable=False, populate_from=b'name', unique=False),
        ),
        migrations.RunPython(
            migrate_data_forward,
            migrate_data_backward
        ),
    ]
