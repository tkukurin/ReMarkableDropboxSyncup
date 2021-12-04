#!/usr/bin/env python
from distutils.core import setup

setup(
  name='tkdbox',
  description='A DropBox sync util.',
  url='https://tkukurin.github.io',
  keywords='python remarkable dropbox',
  author='Toni Kukurin',
  author_email='tkukurin@gmail.com',
  version='0.0.1',
  license='GNU',
  packages=['tkdbox'],
  package_dir={'tkdbox': 'tk'},
  install_requires=[],
  scripts=['scripts/tkdbox'],
)
