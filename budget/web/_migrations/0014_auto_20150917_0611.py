# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0013_auto_20150917_0146'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='transaction',
            name='is_debt',
        ),
        migrations.AlterField(
            model_name='recurringtransaction',
            name='started_at',
            field=models.DateField(default=datetime.datetime(2015, 9, 17, 6, 11, 15, 191081), null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='transaction_type',
            field=models.CharField(default=b'debt', max_length=50, choices=[(b'income', b'Income'), (b'utility', b'Utility'), (b'debt', b'Debt')]),
        ),
    ]
