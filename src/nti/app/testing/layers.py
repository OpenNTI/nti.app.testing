#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Application test layers.

$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"


__test__ = False

logger = __import__('logging').getLogger(__name__)

#disable: accessing protected members, too many methods
#pylint: disable=W0212,R0904

from nti.testing.base import ConfiguringTestBase as _ConfiguringTestBase
from nti.testing.base import SharedConfiguringTestBase as _SharedConfiguringTestBase

from pyramid.testing import setUp as psetUp
from pyramid.testing import tearDown as ptearDown

import ZODB.DemoStorage

from .testing import ITestMailDelivery
from .testing import TestMailDelivery

from nose.tools import assert_raises
from hamcrest import assert_that
from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import described_as

from nti.contentsearch import interfaces as search_interfaces
import nti.contentsearch

import pyramid.config


from webtest import TestApp as _TestApp

from nti.app.pyramid_zope import z3c_zpt



from nti.dataserver import users
from nti.ntiids import ntiids
from nti.dataserver import interfaces as nti_interfaces

from nti.dataserver.tests import mock_dataserver


from urllib import quote as UQ

from zope import interface
from zope import component

from .base import _PWManagerMixin
from .base import DummyRequest


import zope.deferredimport
zope.deferredimport.initialize()
zope.deferredimport.deprecatedFrom(
	"Moved to application_webtest",
	"nti.app.testing.application_webtest",
	"SharedApplicationTestBase" )


from nti.testing.layers import GCLayerMixin
from nti.testing.layers import ZopeComponentLayer
from nti.testing.layers import ConfiguringLayerMixin
from nti.testing.layers import find_test

from nti.dataserver.tests.mock_dataserver import DSInjectorMixin

class PyramidLayerMixin(GCLayerMixin):


	_mailer = None

	security_policy = None

	_pwman = None
	set_up_packages = ('nti.appserver',)

	#: A demo storage will be created on top of this
	#: storage. This can be used to create objects at
	#: class or module set up time and have them available
	#: to dataservers created at test method set up time.
	_storage_base = None

	request = None
	set_up_mailer = True

	@classmethod
	def setUpPyramid(cls,
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



	@classmethod
	def tearDownPyramid( cls ):
		ptearDown()
		cls._mailer = None
		cls.security_policy = None
		cls._pwman.tearDownPasswords()
		cls._pwman = None
		zope.testing.cleanup.cleanUp()


	@classmethod
	def testSetUpPyramid( cls, test=None ):
		test = test or find_test
		test.config = cls.config
		if cls._mailer:
			del cls._mailer.queue[:]


	@classmethod
	def testTearDown( cls ):
		pass

class SharedConfiguringTestLayer(ZopeComponentLayer,
								 PyramidLayerMixin,
								 GCLayerMixin,
								 ConfiguringLayerMixin,
								 DSInjectorMixin):

	@classmethod
	def setUp(cls):
		cls.setUpPyramid()
		cls.setUpPackages()

	@classmethod
	def tearDown(cls):
		cls.tearDownPackages()
		cls.tearDownPyramid()

	@classmethod
	def testSetUp(cls, test=None):
		cls.setUpTestDS(test)
		cls.testSetUpPyramid(test)


class NewRequestSharedConfiguringTestLayer(SharedConfiguringTestLayer):

	@classmethod
	def setUp(cls):
		# You MUST implement this, otherwise zope.testrunner
		# will call the super-class again
		pass

	@classmethod
	def tearDown(cls):
		# You MUST implement this, otherwise zope.testrunner
		# will call the super-class again
		pass

	@classmethod
	def testSetUp( cls, test=None ):
		test = test or find_test()
		cls.testSetUpPyramid(test)
		test.beginRequest()

class NonDevmodeSharedConfiguringTestLayer(ZopeComponentLayer,
										   PyramidLayerMixin,
										   GCLayerMixin,
										   ConfiguringLayerMixin,
										   DSInjectorMixin):

	features = ()

	@classmethod
	def setUp(cls):
		cls.setUpPyramid()
		cls.setUpPackages()

	@classmethod
	def tearDown(cls):
		cls.tearDownPackages()
		cls.tearDownPyramid()

	@classmethod
	def testSetUp(cls, test=None):
		cls.setUpTestDS(test)
		cls.testSetUpPyramid(test)


class NonDevmodeNewRequestSharedConfiguringTestLayer(NonDevmodeSharedConfiguringTestLayer):

	@classmethod
	def setUp(cls):
		# You MUST implement this, otherwise zope.testrunner
		# will call the super-class again
		pass

	@classmethod
	def tearDown(cls):
		# You MUST implement this, otherwise zope.testrunner
		# will call the super-class again
		pass

	@classmethod
	def testSetUp( cls, test=None ):
		test = test or find_test()
		cls.testSetUpPyramid(test)
		test.beginRequest()
