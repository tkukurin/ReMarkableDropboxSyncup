#!/usr/bin/env python
from setuptools import setup

setup(
  name='tkdbox',
  python_requires=">=3.10",
  description='A DropBox sync util.',
  url='https://tkukurin.github.io',
  keywords='python remarkable dropbox',
  author='Toni Kukurin',
  author_email='tkukurin@gmail.com',
  version='0.0.2',
  license='GNU',
  packages=['tk'],
  package_dir={'tk': 'tk'},
  install_requires=['requests'],
  scripts=['bin/tkdbox'],
)
