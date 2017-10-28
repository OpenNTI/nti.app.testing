import codecs
from setuptools import setup, find_packages

entry_points = {
}


def _read(fname):
    with codecs.open(fname, encoding='utf-8') as f:
        return f.read()


setup(
    name='nti.app.testing',
    version=_read('version.txt').strip(),
    author='Jason Madden',
    author_email='jason@nextthought.com',
    description="Testing support for application-layer code",
    long_description=(
        _read('README.rst')
        + '\n\n'
        + _read("CHANGES.rst")
    ),
    license='Apache',
    keywords='pyramid testing',
    classifiers=[
        'Framework :: Pyramid',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Topic :: Software Development :: Testing',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
    url="https://github.com/NextThought/nti.app.testing",
    zip_safe=True,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    namespace_packages=['nti', 'nti.app'],
    install_requires=[
        'setuptools',
        'nti.app.pyramid_zope',
        'nti.contentlibrary',
        'nti.ntiids',
        'nti.monkey',
        'nti.property',
        'nti.testing',
        'nti.wsgi.cors',
        'Paste',
        'PyHamcrest',
        'pyramid',
        'six',
        'transaction',
        'WebOb',
        'WebTest',
        'ZODB',
        'zope.component',
        'zope.testing',
    ],
    extras_require={
        'docs': [
            'Sphinx',
            'repoze.sphinx.autointerface',
            'sphinx_rtd_theme',
        ]
    },
    entry_points=entry_points,
)
