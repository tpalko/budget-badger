# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0005_auto_20150910_0418'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='period',
            name='available_cash',
        ),
        migrations.AddField(
            model_name='plannedpayment',
            name='balance',
            field=models.DecimalField(default=0, max_digits=20, decimal_places=2),
        ),
        migrations.AddField(
            model_name='transaction',
            name='interest_rate',
            field=models.DecimalField(default=0, max_digits=5, decimal_places=2),
        ),
        migrations.AddField(
            model_name='transaction',
            name='isdebt',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='recurringtransaction',
            name='started_at',
            field=models.DateField(default=datetime.datetime(2015, 9, 10, 5, 56, 22, 702533)),
        ),
    ]
