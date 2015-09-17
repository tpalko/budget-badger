# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0002_auto_20150910_0354'),
    ]

    operations = [
        migrations.AddField(
            model_name='period',
            name='transactions',
            field=models.ManyToManyField(to='web.Transaction', through='web.PlannedPayment'),
        ),
        migrations.AlterField(
            model_name='recurringtransaction',
            name='started_at',
            field=models.DateField(default=datetime.datetime(2015, 9, 10, 3, 58, 1, 14171)),
        ),
    ]
