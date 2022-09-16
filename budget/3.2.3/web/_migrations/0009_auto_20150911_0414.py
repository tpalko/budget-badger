# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0008_auto_20150911_0405'),
    ]

    operations = [
        migrations.RenameField(
            model_name='transaction',
            old_name='isdebt',
            new_name='is_debt',
        ),
        migrations.AlterField(
            model_name='recurringtransaction',
            name='started_at',
            field=models.DateField(default=datetime.datetime(2015, 9, 11, 4, 14, 42, 654654), blank=True),
        ),
    ]
