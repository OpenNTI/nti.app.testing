#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Application layer test bases for defining setup.

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

from nose.tools import assert_raises

from nti.contentsearch import interfaces as search_interfaces
import nti.contentsearch

import pyramid.config


from webtest import TestApp as _TestApp





from nti.dataserver import users
from nti.ntiids import ntiids
from nti.dataserver import interfaces as nti_interfaces

from nti.dataserver.tests import mock_dataserver


from urllib import quote as UQ

from zope import interface
from zope import component
from zope.deprecation import __show__

from .matchers import has_permission, doesnt_have_permission
from .request_response import DummyRequest

class _TestBaseMixin(object):
	set_up_packages = ('nti.appserver',)
	set_up_mailer = True
	config = None
	request = None

	def beginRequest( self, request_factory=DummyRequest, request_args=() ):
		_create_request( self, request_factory, request_args )
		self.config.begin( request=self.request )

	def get_ds(self):
		"Convenience for when you have imported mock_dataserver and used @WithMockDS/Trans"
		return getattr( self, '_ds', mock_dataserver.current_mock_ds )

	def set_ds(self,ds):
		"setable for backwards compat"
		self._ds = ds
	ds = property( get_ds, set_ds )

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
		assert_that( link, is_not( none() ), rel )
		return link

	def forbid_link_with_rel( self, ext_obj, rel ):
		link = self.link_with_rel( ext_obj, rel )
		__traceback_info__ = ext_obj, link, rel
		assert_that( link, is_( none() ), rel )


TestBaseMixin = _TestBaseMixin
class ConfiguringTestBase(_TestBaseMixin,_ConfiguringTestBase):
	"""
	Attributes:
	self.config A pyramid configurator. Note that it does not have a
		package associated with it.
	self.request A pyramid request
	"""

	def setUp( self, pyramid_request=True, request_factory=DummyRequest, request_args=() ):
		"""
		:return: The `Configurator`, which is also in ``self.config``.
		"""

		super(ConfiguringTestBase,self).setUp()

		if pyramid_request:
			_create_request( self, request_factory, request_args )

		self.config = psetUp(registry=component.getGlobalSiteManager(),request=self.request,hook_zca=False)
		self.config.setup_registry()
		if pyramid_request and not getattr( self.request, 'registry', None ):
			self.request.registry = component.getGlobalSiteManager()

		if self.set_up_mailer:
			# Must provide the correct zpt template renderer or the email process blows up
			# See application.py
			self.config.include('pyramid_chameleon')
			self.config.include('pyramid_mako')

			component.provideUtility( z3c_zpt.renderer_factory, pyramid.interfaces.IRendererFactory, name=".pt" )
			mailer = TestMailDelivery()
			component.provideUtility( mailer, ITestMailDelivery )

		return self.config

	def tearDown( self ):
		ptearDown()
		super(ConfiguringTestBase,self).tearDown()
from nti.appserver import pyramid_authorization
class SharedConfiguringTestBase(_TestBaseMixin,_SharedConfiguringTestBase):

	HANDLE_GC = True # Must do GCs for ZCA cleanup. See superclass

	_mailer = None

	security_policy = None

	@classmethod
	def setUpClass( cls, request_factory=DummyRequest, request_args=(), security_policy_factory=None, force_security_policy=True ):
		"""
		:return: The `Configurator`, which is also in ``self.config``.
		"""

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
		super(SharedConfiguringTestBase,cls).tearDownClass()

	def setUp( self ):
		super(SharedConfiguringTestBase,self).setUp()
		if self._mailer:
			del self._mailer.queue[:]
		return self.config

	def tearDown( self ):
		# Some things have to be done everytime
		pyramid_authorization._clear_caches()
		super(SharedConfiguringTestBase,self).tearDown()

class NewRequestSharedConfiguringTestBase(SharedConfiguringTestBase):

	def setUp( self ):
		result = super(NewRequestSharedConfiguringTestBase,self).setUp()
		self.beginRequest()
		return result



import contextlib
from ZODB.interfaces import IConnection
from zope.component.hooks import site as using_site
import transaction

@contextlib.contextmanager
def _trivial_db_transaction_cm():
	# TODO: This needs all the retry logic, etc, that we
	# get in the main app through pyramid_tm

	lsm = component.getSiteManager()
	conn = IConnection( lsm, None )
	if conn:
		yield conn
		return

	ds = component.getUtility( nti_interfaces.IDataserver )
	transaction.begin()
	conn = ds.db.open()
	# If we don't sync, then we can get stale objects that
	# think they belong to a closed connection
	# TODO: Are we doing something in the wrong order? Connection
	# is an ISynchronizer and registers itself with the transaction manager,
	# so we shouldn't have to do this manually
	# ... I think the problem was a bad site. I think this can go away.
	conn.sync()
	sitemanc = conn.root()['nti.dataserver']


	with using_site( sitemanc ):
		assert component.getSiteManager() == sitemanc.getSiteManager()
		assert component.getUtility( nti_interfaces.IDataserver )
		try:
			yield conn
			transaction.commit()
		except:
			transaction.abort()
			raise
		finally:
			conn.close()

from nti.appserver.cors import cors_filter_factory as CORSInjector, cors_option_filter_factory as CORSOptionHandler
from paste.exceptions.errormiddleware import ErrorMiddleware

class ZODBGCMiddleware(object):

	def __init__( self, app ):
		self.app = app

	def __call__( self, *args, **kwargs ):
		result = self.app( *args, **kwargs )
		mock_dataserver.reset_db_caches( )
		return result


class _UnicodeTestApp(_TestApp):
	"To make using unicode literals easier"

	def _make_( name ):
		def f( self, path, *args, **kwargs ):
			__traceback_info__ = path, args, kwargs
			return getattr( super(_UnicodeTestApp,self), name )( str(path), *args, **kwargs )

		f.__name__ = name
		return f

	# XXX: PY3: These change between bytes and strings, bytes in py2, unicode
	# strings in py 3
	get = _make_(b'get')
	put = _make_(b'put')
	post = _make_(b'post')
	put_json = _make_(b'put_json')
	post_json = _make_(b'post_json')
	delete = _make_( b'delete' )

	del _make_

_TestApp = _UnicodeTestApp

def TestApp(app, **kwargs):
	"""Sets up the pipeline just like in real life.

	:return: A WebTest testapp.
	"""

	return _TestApp( CORSInjector( CORSOptionHandler( ErrorMiddleware( ZODBGCMiddleware( app ), debug=True ) ) ),
					 **kwargs )
TestApp.__test__ = False # make nose not call this

class _AppTestBaseMixin(object):

	default_user_extra_interfaces = ()
	extra_environ_default_user = b'sjohnson@nextthought.COM'
	default_origin = b'http://localhost'

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
			b'HTTP_USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_3) AppleWebKit/537.6 (KHTML, like Gecko) Chrome/23.0.1239.0 Safari/537.6',
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
			user.join_community( comm )

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

from zope.component import eventtesting
class SharedApplicationTestBase(_AppTestBaseMixin,SharedConfiguringTestBase):
	features = ()
	set_up_packages = () # None, because configuring the app will do this
	APP_IN_DEVMODE = True
	configure_events = False # We have no packages, but we will set up the listeners ourself when configuring the app

	@classmethod
	def _setup_library(cls, *args, **kwargs):
		return Library()

	@classmethod
	def setUpClass(cls):
		__show__.off()
		#self.ds = mock_dataserver.MockDataserver()
		super(SharedApplicationTestBase,cls).setUpClass()
		cls.app = createApplication( 8080, cls._setup_library(), create_ds=False, force_create_indexmanager=True,
									 pyramid_config=cls.config, devmode=cls.APP_IN_DEVMODE, testmode=True, zcml_features=cls.features )

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
		__show__.on()
		super(SharedApplicationTestBase,cls).tearDownClass()

def WithSharedApplicationMockDS( *args, **kwargs ):
	"""
	Decorator for a test function using the shared application.
	Unknown keyword arguments are passed to :func:`.WithMockDS`.

	:keyword users: Either `True`, or a sequence of strings naming users. If True,
		 then the standard user is created. If a sequence, then the standard user,
		 followed by each named user is created.
	:keyword bool default_authenticate: Only used if ``users`` was a sequence
		(and so we have created at least two users). If set to `True` (NOT the default),
		then ``self.testapp`` will be authenticated by the standard user.
	:keyword bool testapp: If True (NOT the default) then ``self.testapp`` will
		be created.
	:keyword bool handle_changes: If `True` (NOT the default), the application will
		have the usual change managers set up (users.onChange, etc).

	"""

	users_to_create = kwargs.pop( 'users', None )
	default_authenticate = kwargs.pop( 'default_authenticate', None )
	testapp = kwargs.pop( 'testapp', None )
	handle_changes = kwargs.pop( 'handle_changes', False )
	user_hook = kwargs.pop( 'user_hook', None )

	if testapp:
		def _make_app(self):
			if users_to_create is True or (users_to_create and default_authenticate):
				self.testapp = TestApp( self.app, extra_environ=self._make_extra_environ() )
			else:
				self.testapp = TestApp( self.app )

			if handle_changes:
				ds = self.ds
				ix = component.queryUtility( search_interfaces.IIndexManager )
				_configure_async_changes( ds, ix )
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
	else:
		def _do_create(self):
			pass

	if handle_changes:
		kwargs['with_changes'] = True # make sure the DS gets it

	if len(args) == 1 and not kwargs:
		# being used as a decorator
		func = args[0]

		@functools.wraps(func)
		@mock_dataserver.WithMockDS
		def f(self):
			self.config.registry._zodb_databases = { '': self.ds.db } # 0.3
			self.ds.redis.flushall()
			_do_create( self )
			_make_app( self )
			func(self)
		return f

	# Being used as a decorator factory
	def factory(func):
		@functools.wraps(func)
		@mock_dataserver.WithMockDS(**kwargs)
		def f(self):
			self.config.registry._zodb_databases = { '': self.ds.db } # 0.3
			self.ds.redis.flushall()
			_do_create( self )
			_make_app( self )
			func(self)
		return f
	return factory

def WithSharedApplicationMockDSHandleChanges( *args, **kwargs ):
	call_factory = False
	if len(args) == 1 and not kwargs:
		# Being used as a plain decorator. But we add kwargs that make
		# it look like we're being used as a factory
		call_factory = True

	kwargs['handle_changes'] = True
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


class ApplicationTestBase(_AppTestBaseMixin, ConfiguringTestBase):

	set_up_packages = () # None, because configuring the app will do this
	APP_IN_DEVMODE = True
	def _setup_library(self, *args, **kwargs):
		return Library()

	def setUp(self):
		__show__.off()
		super(ApplicationTestBase,self).setUp(pyramid_request=False)
		#self.ds = mock_dataserver.MockDataserver()
		test_func = getattr( self, self._testMethodName )
		ds_factory = getattr( test_func, 'mock_ds_factory', mock_dataserver.MockDataserver )

		self.app = createApplication( 8080, self._setup_library(), create_ds=ds_factory, pyramid_config=self.config, devmode=self.APP_IN_DEVMODE, testmode=True )
		self.ds = component.getUtility( nti_interfaces.IDataserver )

		# If we try to externalize things outside of an active request, but
		# the get_current_request method returns the mock request we just set up,
		# then if the environ doesn't have these things in it we can get an AssertionError
		# from paste.httpheaders n behalf of repoze.who's request classifier
		self.beginRequest()
		self.request.environ[b'HTTP_USER_AGENT'] = b'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_3) AppleWebKit/537.6 (KHTML, like Gecko) Chrome/23.0.1239.0 Safari/537.6'
		self.request.environ[b'wsgi.version'] = '1.0'


	def tearDown(self):
		__show__.on()
		super(ApplicationTestBase,self).tearDown()
