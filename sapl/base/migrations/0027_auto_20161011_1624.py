# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-10-11 19:24
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0026_remove_tipoautor_cria_usuario'),
    ]

    operations = [
        migrations.AlterField(
            model_name='autor',
            name='user',
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
    ]