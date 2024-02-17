# Generated by Django 4.0.5 on 2023-12-16 01:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0082_remove_prototransaction_period'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='comments',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='creditcard',
            name='comments',
            field=models.TextField(null=True),
        ),
        migrations.AlterField(
            model_name='prototransaction',
            name='criticality',
            field=models.CharField(choices=[['necessary', 'Necessary'], ['flexible', 'Flexible'], ['optional', 'Optional']], default='optional', max_length=20),
        ),
    ]
