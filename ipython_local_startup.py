#!/usr/local/bin/python2.7
from __future__ import print_function

import os
import sys

print("hello from ipython_local_startup.py in ",  os.getcwd())

import index
from index.models import InstlItemModel
from index.models import create_install_items_db
