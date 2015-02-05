# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django_pgjson.fields


class Migration(migrations.Migration):

    dependencies = [
        ('userstories', '0009_remove_userstory_is_archived'),
    ]

    operations = [
        migrations.AddField(
            model_name='userstory',
            name='custom_attributes',
            field=django_pgjson.fields.JsonField(blank=True, null=True, default=None, verbose_name='custom attributes'),
            preserve_default=True,
        ),
    ]
