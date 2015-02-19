#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Application test layers.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

__test__ = False

import pyramid
from pyramid.testing import setUp as psetUp
from pyramid.testing import tearDown as ptearDown

import ZODB.DemoStorage

from zope import component
import zope.testing.cleanup

from nti.app.pyramid_zope import z3c_zpt

from nti.dataserver.tests.mock_dataserver import DSInjectorMixin

from nti.testing.layers import find_test
from nti.testing.layers import GCLayerMixin
from nti.testing.layers import ZopeComponentLayer
from nti.testing.layers import ConfiguringLayerMixin

from .base import DummyRequest
from .base import _PWManagerMixin

from .testing import TestMailDelivery
from .testing import ITestMailDelivery

class PyramidLayerMixin(GCLayerMixin):


	_mailer = None

	security_policy = None

	_pwman = None

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
		setHooks() # but these must be back!

	@classmethod
	def testSetUpPyramid( cls, test=None ):
		test = test or find_test
		test.config = cls.config
		if cls._mailer:
			del cls._mailer.queue[:]

	@classmethod
	def setUp(cls):
		pass

	@classmethod
	def tearDown(cls):
		pass

	@classmethod
	def testSetUp( cls ):
		pass

	@classmethod
	def testTearDown(cls):
		# Must implement
		pass

from zope.component.hooks import setHooks

class AppTestLayer(ZopeComponentLayer,
				   PyramidLayerMixin,
				   GCLayerMixin,
				   ConfiguringLayerMixin,
				   DSInjectorMixin):
	set_up_packages = ('nti.appserver',)
	@classmethod
	def setUp(cls):
		setHooks()
		cls.setUpPyramid()
		cls.setUpPackages()

	@classmethod
	def tearDown(cls):
		cls.tearDownPackages()
		cls.tearDownPyramid()
		zope.testing.cleanup.cleanUp()
		setHooks() # but these must be back!

	@classmethod
	def testSetUp(cls, test=None):
		cls.setUpTestDS(test)
		cls.testSetUpPyramid(test)

	@classmethod
	def testTearDown(cls):
		# Must implement
		pass

class NewRequestAppTestLayer(AppTestLayer):

	@classmethod
	def setUp(cls):
		# You MUST implement this, otherwise zope.testrunner
		# will call the super-class again
		setHooks()

	@classmethod
	def tearDown(cls):
		# You MUST implement this, otherwise zope.testrunner
		# will call the super-class again
		zope.testing.cleanup.cleanUp()
		setHooks() # but these must be back!

	@classmethod
	def testSetUp( cls, test=None ):
		test = test or find_test()
		cls.testSetUpPyramid(test)
		test.beginRequest()

	@classmethod
	def testTearDown(cls):
		# Must implement
		pass

SharedConfiguringTestLayer = AppTestLayer
NewRequestSharedConfiguringTestLayer = NewRequestAppTestLayer

import unittest

from .base import TestBaseMixin

class AppLayerTest(TestBaseMixin,unittest.TestCase):
	layer = AppTestLayer

class NewRequestLayerTest(TestBaseMixin,unittest.TestCase):
	layer = NewRequestAppTestLayer

class NonDevmodeSharedConfiguringTestLayer(ZopeComponentLayer,
										   PyramidLayerMixin,
										   GCLayerMixin,
										   ConfiguringLayerMixin,
										   DSInjectorMixin):

	features = ()
	set_up_packages = ('nti.appserver',)
	@classmethod
	def setUp(cls):
		setHooks()
		cls.setUpPyramid()
		cls.setUpPackages()

	@classmethod
	def tearDown(cls):
		cls.tearDownPackages()
		cls.tearDownPyramid()
		zope.testing.cleanup.cleanUp()
		setHooks()

	@classmethod
	def testSetUp(cls, test=None):
		cls.setUpTestDS(test)
		cls.testSetUpPyramid(test)

class NonDevmodeNewRequestSharedConfiguringTestLayer(NonDevmodeSharedConfiguringTestLayer):

	@classmethod
	def setUp(cls):
		# You MUST implement this, otherwise zope.testrunner
		# will call the super-class again
		setHooks()

	@classmethod
	def tearDown(cls):
		# You MUST implement this, otherwise zope.testrunner
		# will call the super-class again
		zope.testing.cleanup.cleanUp()
		setHooks()

	@classmethod
	def testSetUp( cls, test=None ):
		test = test or find_test()
		cls.testSetUpPyramid(test)
		test.beginRequest()

	@classmethod
	def testTearDown(cls):
		pass

class NonDevmodeNewRequestLayerTest(TestBaseMixin,unittest.TestCase):
	layer = NonDevmodeNewRequestSharedConfiguringTestLayer
