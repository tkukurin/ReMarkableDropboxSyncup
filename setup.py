#!/usr/bin/env python
from distutils.core import setup

setup(
  name = 'tkdbox',
  description = '',
  url = 'https://tkukurin.github.io',
  keywords = 'python remarkable dropbox',
  author = 'Toni Kukurin',
  author_email = 'tkukurin@gmail.com',
  version = '0.0.1',
  license = 'GNU',
  packages=['tkdbox'],
  package_dir={'tkdbox': 'src/tkukurin'},
  #package_data={'mypkg': ['data/*.dat']},
  install_requires = [],
  scripts=['scripts/tkdbox'],
)
