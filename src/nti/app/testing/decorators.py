#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import warnings

from .webtest import TestApp
import functools
from nti.dataserver.tests import mock_dataserver

def WithSharedApplicationMockDS( *args, **kwargs ):
	"""
	Decorator for a test function using the shared application.
	Unknown keyword arguments are passed to :func:`.WithMockDS`.

	:keyword users: Either `True`, or a sequence of strings naming users. If True,
		then the standard user is created. If a sequence, then the standard user,
		followed by each named user is created. This is done by calling a method
		``_create_user`` on ``self``.
	:keyword bool default_authenticate: Only used if ``users`` was a sequence
		(and so we have created at least two users). If set to `True` (NOT the default),
		then ``self.testapp`` will be authenticated by the standard user.
	:keyword bool testapp: If True (NOT the default) then ``self.testapp`` will
		be created.
	:keyword function users_hook: If given, a function that will be called with
		a mapping {username:user} after we have created all users, in the scope
		of the transaction.
	"""

	users_to_create = kwargs.pop( 'users', None )
	if isinstance(users_to_create,basestring):
		# They forgot the comma to make a tuple
		users_to_create = (users_to_create,)
	default_authenticate = kwargs.pop( 'default_authenticate', None )
	testapp = kwargs.pop( 'testapp', None )
	if 'handle_changes' in kwargs:
		val = kwargs.pop( 'handle_changes', False )
		warnings.warn('handle_changes is always on', DeprecationWarning, stacklevel=1)
		kwargs['with_changes'] =  val # needed to get the decorator vs factory logic correct below
	user_hook = kwargs.pop( 'user_hook', None )
	users_hook = kwargs.pop( 'users_hook', None )

	if testapp:
		def _make_app(self):
			if ((users_to_create is True and default_authenticate is not False)
				or (users_to_create and default_authenticate)):
				self.testapp = TestApp( self.app, extra_environ=self._make_extra_environ() )
			else:
				self.testapp = TestApp( self.app )

	else:
		def _make_app( self ):
			pass

	if users_to_create:
		def _do_create(self):
			with mock_dataserver.mock_db_trans( self.ds ):
				base_user = self._create_user()
				self.users = { base_user.username: base_user }
				if user_hook:
					user_hook( base_user )
				if users_to_create and users_to_create is not True:
					for username in users_to_create:
						self.users[username] = self._create_user( username )
				if users_hook:
					users_hook(self.users)
	else:
		def _do_create(self):
			pass

	if len(args) == 1 and not kwargs:
		# being used as a decorator:
		# @WithSharedApplicatonMockDS
		# def test_foo(...):

		kwargs = {'base_storage': lambda self: self._storage_base}
		func = args[0]

		@functools.wraps(func)
		@mock_dataserver.WithMockDS(**kwargs)
		def f(self):
			self.config.registry._zodb_databases = { '': self.ds.db } # 0.3
			self.ds.redis.flushall()
			_do_create( self )
			_make_app( self )
			func(self)

		return f

	# Being used as a decorator factory:
	# @WithSharedApplicationMockDS(...)
	# def test_foo(...):

	# Are we in a layer that set up shared storage for us?
	kwargs['base_storage'] = lambda self: getattr(self, '_storage_base', None)
	def factory(func):
		@functools.wraps(func)
		@mock_dataserver.WithMockDS(**kwargs)
		def f(self):
			self.config.registry._zodb_databases = { '': self.ds.db } # 0.3
			self.ds.redis.flushall()
			_do_create( self )
			_make_app( self )
			if getattr(self, 'setUpDs', None):
				self.setUpDs(self.ds)
			func(self)
		return f
	return factory

def WithSharedApplicationMockDSHandleChanges( *args, **kwargs ):
	call_factory = False
	if len(args) == 1 and not kwargs:
		# Being used as a plain decorator. But we add kwargs that make
		# it look like we're being used as a factory
		call_factory = True

	kwargs['handle_changes'] = True # yes, deprecated, but necessary to ensure kwargs not empty
	if 'testapp' not in kwargs:
		kwargs['testapp'] = True
	result = WithSharedApplicationMockDS( *args, **kwargs )
	if call_factory:
		result = result(args[0])
	return result

def WithSharedApplicationMockDSWithChanges(func):
	@functools.wraps(func)
	@mock_dataserver.WithMockDS(with_changes=True)
	def f(self):
		self.config.registry._zodb_databases = { '': self.ds.db } # 0.3
		func(self)
	return f
