# Copyright (C) 2014 Andrey Antukh <niwi@niwi.be>
# Copyright (C) 2014 Jesús Espino <jespinog@gmail.com>
# Copyright (C) 2014 David Barragán <bameda@dbarragan.com>
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

import json
import codecs
import uuid

from rest_framework.response import Response
from rest_framework.decorators import throttle_classes
from rest_framework import status

from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.db.transaction import atomic
from django.db.models import signals
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from taiga.base.api.mixins import CreateModelMixin
from taiga.base.api.viewsets import GenericViewSet
from taiga.base.decorators import detail_route, list_route
from taiga.base import exceptions as exc
from taiga.projects.models import Project, Membership
from taiga.projects.issues.models import Issue
from taiga.projects.serializers import ProjectSerializer

from . import mixins
from . import serializers
from . import service
from . import permissions
from . import tasks
from . import dump_service
from . import throttling
from .renderers import ExportRenderer

from taiga.base.api.utils import get_object_or_404


class ProjectExporterViewSet(mixins.ImportThrottlingPolicyMixin, GenericViewSet):
    model = Project
    permission_classes = (permissions.ImportExportPermission, )

    def retrieve(self, request, pk, *args, **kwargs):
        throttle = throttling.ImportDumpModeRateThrottle()

        if not throttle.allow_request(request, self):
            self.throttled(request, throttle.wait())

        project = get_object_or_404(self.get_queryset(), pk=pk)
        self.check_permissions(request, 'export_project', project)

        if settings.CELERY_ENABLED:
            task = tasks.dump_project.delay(request.user, project)
            tasks.delete_project_dump.apply_async((project.pk, project.slug), countdown=settings.EXPORTS_TTL)
            return Response({"export_id": task.id}, status=status.HTTP_202_ACCEPTED)

        path = "exports/{}/{}-{}.json".format(project.pk, project.slug, uuid.uuid4().hex)
        content = ContentFile(ExportRenderer().render(service.project_to_dict(project),
            renderer_context={"indent": 4}).decode('utf-8'))

        default_storage.save(path, content)
        response_data = {
            "url": default_storage.url(path)
        }
        return Response(response_data, status=status.HTTP_200_OK)


class ProjectImporterViewSet(mixins.ImportThrottlingPolicyMixin, CreateModelMixin, GenericViewSet):
    model = Project
    permission_classes = (permissions.ImportExportPermission, )

    @method_decorator(atomic)
    def create(self, request, *args, **kwargs):
        self.check_permissions(request, 'import_project', None)

        data = request.DATA.copy()
        data['owner'] = data.get('owner', request.user.email)

        project_serialized = service.store_project(data)

        if project_serialized is None:
            raise exc.BadRequest(service.get_errors())

        if "points" in data:
            service.store_choices(project_serialized.object, data,
                                  "points", serializers.PointsExportSerializer)
        if "issue_types" in data:
            service.store_choices(project_serialized.object, data,
                                  "issue_types",
                                  serializers.IssueTypeExportSerializer)
        if "issue_statuses" in data:
            service.store_choices(project_serialized.object, data,
                                  "issue_statuses",
                                  serializers.IssueStatusExportSerializer,)
        if "us_statuses" in data:
            service.store_choices(project_serialized.object, data,
                                  "us_statuses",
                                  serializers.UserStoryStatusExportSerializer,)
        if "task_statuses" in data:
            service.store_choices(project_serialized.object, data,
                                  "task_statuses",
                                  serializers.TaskStatusExportSerializer)
        if "priorities" in data:
            service.store_choices(project_serialized.object, data,
                                  "priorities",
                                  serializers.PriorityExportSerializer)
        if "severities" in data:
            service.store_choices(project_serialized.object, data,
                                  "severities",
                                  serializers.SeverityExportSerializer)

        if ("points" in data or "issues_types" in data or
                "issues_statuses" in data or "us_statuses" in data or
                "task_statuses" in data or "priorities" in data or
                "severities" in data):
            service.store_default_choices(project_serialized.object, data)

        if "userstorycustomattributes" in data:
            service.store_custom_attributes(project_serialized.object, data,
                                            "userstorycustomattributes",
                                            serializers.UserStoryCustomAttributeExportSerializer)

        if "taskcustomattributes" in data:
            service.store_custom_attributes(project_serialized.object, data,
                                            "taskcustomattributes",
                                            serializers.TaskCustomAttributeExportSerializer)

        if "issuecustomattributes" in data:
            service.store_custom_attributes(project_serialized.object, data,
                                            "issuecustomattributes",
                                            serializers.IssueCustomAttributeExportSerializer)

        if "roles" in data:
            service.store_roles(project_serialized.object, data)

        if "memberships" in data:
            service.store_memberships(project_serialized.object, data)

        if project_serialized.object.memberships.filter(user=project_serialized.object.owner).count() == 0:
            if project_serialized.object.roles.all().count() > 0:
                Membership.objects.create(
                    project=project_serialized.object,
                    email=project_serialized.object.owner.email,
                    user=project_serialized.object.owner,
                    role=project_serialized.object.roles.all().first(),
                    is_owner=True
                )

        errors = service.get_errors()
        if errors:
            raise exc.BadRequest(errors)

        response_data = project_serialized.data
        response_data['id'] = project_serialized.object.id
        headers = self.get_success_headers(response_data)
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)

    @list_route(methods=["POST"])
    @method_decorator(atomic)
    def load_dump(self, request):
        throttle = throttling.ImportDumpModeRateThrottle()

        if not throttle.allow_request(request, self):
            self.throttled(request, throttle.wait())

        self.check_permissions(request, "load_dump", None)

        dump = request.FILES.get('dump', None)

        if not dump:
            raise exc.WrongArguments(_("Needed dump file"))

        reader = codecs.getreader("utf-8")

        try:
            dump = json.load(reader(dump))
        except Exception:
            raise exc.WrongArguments(_("Invalid dump format"))

        if Project.objects.filter(slug=dump['slug']).exists():
            del dump['slug']

        if settings.CELERY_ENABLED:
            task = tasks.load_project_dump.delay(request.user, dump)
            return Response({"import_id": task.id}, status=status.HTTP_202_ACCEPTED)

        project = dump_service.dict_to_project(dump, request.user.email)
        response_data = ProjectSerializer(project).data
        return Response(response_data, status=status.HTTP_201_CREATED)


    @detail_route(methods=['post'])
    @method_decorator(atomic)
    def issue(self, request, *args, **kwargs):
        project = self.get_object_or_none()
        self.check_permissions(request, 'import_item', project)

        signals.pre_save.disconnect(sender=Issue,
            dispatch_uid="set_finished_date_when_edit_issue")

        issue = service.store_issue(project, request.DATA.copy())

        errors = service.get_errors()
        if errors:
            raise exc.BadRequest(errors)

        headers = self.get_success_headers(issue.data)
        return Response(issue.data, status=status.HTTP_201_CREATED, headers=headers)

    @detail_route(methods=['post'])
    @method_decorator(atomic)
    def task(self, request, *args, **kwargs):
        project = self.get_object_or_none()
        self.check_permissions(request, 'import_item', project)

        task = service.store_task(project, request.DATA.copy())

        errors = service.get_errors()
        if errors:
            raise exc.BadRequest(errors)

        headers = self.get_success_headers(task.data)
        return Response(task.data, status=status.HTTP_201_CREATED, headers=headers)

    @detail_route(methods=['post'])
    @method_decorator(atomic)
    def us(self, request, *args, **kwargs):
        project = self.get_object_or_none()
        self.check_permissions(request, 'import_item', project)

        us = service.store_user_story(project, request.DATA.copy())

        errors = service.get_errors()
        if errors:
            raise exc.BadRequest(errors)

        headers = self.get_success_headers(us.data)
        return Response(us.data, status=status.HTTP_201_CREATED, headers=headers)

    @detail_route(methods=['post'])
    @method_decorator(atomic)
    def milestone(self, request, *args, **kwargs):
        project = self.get_object_or_none()
        self.check_permissions(request, 'import_item', project)

        milestone = service.store_milestone(project, request.DATA.copy())

        errors = service.get_errors()
        if errors:
            raise exc.BadRequest(errors)

        headers = self.get_success_headers(milestone.data)
        return Response(milestone.data, status=status.HTTP_201_CREATED, headers=headers)

    @detail_route(methods=['post'])
    @method_decorator(atomic)
    def wiki_page(self, request, *args, **kwargs):
        project = self.get_object_or_none()
        self.check_permissions(request, 'import_item', project)

        wiki_page = service.store_wiki_page(project, request.DATA.copy())

        errors = service.get_errors()
        if errors:
            raise exc.BadRequest(errors)

        headers = self.get_success_headers(wiki_page.data)
        return Response(wiki_page.data, status=status.HTTP_201_CREATED, headers=headers)

    @detail_route(methods=['post'])
    @method_decorator(atomic)
    def wiki_link(self, request, *args, **kwargs):
        project = self.get_object_or_none()
        self.check_permissions(request, 'import_item', project)

        wiki_link = service.store_wiki_link(project, request.DATA.copy())

        errors = service.get_errors()
        if errors:
            raise exc.BadRequest(errors)

        headers = self.get_success_headers(wiki_link.data)
        return Response(wiki_link.data, status=status.HTTP_201_CREATED, headers=headers)
