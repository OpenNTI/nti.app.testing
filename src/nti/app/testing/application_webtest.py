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

from urllib import quote as UQ

from nti.dataserver import users
from nti.ntiids import ntiids
from nti.dataserver import interfaces as nti_interfaces
from nti.contentlibrary.filesystem import StaticFilesystemLibrary as Library

from nti.appserver.application import createApplication # TODO: Break this dep

from nti.dataserver.tests import mock_dataserver


class _AppTestBaseMixin(object):
	"""
	A mixin that exposes knowledge about how
	URLs are structured and includes some convenience functions
	for working with common URLs.
	"""

	default_user_extra_interfaces = ()
	extra_environ_default_user = b'sjohnson@nextthought.COM'
	default_origin = b'http://localhost'

	#: Set this to the username or NTIID of a community that users
	#: created with :meth:`_create_user` should be added to.
	default_community = None

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
		user = user.replace( '@', "%40" )
		result = {
			b'HTTP_AUTHORIZATION': b'Basic ' + (user + ':%s' % password).encode('base64'),
			b'HTTP_ORIGIN': self.default_origin, # To trigger CORS
			b'HTTP_USER_AGENT': b'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_3) AppleWebKit/537.6 (KHTML, like Gecko) Chrome/23.0.1239.0 Safari/537.6',
			b'paste.throw_errors': True, # Cause paste to throw everything in case it gets in the pipeline
			}
		for k, v in kwargs.items():
			k = str(k)
			k.replace( '_', '-' )
			result[k] = v

		if update_request:
			self.request.environ.update( result )

		return result

	def _create_user(self, username=None, password='temp001', **kwargs):
		if username is None:
			username = self.extra_environ_default_user.lower()
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

	def fetch_user_activity( self, testapp=None, username=None ):
		"Using the given or default app, fetch the activity for the given or default user"
		return self._fetch_user_url( '/Activity', testapp=testapp, username=username )

	def fetch_user_ugd( self, containerId, testapp=None, username=None, **kwargs ):
		"Using the given or default app, fetch the UserGeneratedData for the given or default user"
		return self._fetch_user_url( '/Pages(' + containerId + ')/UserGeneratedData', testapp=testapp, username=username, **kwargs )

	def fetch_user_root_rugd( self, testapp=None, username=None, **kwargs ):
		"Using the given or default app, fetch the RecursiveUserGeneratedData for the given or default user"
		return self._fetch_user_url( '/Pages(' + ntiids.ROOT + ')/RecursiveUserGeneratedData', testapp=testapp, username=username, **kwargs )

	def fetch_user_root_rstream( self, testapp=None, username=None, **kwargs ):
		"Using the given or default app, fetch the RecursiveStream for the given or default user"
		return self._fetch_user_url( '/Pages(' + ntiids.ROOT + ')/RecursiveStream', testapp=testapp, username=username, **kwargs )

	def search_user_rugd( self, term, testapp=None, username=None, **kwargs ):
		"""Search the user for the given term and return the results"""
		return self._fetch_user_url( '/Search/RecursiveUserGeneratedData/' + term, testapp=testapp, username=username, **kwargs )

	def fetch_by_ntiid( self, ntiid, testapp=None, **kwargs ):
		"Using the given or default app, fetch the object with the given ntiid"
		if testapp is None:
			testapp = self.testapp

		return testapp.get( '/dataserver2/NTIIDs/' + ntiid, **kwargs )

AppTestBaseMixin = _AppTestBaseMixin


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
		# During initial application setup, we need to have an open
		# database/dataserver in case any global setup needs to be
		# done. It needs to use our base storage so that these things
		# will be visible to future DBs.
		# But we can't open it until the configuration is done
		# so that zope.generations kicks in and installs things
		# (in zope.app.appsetup, this is handled by the bootstrap subscribers;
		# but still, configuration must be done)
		_ds = []
		def create_ds():
			_ds.append( mock_dataserver.MockDataserver(base_storage=cls._storage_base) )
			return _ds[0]

		cls.app = createApplication( 8080,
									 cls._setup_library(),
									 create_ds=create_ds,
									 force_create_indexmanager=True,
									 pyramid_config=cls.config,
									 devmode=cls.APP_IN_DEVMODE,
									 testmode=True,
									 zcml_features=cls.features,
									 **cls._extra_app_settings())
		_ds[0].close()
		component.provideHandler( eventtesting.events.append, (None,) )

	def setUp(self):
		super(SharedApplicationTestBase,self).setUp()

		test_func = getattr( self, self._testMethodName )
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


	def tearDown(self):
		self.users = {}
		self.testapp = None
		super(SharedApplicationTestBase,self).tearDown()

	@classmethod
	def tearDownClass(cls):
		super(SharedApplicationTestBase,cls).tearDownClass()



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
