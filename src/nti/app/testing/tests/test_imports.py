#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

import unittest
import importlib


def _make_import_test(mod_name=None, root='nti.app.testing'):
    def test(self):
        parts = [root]
        if mod_name:
            parts.append(mod_name)
        mod = importlib.import_module('.'.join(parts))
        self.assertIsNotNone(mod)
    return test


class TestModuleImportSideEffects(unittest.TestCase):
    """
    A TestCase defining tests that import a set of modules from this
    package.
    """

    for mod_name in (None, 'base', 'matchers', 'request_response'):
        test_name = 'test_' + (mod_name if mod_name else 'root')
        test = _make_import_test(mod_name)
        test.__name__ = test_name
        locals()[test_name] = test


def test_suite():
    return unittest.defaultTestLoader.loadTestsFromName(__name__)
