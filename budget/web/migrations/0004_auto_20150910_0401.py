# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0003_auto_20150910_0358'),
    ]

    operations = [
        migrations.AddField(
            model_name='period',
            name='balance',
            field=models.DecimalField(default=0, max_digits=20, decimal_places=2),
        ),
        migrations.AlterField(
            model_name='recurringtransaction',
            name='started_at',
            field=models.DateField(default=datetime.datetime(2015, 9, 10, 4, 1, 32, 179241)),
        ),
    ]
