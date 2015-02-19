#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Fixture functions and context managers for making it easy to deal with sites.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

import contextlib

from zope import component
from zope.component.hooks import site as using_site

from ZODB.interfaces import IConnection

import transaction

from nti.dataserver import interfaces as nti_interfaces

@contextlib.contextmanager
def trivial_transaction_in_root_site():
	"""
	A context manager for running a transaction
	and either committing or aborting it after
	running the body; the body is run in a site
	set up as the root IDataserver site.

	This context manager is trivial because it supports
	no retry logic or any fancy error handling.
	"""

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
