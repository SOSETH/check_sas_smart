#!/usr/bin/env python3

from setuptools import setup

setup(name='check_sas_smart',
      version='0.1',
      description='Check SMART values of SAS disks',
      author='Maximilian Falkenstein',
      author_email='mfalkenstein@sos.ethz.ch',
      url='https://github.com/SOSETH/check_sas_smart',
      scripts=['bin/check_sas_smart'],
)
