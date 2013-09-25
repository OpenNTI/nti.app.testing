#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.testing.matchers import BoolMatcher

from pyramid.security import has_permission as _p_has_permission

class HasPermission(BoolMatcher):

	def __init__( self, value, permission, request ):
		super(HasPermission,self).__init__( value )
		self.permission = permission
		self.request = request

	def _matches(self, item):
		return super(HasPermission,self)._matches(
			_p_has_permission( self.permission, item, self.request ) )

def has_permission( permission, request ):
	return HasPermission(True, permission, request)

def doesnt_have_permission( permission, request ):
	return HasPermission(False, permission, request)
