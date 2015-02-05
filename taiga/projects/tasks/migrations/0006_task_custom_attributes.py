# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django_pgjson.fields


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0005_auto_20150114_0954'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='custom_attributes',
            field=django_pgjson.fields.JsonField(default=None, null=True, blank=True, verbose_name='custom attributes'),
            preserve_default=True,
        ),
    ]
