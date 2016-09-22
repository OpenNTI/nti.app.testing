#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Application layer test bases for defining setup.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

# disable: accessing protected members, too many methods
# pylint: disable=I0011,W0212,R0904

__test__ = False

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import assert_that
from hamcrest import described_as

from zope import component
from zope import interface

import ZODB.DemoStorage

import pyramid
from pyramid.testing import setUp as psetUp
from pyramid.testing import tearDown as ptearDown

from nti.app.pyramid_zope import z3c_zpt

from nti.dataserver import users
from nti.dataserver.tests import mock_dataserver

from nti.testing.base import ConfiguringTestBase as _ConfiguringTestBase
from nti.testing.base import SharedConfiguringTestBase as _SharedConfiguringTestBase

from .testing import TestMailDelivery
from .testing import ITestMailDelivery

import zope.deferredimport
zope.deferredimport.initialize()
zope.deferredimport.deprecatedFrom(
	"Moved to application_webtest",
	"nti.app.testing.application_webtest",
	"SharedApplicationTestBase" )

from .request_response import DummyRequest

from .matchers import has_permission, doesnt_have_permission

def _create_request( self, request_factory, request_args ):
	self.request = request_factory( *request_args )
	if request_factory is DummyRequest:
		# See the WebTest 'Framework Hooks' documentation
		self.request.environ['paste.testing'] = True
		self.request.environ['paste.testing_variables'] = {}

		if 'REQUEST_METHOD' not in self.request.environ:
			# req'd by repoze.who 2.1
			self.request.environ['REQUEST_METHOD'] = 'UNKNOWN'


class _TestBaseMixin(object):
	set_up_packages = ('nti.appserver',)
	set_up_mailer = True
	config = None
	request = None
	_ds = None

	def beginRequest( self, request_factory=DummyRequest, request_args=() ):
		_create_request( self, request_factory, request_args )
		self.config.begin( request=self.request )
		return self.request

	def get_ds(self):
		"Convenience for when you have imported mock_dataserver and used @WithMockDS/Trans"
		return self._ds or mock_dataserver.current_mock_ds

	def set_ds(self,ds):
		"setable for backwards compat"
		self._ds = ds
	ds = property( get_ds, set_ds )

	default_user_extra_interfaces = ()
	default_username = b'sjohnson@nextthought.COM'

	#: Set this to the username or NTIID of a community that users
	#: created with :meth:`_create_user` should be added to.
	default_community = None

	def _create_user(self, username=None, password='temp001', **kwargs):
		if username is None:
			# BWC with the old name if it is being set at the class level
			username = getattr(self, 'extra_environ_default_user', self.default_username).lower()
			ifaces = self.default_user_extra_interfaces
		else:
			ifaces = kwargs.pop( 'extra_interfaces', () )

		user = users.User.create_user( self.ds, username=username, password=password, **kwargs)
		interface.alsoProvides( user, ifaces )

		if self.default_community:
			comm = users.Community.get_community( self.default_community, self.ds )
			if not comm:
				comm = users.Community.create_community( self.ds, username=self.default_community )
			user.record_dynamic_membership( comm )

		return user

	def _get_user(self, username=None):
		if username is None:
			username = self.default_username.lower()
		return users.User.get_user(username, self.ds)

	def _get_entity(self, username=None):
		if username is None:
			username = self.default_username.lower()
		return users.User.get_entity(username, self.ds)

	def has_permission( self, permission ):
		return has_permission( permission, self.request )

	def doesnt_have_permission( self, permission ):
		return doesnt_have_permission( permission, self.request )

	def link_with_rel( self, ext_obj, rel ):
		for lnk in ext_obj.get( 'Links', () ):
			if lnk['rel'] == rel:
				return lnk

	def link_href_with_rel( self, ext_obj, rel ):
		link = self.link_with_rel( ext_obj, rel )
		if link:
			return link['href']

	def require_link_href_with_rel( self, ext_obj, rel ):
		link = self.link_href_with_rel( ext_obj, rel )
		__traceback_info__ = ext_obj
		assert_that( link, described_as( "A link with rel %0", is_not( none() ), rel ) )
		return link

	def forbid_link_with_rel( self, ext_obj, rel ):
		link = self.link_with_rel( ext_obj, rel )
		__traceback_info__ = ext_obj, link, rel
		assert_that( link, is_( none() ), rel )

	def provide_security_policy_from_factory(self, security_policy_factory=None, force_security_policy=True):
		if security_policy_factory:
			self.security_policy = security_policy_factory()
			for iface in pyramid.interfaces.IAuthenticationPolicy, pyramid.interfaces.IAuthorizationPolicy:
				if iface.providedBy( self.security_policy ) or force_security_policy:
					component.provideUtility( self.security_policy, iface )
			return self.security_policy

TestBaseMixin = _TestBaseMixin

class _PWManagerMixin(object):
	
	_old_pw_manager = None

	def setUpPasswords(self):
		from nti.dataserver.users import Principal
		# By switching from the very secure and very expensive
		# bcrypt default, we speed application-level tests
		# up (due to faster principal creation and faster password authentication)
		# The forum tests go from 55s to 15s
		# This is a nose1 feature and will have to be moved for nose2,
		# probably to layers (which is a good thing in general)
		self._old_pw_manager = Principal.password_manager_name
		Principal.password_manager_name = 'Plain Text'

	def tearDownPasswords(self):
		if self._old_pw_manager:
			from nti.dataserver.users import Principal
			Principal.password_manager_name = self._old_pw_manager

class ConfiguringTestBase(_TestBaseMixin,_ConfiguringTestBase,_PWManagerMixin):
	"""
	Attributes:
	self.config A pyramid configurator. Note that it does not have a
		package associated with it.
	self.request A pyramid request
	"""

	def setUp( self,
			   pyramid_request=True,
			   request_factory=DummyRequest,
			   request_args=() ):
		"""
		:return: The `Configurator`, which is also in ``self.config``.
		"""
		self.setUpPasswords()

		super(ConfiguringTestBase,self).setUp()

		if pyramid_request:
			_create_request( self, request_factory, request_args )

		self.config = psetUp(registry=component.getGlobalSiteManager(),
							 request=self.request,
							 hook_zca=False)
		self.config.setup_registry()

		if pyramid_request and not getattr( self.request, 'registry', None ):
			self.request.registry = component.getSiteManager()

		if self.set_up_mailer:
			# Must provide the correct zpt template renderer or the email process blows up
			# See application.py
			self.config.include('pyramid_chameleon')
			self.config.include('pyramid_mako')

			component.provideUtility( z3c_zpt.renderer_factory,
									  pyramid.interfaces.IRendererFactory,
									  name=".pt" )
			mailer = TestMailDelivery()
			component.provideUtility( mailer, ITestMailDelivery )

		return self.config

	def tearDown( self ):
		ptearDown()
		self.tearDownPasswords()
		super(ConfiguringTestBase,self).tearDown()

class SharedConfiguringTestBase(_TestBaseMixin,_SharedConfiguringTestBase):

	HANDLE_GC = True # Must do GCs for ZCA cleanup. See superclass

	_mailer = None

	security_policy = None

	_pwman = None

	#: A demo storage will be created on top of this
	#: storage. This can be used to create objects at
	#: class or module set up time and have them available
	#: to dataservers created at test method set up time.
	_storage_base = None

	@classmethod
	def setUpClass( cls,
					request_factory=DummyRequest,
					request_args=(),
					security_policy_factory=None,
					force_security_policy=True ):
		"""
		:return: The `Configurator`, which is also in ``self.config``.
		"""
		cls._pwman = _PWManagerMixin()
		cls._pwman.setUpPasswords()

		# The demo storage has less strict requirements about
		# being open/closed than a plain mapping storage
		cls._storage_base = ZODB.DemoStorage.DemoStorage()

		super(SharedConfiguringTestBase,cls).setUpClass()

		cls.config = psetUp(registry=component.getGlobalSiteManager(),request=cls.request,hook_zca=False)
		cls.config.setup_registry()

		if cls.set_up_mailer:
			# Must provide the correct zpt template renderer or the email process blows up
			# See application.py
			cls.config.include('pyramid_chameleon')
			cls.config.include('pyramid_mako')
			component.provideUtility( z3c_zpt.renderer_factory, pyramid.interfaces.IRendererFactory, name=".pt" )
			cls._mailer = mailer = TestMailDelivery()
			component.provideUtility( mailer, ITestMailDelivery )


		if security_policy_factory:
			cls.security_policy = security_policy_factory()
			for iface in pyramid.interfaces.IAuthenticationPolicy, pyramid.interfaces.IAuthorizationPolicy:
				if iface.providedBy( cls.security_policy ) or force_security_policy:
					component.provideUtility( cls.security_policy, iface )
		return cls.config

	ds = property( lambda s: getattr(mock_dataserver, 'current_mock_ds' ) )

	@classmethod
	def tearDownClass( cls ):
		ptearDown()
		cls._mailer = None
		cls.security_policy = None
		cls._pwman.tearDownPasswords()
		cls._pwman = None
		super(SharedConfiguringTestBase,cls).tearDownClass()

	def setUp( self ):
		super(SharedConfiguringTestBase,self).setUp()
		if self._mailer:
			del self._mailer.queue[:]
		return self.config

	def tearDown( self ):
		super(SharedConfiguringTestBase,self).tearDown()

class NewRequestSharedConfiguringTestBase(SharedConfiguringTestBase):

	def setUp( self ):
		result = super(NewRequestSharedConfiguringTestBase,self).setUp()
		self.beginRequest()
		return result
