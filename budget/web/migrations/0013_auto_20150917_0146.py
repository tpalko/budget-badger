# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0012_auto_20150916_0521'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='transaction_type',
            field=models.CharField(default=b'debt', max_length=50, choices=[(b'income', b'Income'), (b'utility', b'Utility'), (b'debt', b'Debut')]),
        ),
        migrations.AlterField(
            model_name='recurringtransaction',
            name='started_at',
            field=models.DateField(default=datetime.datetime(2015, 9, 17, 1, 46, 18, 442992), null=True, blank=True),
        ),
    ]
