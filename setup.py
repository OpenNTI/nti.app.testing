#!/usr/bin/env python
from setuptools import setup, find_packages
import codecs

VERSION = '0.0.0'

entry_points = {
}

setup(
	name = 'nti.app.testing',
	version = VERSION,
	author = 'Jason Madden',
	author_email = 'jason@nextthought.com',
	description = "Testing support for application-layer code",
	long_description = codecs.open('README.rst', encoding='utf-8').read(),
	license = 'Proprietary',
	keywords = 'pyramid testing',
	#url = 'https://github.com/NextThought/nti.nose_traceback_info',
	classifiers = [
		'Intended Audience :: Developers',
		'Natural Language :: English',
		'Operating System :: OS Independent',
		'Programming Language :: Python :: 2',
		'Programming Language :: Python :: 2.7',
		'Topic :: Software Development :: Testing'
		'Framework :: Pyramid',
	],
	packages=find_packages('src'),
	package_dir={'': 'src'},
	namespace_packages=['nti', 'nti.app'],
	install_requires=[
		'setuptools',
		'nose',
		'pyhamcrest',
		'nti.testing'
	],
	entry_points=entry_points
)
