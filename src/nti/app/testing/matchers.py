#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from nti.testing.matchers import BoolMatcher

__test__ = False

logger = __import__('logging').getLogger(__name__)


class HasPermission(BoolMatcher):

    def __init__(self, value, permission, request):
        super(HasPermission, self).__init__(value)
        self.request = request
        self.permission = permission

    def _matches(self, item):
        return super(HasPermission, self)._matches(
            self.request.has_permission(self.permission, item)
        )


def has_permission(permission, request):
    return HasPermission(True, permission, request)


def doesnt_have_permission(permission, request):
    return HasPermission(False, permission, request)
