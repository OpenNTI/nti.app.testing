#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Integration with WebTest, including improved pipelines and unicode support.



$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from webtest import TestApp as _TestApp


from nti.wsgi.cors import cors_filter_factory as CORSInjector
from nti.wsgi.cors import cors_option_filter_factory as CORSOptionHandler
from paste.exceptions.errormiddleware import ErrorMiddleware

from nti.dataserver.tests import mock_dataserver

class _ZODBGCMiddleware(object):

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

class _PasteTestingMiddleware(object):
	"""
	Ensure we are in paste.testing mode, which isn't
	guaranteed if the user manually set all the incoming
	headers.
	"""

	def __init__(self, app):
		self.app = app

	def __call__(self, environ, start_response):
		environ[b'paste.testing'] = True
		return self.app(environ, start_response)

def TestApp(app, **kwargs):
	"""Sets up the pipeline just like in real life.

	:return: A WebTest testapp.
	"""
	# TODO: Load from paste?
	return _TestApp(
			CORSInjector(
				CORSOptionHandler(
					ErrorMiddleware(
						_ZODBGCMiddleware(
							_PasteTestingMiddleware( app ) ),
						debug=True ) ) ),
			**kwargs )
TestApp.__test__ = False # make nose not call this
