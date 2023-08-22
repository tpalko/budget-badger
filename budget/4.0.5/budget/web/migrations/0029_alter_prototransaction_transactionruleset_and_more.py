# Generated by Django 4.0.5 on 2022-09-28 19:29

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0028_prototransaction_stats'),
    ]

    operations = [
        migrations.AlterField(
            model_name='prototransaction',
            name='transactionruleset',
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='prototransaction', to='web.transactionruleset'),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='prototransaction',
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='transaction', to='web.prototransaction'),
        ),
    ]