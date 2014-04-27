#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Base classes useful for working with application level
uses of :mod:`webtest`. These bases have some dependencies
on :mod:`nti.dataserver` and otherwise set up.

$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

#disable: accessing protected members, too many methods
#pylint: disable=W0212,R0904


from zope import interface
from zope.component import eventtesting
from zope import component

from .base import ConfiguringTestBase
from .base import SharedConfiguringTestBase
from .base import TestBaseMixin

from urllib import quote as UQ

from nti.dataserver import users
from nti.ntiids import ntiids
from nti.dataserver import interfaces as nti_interfaces
from nti.contentlibrary.filesystem import StaticFilesystemLibrary as Library

from nti.appserver.application import createApplication # TODO: Break this dep

from nti.dataserver.tests import mock_dataserver
from nti.utils.property import alias

class _AppTestBaseMixin(TestBaseMixin):
	"""
	A mixin that exposes knowledge about how
	URLs are structured and includes some convenience functions
	for working with common URLs.
	"""

	default_origin = b'http://localhost'

	extra_environ_default_user = alias('default_username')


	testapp = None

	def _make_extra_environ(self, user=None, update_request=False, **kwargs):
		"""
		The default username is a case-modified version of the default user in :meth:`_create_user`,
		to test case-insensitive ACLs and login.
		"""
		if user is None:
			user = self.extra_environ_default_user

		if user is self.extra_environ_default_user and 'username' in kwargs:
			user = str(kwargs.pop( 'username' ) )
		password = str(kwargs.pop('user_password', 'temp001'))

		# Simulate what some browsers or command line clients do by encoding the '@'
		# As of WebTest 2.0.15, see also TestApp.authorization:
		#  app.authorization = ('Basic', ('user', 'password'))
		user = user.replace( '@', "%40" )
		result = {
			b'HTTP_AUTHORIZATION': b'Basic ' + (user + ':%s' % password).encode('base64'),
			b'HTTP_ORIGIN': self.default_origin, # To trigger CORS
			b'HTTP_USER_AGENT': b'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_3) AppleWebKit/537.6 (KHTML, like Gecko) Chrome/23.0.1239.0 Safari/537.6',
			b'paste.throw_errors': True, # Cause paste to throw everything in case it gets in the pipeline
			b'paste.testing': True, # Let lower layers know we're testing
			}
		for k, v in kwargs.items():
			k = str(k)
			k.replace( '_', '-' )
			result[k] = v

		if update_request:
			self.request.environ.update( result )

		return result

	def _fetch_user_url( self, path, testapp=None, username=None, **kwargs ):
		if testapp is None:
			testapp = self.testapp
		if username is None:
			username = self.extra_environ_default_user

		return testapp.get( '/dataserver2/users/' + username + path, **kwargs )


	def resolve_user_response( self, testapp=None, username=None, **kwargs ):
		if testapp is None:
			testapp = self.testapp
		if username is None:
			username = self.extra_environ_default_user

		return testapp.get( UQ('/dataserver2/ResolveUser/' + username), **kwargs )


	def resolve_user( self, *args, **kwargs ):
		return self.resolve_user_response( *args, **kwargs ).json_body['Items'][0]

	def fetch_service_doc( self, testapp=None ):
		if testapp is None:
			testapp = self.testapp
		return testapp.get( '/dataserver2' )

	def post_user_data(self, ext_obj, testapp=None, username=None, **kwargs):
		"""Post the given external data to the given or default user."""
		if testapp is None:
			testapp = self.testapp
		if username is None:
			username = self.extra_environ_default_user

		return testapp.post_json( UQ('/dataserver2/users/' + username), ext_obj, **kwargs )

	def fetch_user_activity( self, testapp=None, username=None ):
		"Using the given or default app, fetch the activity for the given or default user"
		return self._fetch_user_url( '/Activity', testapp=testapp, username=username )

	def fetch_user_ugd( self, containerId, testapp=None, username=None, **kwargs ):
		"Using the given or default app, fetch the UserGeneratedData for the given or default user"
		return self._fetch_user_url( '/Pages(' + containerId + ')/UserGeneratedData',
									 testapp=testapp,
									 username=username,
									 **kwargs )

	def fetch_user_root_rugd( self, testapp=None, username=None, **kwargs ):
		"Using the given or default app, fetch the RecursiveUserGeneratedData for the given or default user"
		return self._fetch_user_url( '/Pages(' + ntiids.ROOT + ')/RecursiveUserGeneratedData',
									 testapp=testapp,
									 username=username,
									 **kwargs )

	def fetch_user_root_rstream( self, testapp=None, username=None, **kwargs ):
		"Using the given or default app, fetch the RecursiveStream for the given or default user"
		return self._fetch_user_url( '/Pages(' + ntiids.ROOT + ')/RecursiveStream',
									 testapp=testapp,
									 username=username,
									 **kwargs )

	def search_user_rugd( self, term, testapp=None, username=None, **kwargs ):
		"""Search the user for the given term and return the results"""
		return self._fetch_user_url( '/Search/RecursiveUserGeneratedData/' + term,
									 testapp=testapp,
									 username=username,
									 **kwargs )

	def fetch_by_ntiid( self, ntiid, testapp=None, **kwargs ):
		"Using the given or default app, fetch the object with the given ntiid"
		if testapp is None:
			testapp = self.testapp

		return testapp.get( '/dataserver2/NTIIDs/' + ntiid, **kwargs )


	def fetch_user_recursive_notable_ugd(self, testapp=None, username=None, **kwargs ):
		return self._fetch_user_url( '/Pages(' + ntiids.ROOT + ')/RUGDByOthersThatIMightBeInterestedIn',
									 testapp=testapp,
									 username=username,
									 **kwargs )


AppTestBaseMixin = _AppTestBaseMixin
import gc
def _create_app(cls, *args, **kwargs):
	# We do some very fragile things to make us work
	# correctly if *part* of the application has been
	# set up but not torn down...some things live outside
	# the ZCA registry but are nevertheless set up by the
	# ZCA registry...typically zope.testing.cleanup would get
	# these, but it's probably not run if we're in a layer
	import zope.browserpage.metaconfigure
	zope.browserpage.metaconfigure.clear()

	gc.collect()
	# During initial application setup, we need to have an open
	# database/dataserver in case any global setup needs to be
	# done. Whatever changes it makes we need to capture and use
	# as our base storage so that future tests can see them.

	# But we can't open it until the configuration is done
	# so that zope.generations kicks in and installs things
	# (in zope.app.appsetup, this is handled by the bootstrap subscribers;
	# but still, configuration must be done)
	_ds = []
	def create_ds():
		_ds.append( mock_dataserver.MockDataserver(base_storage=None) )
		return _ds[0]

	cls.app = createApplication( 8080,
								 cls._setup_library(),
								 create_ds=create_ds,
								 force_create_indexmanager=True,
								 pyramid_config=cls.config,
								 devmode=cls.APP_IN_DEVMODE,
								 testmode=True,
								 zcml_features=cls.features,
								 secure_cookies=False, # so we can authenticate with webtest cookies
								 **cls._extra_app_settings())
	cls._storage_base = _ds[0].db.storage
	_ds[0].close() # closing closes the storage and deletes the attribute
	cls.current_mock_ds = _ds[0]

def _test_set_up(self):
	#test_func = getattr( self, self._testMethodName )
	#ds_factory = getattr( test_func, 'mock_ds_factory', mock_dataserver.MockDataserver )
	#self.ds = ds_factory()
	#component.provideUtility( self.ds, nti_interfaces.IDataserver )

	# If we try to externalize things outside of an active request, but
	# the get_current_request method returns the mock request we just set up,
	# then if the environ doesn't have these things in it we can get an AssertionError
	# from paste.httpheaders n behalf of repoze.who's request classifier
	self.beginRequest()
	self.request.environ[b'HTTP_USER_AGENT'] = b'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_3) AppleWebKit/537.6 (KHTML, like Gecko) Chrome/23.0.1239.0 Safari/537.6'
	self.request.environ[b'wsgi.version'] = '1.0'

	self.users = {}
	self.testapp = None

def _test_tear_down(self):
	self.users = {}
	self.testapp = None

class SharedApplicationTestBase(_AppTestBaseMixin,SharedConfiguringTestBase):
	features = ()
	set_up_packages = () # None, because configuring the app will do this
	APP_IN_DEVMODE = True
	configure_events = False # We have no packages, but we will set up the listeners ourself when configuring the app

	@classmethod
	def _setup_library(cls, *args, **kwargs):
		return Library()

	@classmethod
	def _extra_app_settings(cls):
		return {}

	@classmethod
	def setUpClass(cls, *args, **kwargs):
		__traceback_info__ = cls
		super(SharedApplicationTestBase,cls).setUpClass(*args, **kwargs)
		_create_app(cls, *args, **kwargs)
		component.provideHandler( eventtesting.events.append, (None,) )

	def setUp(self):
		super(SharedApplicationTestBase,self).setUp()
		_test_set_up(self)

	def tearDown(self):
		_test_tear_down(self)
		super(SharedApplicationTestBase,self).tearDown()

	@classmethod
	def tearDownClass(cls):
		super(SharedApplicationTestBase,cls).tearDownClass()


from nti.testing.layers import GCLayerMixin
from nti.testing.layers import ZopeComponentLayer
from nti.testing.layers import ConfiguringLayerMixin
from nti.testing.layers import find_test
from nti.dataserver.tests.mock_dataserver import DSInjectorMixin
from .layers import PyramidLayerMixin


class AppCreatingLayerHelper(object):

	@classmethod
	def _setup_library(cls, *args, **kwargs):
		return Library()

	@classmethod
	def _extra_app_settings(cls):
		return {}

	@classmethod
	def appSetUp(cls, layer):
		layer.setUpPyramid()
		layer.setUpPackages()
		_create_app(layer)

	@classmethod
	def appTearDown(cls, layer):
		layer.tearDownPackages()
		layer.tearDownPyramid()

	@classmethod
	def appTestSetUp(cls, layer, test=None):
		test = test or find_test()
		layer.setUpTestDS(test)
		layer.testSetUpPyramid(test)
		test._storage_base = layer._storage_base
		test.app = layer.app
		_test_set_up(test)

	@classmethod
	def appTestTearDown(cls, layer, test=None):
		test = test or find_test()
		_test_tear_down(test)

class ApplicationTestLayer(ZopeComponentLayer,
						   PyramidLayerMixin,
						   GCLayerMixin,
						   ConfiguringLayerMixin,
						   DSInjectorMixin,
						   ):
	features = ('forums',)
	set_up_packages = () # None, because configuring the app will do this
	APP_IN_DEVMODE = True
	configure_events = False # We have no packages, but we will set up the listeners ourself when configuring the app

	@classmethod
	def _setup_library(cls, *args, **kwargs):
		return Library()

	@classmethod
	def _extra_app_settings(cls):
		return {}

	@classmethod
	def setUp(cls):
		AppCreatingLayerHelper.appSetUp(cls)

	@classmethod
	def tearDown(cls):
		AppCreatingLayerHelper.appTearDown(cls)

	@classmethod
	def testSetUp(cls, test=None):
		AppCreatingLayerHelper.appTestSetUp(cls, test)

	@classmethod
	def testTearDown(cls, test=None):
		AppCreatingLayerHelper.appTestTearDown(cls, test)


class NonDevmodeApplicationTestLayer(ZopeComponentLayer,
									 PyramidLayerMixin,
									 GCLayerMixin,
									 ConfiguringLayerMixin,
									 DSInjectorMixin):
	features = ()
	set_up_packages = () # None, because configuring the app will do this
	APP_IN_DEVMODE = False
	configure_events = False # We have no packages, but we will set up the listeners ourself when configuring the app

	@classmethod
	def _setup_library(cls, *args, **kwargs):
		return Library()

	@classmethod
	def _extra_app_settings(cls):
		return {'force_devmode_off': True}

	@classmethod
	def setUp(cls):
		AppCreatingLayerHelper.appSetUp(cls)

	@classmethod
	def tearDown(cls):
		AppCreatingLayerHelper.appTearDown(cls)

	@classmethod
	def testSetUp(cls, test=None):
		AppCreatingLayerHelper.appTestSetUp(cls, test)

	@classmethod
	def testTearDown(cls, test=None):
		AppCreatingLayerHelper.appTestTearDown(cls, test)


import unittest

class ApplicationLayerTest(AppTestBaseMixin, unittest.TestCase):
	layer = ApplicationTestLayer

class NonDevmodeApplicationLayerTest(AppTestBaseMixin, unittest.TestCase):
	layer = NonDevmodeApplicationTestLayer


class ApplicationTestBase(_AppTestBaseMixin, ConfiguringTestBase):

	set_up_packages = () # None, because configuring the app will do this
	APP_IN_DEVMODE = True
	def _setup_library(self, *args, **kwargs):
		return Library()

	def setUp(self):
		super(ApplicationTestBase,self).setUp(pyramid_request=False)
		#self.ds = mock_dataserver.MockDataserver()
		test_func = getattr( self, self._testMethodName )
		ds_factory = getattr( test_func, 'mock_ds_factory', mock_dataserver.MockDataserver )

		self.app = createApplication( 8080,
									  self._setup_library(),
									  create_ds=ds_factory,
									  pyramid_config=self.config,
									  devmode=self.APP_IN_DEVMODE,
									  testmode=True )
		self.ds = component.getUtility( nti_interfaces.IDataserver )

		# If we try to externalize things outside of an active request, but
		# the get_current_request method returns the mock request we just set up,
		# then if the environ doesn't have these things in it we can get an AssertionError
		# from paste.httpheaders n behalf of repoze.who's request classifier
		self.beginRequest()
		self.request.environ[b'HTTP_USER_AGENT'] = b'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_3) AppleWebKit/537.6 (KHTML, like Gecko) Chrome/23.0.1239.0 Safari/537.6'
		self.request.environ[b'wsgi.version'] = '1.0'


	def tearDown(self):
		super(ApplicationTestBase,self).tearDown()
