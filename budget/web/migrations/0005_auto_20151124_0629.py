# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0004_auto_20151124_0626'),
    ]

    operations = [
        migrations.RenameField(
            model_name='singletransaction',
            old_name='transaction_date',
            new_name='transaction_at',
        ),
        migrations.AlterField(
            model_name='recurringtransaction',
            name='started_at',
            field=models.DateField(default=datetime.datetime(2015, 11, 24, 6, 29, 55, 900592), null=True, blank=True),
        ),
    ]
