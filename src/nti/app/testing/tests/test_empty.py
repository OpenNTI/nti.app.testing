#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904,W0611

__import__('nti.app.testing')
__import__('nti.app.testing.base')
__import__('nti.app.testing.matchers')
__import__('nti.app.testing.request_response')


def test_empty():
    return
