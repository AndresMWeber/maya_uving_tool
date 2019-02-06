import codecs
import os
import sys
from setuptools import setup, find_packages
from setuptools.command.install import install

name = 'maya-uving-tool'
__author__ = 'Andres Weber'
__author_email__ = 'andresmweber@gmail.com'
__url__ = 'https://github.com/andresmweber/%s' % __package__

with codecs.open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'README.md'), encoding='utf-8') as readme:
    long_description = readme.read()

description = 'A tool for atlasing UVs.'

install_requires = [
    'rectangle-packer'
]

tests_requires = [
]


dev_requires = [
]

setup(
    name=name,
    version='0.1.0',
    packages=find_packages(exclude=['tests', '*.tests', '*.tests.*']),
    package_data={'configYML': ['nomenclate/core/*.yml']},
    include_package_data=True,
    url=__url__,
    license='MIT',
    author=__author__,
    author_email=__author_email__,
    description=description,
    long_description="Nada.",
    keywords='uving',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Development Status :: 4 - Beta',
        'Natural Language :: English',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',
        'Operating System :: Unix',
        'Programming Language :: Python :: 2.7',
        'Topic :: Documentation :: Sphinx',
        'Topic :: Multimedia :: Graphics :: 3D Modeling',
    ],
    install_requires=install_requires,
    extras_require={
        'tests': tests_requires,
        'dev': dev_requires
    }
)
