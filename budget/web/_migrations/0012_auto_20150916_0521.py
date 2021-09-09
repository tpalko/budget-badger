# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0011_auto_20150916_0406'),
    ]

    operations = [
        migrations.AddField(
            model_name='recurringtransaction',
            name='is_variable',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='recurringtransaction',
            name='started_at',
            field=models.DateField(default=datetime.datetime(2015, 9, 16, 5, 21, 8, 682471), null=True, blank=True),
        ),
    ]
