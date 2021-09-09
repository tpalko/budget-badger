# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0021_auto_20151207_0532'),
    ]

    operations = [
        migrations.CreateModel(
            name='CashTransaction',
            fields=[
                ('transaction_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='web.Transaction')),
            ],
            options={
                'abstract': False,
            },
            bases=('web.transaction', models.Model),
        ),
    ]
