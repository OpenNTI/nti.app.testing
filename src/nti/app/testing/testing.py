
from hamcrest import assert_that
from hamcrest import is_
from hamcrest import is_not
from hamcrest import none
from pyramid.testing import setUp as psetUp
from pyramid.testing import tearDown as ptearDown

__test__ = False

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


import pyramid.interfaces


from pyramid_mailer.interfaces import IMailer
from pyramid_mailer.mailer import DummyMailer as _DummyMailer
from repoze.sendmail.interfaces import IMailDelivery

class ITestMailDelivery(IMailer, IMailDelivery):
	pass


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
