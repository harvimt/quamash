"""Implementation of the PEP 3156 Event-Loop with Qt."""


# © 2014 Mark Harviston <mark.harviston@gmail.com>
# © 2014 Arve Knudsen <arve.knudsen@gmail.com>
# BSD License

__author__ = 'Mark Harviston <mark.harviston@gmail.com>, Arve Knudsen <arve.knudsen@gmail.com>'
__version__ = '0.6.1'
__url__ = 'https://github.com/harvimt/quamash'
__license__ = 'BSD'
__all__ = ['QEventLoop', 'QThreadExecutor', 'QtModuleName']

import os
import logging
import importlib
logger = logging.getLogger('quamash')

try:
	QtModuleName = os.environ['QUAMASH_QTIMPL']
except KeyError:
	QtModule = None
else:
	logger.info('Forcing use of {} as Qt Implementation'.format(QtModuleName))
	QtModule = importlib.import_module(QtModuleName)

if not QtModule:
	for QtModuleName in ('PyQt6', 'PyQt5', 'PyQt4', 'PySide'):
		try:
			QtModule = importlib.import_module(QtModuleName)
		except ImportError:
			continue
		else:
			from . import _qtmodule
			_qtmodule.QtModuleName = QtModuleName
			from ._init import *
			break
	else:
		logger.warning('No Qt implementations found')
