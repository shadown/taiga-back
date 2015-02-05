# Copyright (C) 2015 Andrey Antukh <niwi@niwi.be>
# Copyright (C) 2015 Jesús Espino <jespinog@gmail.com>
# Copyright (C) 2015 David Barragán <bameda@dbarragan.com>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from django.utils.translation import ugettext_lazy as _

from rest_framework.serializers import ValidationError

from taiga.base.serializers import JsonField
from taiga.projects.custom_attributes import models


class BaseCustomAttributeValuesSerializerMixin:
    custom_attributes = JsonField(required=False)

    def validate_custom_attributes(self, attrs, source):
        data_custom_attributes = attrs.get("custom_attributes", None)
        data_project = attrs.get("project", None)

        if self.object:
            data_custom_attributes = data_custom_attributes or self.object.custom_attributes
            data_project = data_project or self.object.project

        if data_custom_attributes:
            if type(data_custom_attributes) is not dict:
                raise ValidationError(_("Invalid content. It must be {\"key\": \"value\",...}"))

            custom_attributes_ids = list(data_custom_attributes.keys())
            qs = self._custom_attribute_model.objects.filter(project=data_project, id__in=custom_attributes_ids)
            if qs.count() != len(ids):
                raise ValidationError(_("It's contain invalid custom fields."))

        return attrs


class UserStoryCustomAttributeValuesSerializerMixin(BaseCustomAttributeValuesSerializerMixin):
    _custom_attribute_model = models.UserStoryCustomAttribute


class TaskCustomAttributeValuesSerializerMixin(BaseCustomAttributeValuesSerializerMixin):
    _custom_attribute_model = models.TaskCustomAttribute


class IssueCustomAttributeValuesSerializerMixin(BaseCustomAttributeValuesSerializerMixin):
    _custom_attribute_model = models.IssueCustomAttribute
