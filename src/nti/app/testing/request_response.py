#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

__test__ = False

from hamcrest import is_
from hamcrest import assert_that

from pyramid.decorator import reify

from pyramid.response import Response as _Response

from pyramid.testing import DummyRequest as _DummyRequest

from webob import BaseRequest as _BaseRequest

from nti.testing.matchers import TypeCheckedDict

logger = __import__('logging').getLogger(__name__)


class _HeaderList(list):

    # TODO: Very incomplete, but append is the main method
    # used by webob
    def __init__(self, other=()):
        list.__init__(self)
        for k in other:
            self.append(k)

    def append(self, k):
        __traceback_info__ = k
        assert_that(k[0], is_(str), "Header names must be byte strings")
        assert_that(k[1], is_(str), "Header values must be byte strings")
        list.append(self, k)


class ByteHeadersResponse(_Response):

    def __init__(self, *args, **kwargs):
        super(ByteHeadersResponse, self).__init__(*args, **kwargs)
        # make the list be right, which is directly assigned to in the
        # super, bypassing the property
        self.headerlist = self._headerlist

    def _headerlist__set(self, value):
        """
        Ensure type checking of the headers.
        """
        super(ByteHeadersResponse, self)._headerlist__set(value)
        if not isinstance(self._headerlist, _HeaderList):
            self._headerlist = _HeaderList(self._headerlist)

    headerlist = property(_Response._headerlist__get, _headerlist__set,
                          _Response._headerlist__del, doc=_Response._headerlist__get.__doc__)


class ByteHeadersDummyRequest(_DummyRequest):

    def __init__(self, **kwargs):
        if 'headers' in kwargs:
            old_headers = kwargs['headers']
            headers = TypeCheckedDict(str, str, self._on_set_header)
            for k, v in old_headers.items():
                headers[k] = v
            kwargs['headers'] = headers
        else:
            kwargs['headers'] = TypeCheckedDict(str, str, self._on_set_header)
        super(ByteHeadersDummyRequest, self).__init__(**kwargs)

    def _on_set_header(self, key, val):
        pass

    @reify
    def response(self):
        return ByteHeadersResponse()
        # NOTE: The super implementation consults the registry to find a
        # factory.


class DummyRequest(ByteHeadersDummyRequest):

    possible_site_names = ()
    if_unmodified_since = None

    def _on_set_header(self, key, val):
        __traceback_info__ = key, val
        from nti.appserver.tweens.zope_site_tween import _get_possible_site_names
        site_names = _get_possible_site_names(self)
        self.possible_site_names = tuple(site_names)

    @classmethod
    def blank(cls, *args, **kwargs):
        # Pyramid's testing request doesn't have this for some reason
        return _BaseRequest.blank(*args, **kwargs)
