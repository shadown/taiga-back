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

from taiga.base.api.permissions import (PermissionComponent,
                                        AllowAny as TruePermissionComponent,
                                        DenyAll as FalsePermissionComponent)

import pytest


def test_permission_component_composition():
    assert (TruePermissionComponent() | TruePermissionComponent()).check_permissions(None, None, None)
    assert (TruePermissionComponent() | FalsePermissionComponent()).check_permissions(None, None, None)
    assert (FalsePermissionComponent() | TruePermissionComponent()).check_permissions(None, None, None)
    assert not (FalsePermissionComponent() | FalsePermissionComponent()).check_permissions(None, None, None)

    assert (TruePermissionComponent() & TruePermissionComponent()).check_permissions(None, None, None)
    assert not (TruePermissionComponent() & FalsePermissionComponent()).check_permissions(None, None, None)
    assert not (FalsePermissionComponent() & TruePermissionComponent()).check_permissions(None, None, None)
    assert not (FalsePermissionComponent() & FalsePermissionComponent()).check_permissions(None, None, None)

    assert (~FalsePermissionComponent()).check_permissions(None, None, None)
    assert not (~TruePermissionComponent()).check_permissions(None, None, None)
