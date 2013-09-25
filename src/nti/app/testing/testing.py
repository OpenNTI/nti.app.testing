import nti.appserver
from hamcrest import assert_that
from hamcrest import is_
from hamcrest import is_not
from hamcrest import none
from pyramid.testing import setUp as psetUp
from pyramid.testing import tearDown as ptearDown
#from pyramid.testing import DummyRequest
from nti.tests import ByteHeadersDummyRequest as _ByteHeadersDummyRequest

_old_pw_manager = None
def setUpPackage():
	from nti.dataserver.users import Principal
	global _old_pw_manager
	# By switching from the very secure and very expensive
	# bcrypt default, we speed application-level tests
	# up (due to faster principal creation and faster password authentication)
	# The forum tests go from 55s to 15s
	# This is a nose1 feature and will have to be moved for nose2
	_old_pw_manager = Principal.password_manager_name
	Principal.password_manager_name = 'Plain Text'

def tearDownPackage():
	if _old_pw_manager:
		from nti.dataserver.users import Principal
		Principal.password_manager_name = _old_pw_manager


class DummyRequest(_ByteHeadersDummyRequest):
	possible_site_names = ()
	def _on_set_header( self, key, val ):
		from nti.appserver.tweens.zope_site_tween import _get_possible_site_names
		site_names = _get_possible_site_names( self )
		self.possible_site_names = tuple(site_names)

import pyramid.interfaces


import zope.component as component

from nti.dataserver.tests import mock_dataserver
import nti.tests


from pyramid_mailer.interfaces import IMailer
from pyramid_mailer.mailer import DummyMailer as _DummyMailer
from repoze.sendmail.interfaces import IMailDelivery

class ITestMailDelivery(IMailer, IMailDelivery):
	pass

from nti.appserver import z3c_zpt

import webtest.lint
from webtest.lint import check_headers as _orig_check_headers
def unicode_check_headers(headers):
	"""
	Up through at least WebTest 1.4.0, the middleware in webtest.lint
	doesn't ensure that header names and values are bytestrings, but
	this is required (if not in the spec, then in the implementation
	provided in gevent 1.0rc1). This check causes that to happen.
	"""
	_orig_check_headers( headers )
	for k, v in headers:
		assert_that( k, is_( str ), 'Header names must be byte strings' )
		assert_that( v, is_( str ), 'Header values must be byte strings' )

def monkey_patch_check_headers():
	"""
	Patches webtest.lint to use :func:`unicode_check_headers`. This module
	does this on import.
	"""
	if webtest.lint.check_headers.__module__ == 'webtest.lint':
		webtest.lint.check_headers = unicode_check_headers
monkey_patch_check_headers()

import simplejson
import webtest.compat
import webtest.app
import webtest.utils
def monkey_patch_webtest_json_to_simplejson():
	"""
	Make webtest use the faster simplejson dump/load functions.
	"""
	webtest.compat.loads = simplejson.loads
	webtest.compat.dumps = simplejson.dumps
	webtest.app.dumps = simplejson.dumps
	webtest.app.loads = simplejson.loads
	webtest.utils.dumps = simplejson.dumps
	webtest.utils.loads = simplejson.loads
monkey_patch_webtest_json_to_simplejson()

def monkey_patch_webtest_form20_to_not_be_stupid():
	import webtest.forms
	webtest.forms.Field.value = None # Idiot thing is broken in 2.0
monkey_patch_webtest_form20_to_not_be_stupid()

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
	set_up_packages = (nti.appserver,)
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
		return HasPermission( True, permission, self.request )

	def doesnt_have_permission( self, permission ):
		return HasPermission( False, permission, self.request )


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
class ConfiguringTestBase(_TestBaseMixin,nti.tests.ConfiguringTestBase):
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
class SharedConfiguringTestBase(_TestBaseMixin,nti.tests.SharedConfiguringTestBase):

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

from pyramid.security import has_permission

class HasPermission(nti.tests.BoolMatcher):

	def __init__( self, value, permission, request ):
		super(HasPermission,self).__init__( value )
		self.permission = permission
		self.request = request

	def _matches(self, item):
		return super(HasPermission,self)._matches( has_permission( self.permission, item, self.request ) )


class TestMailDelivery(_DummyMailer):

	default_sender = 'no-reply@nextthought.com'

	def __init__( self ):
		super(TestMailDelivery,self).__init__()


	def send( self, fromaddr, toaddr, message ):
		#from IPython.core.debugger import Tracer; Tracer()() ## DEBUG ##

		self.queue.append( message )
		# compat with pyramid_mailer messages
		message.subject = message.get( 'Subject' )
		payload = message.get_payload()
		message.body = payload[0].get_payload()
		if len(payload) > 1:
			message.html = payload[1].get_payload()
