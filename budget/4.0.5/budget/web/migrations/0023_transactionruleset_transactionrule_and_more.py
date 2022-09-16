# Generated by Django 4.0.5 on 2022-09-15 04:24

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0022_record_creditcardexpense'),
    ]

    operations = [
        migrations.CreateModel(
            name='TransactionRuleSet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(null=True)),
                ('join_operator', models.CharField(max_length=3, null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='TransactionRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(null=True)),
                ('record_field', models.CharField(max_length=50, null=True)),
                ('match_operator', models.CharField(max_length=20, null=True)),
                ('match_value', models.CharField(max_length=100, null=True)),
                ('transactionruleset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactionrules', to='web.transactionruleset')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='recurringtransaction',
            name='transactionruleset',
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recurringtransaction', to='web.transactionruleset'),
        ),
    ]
