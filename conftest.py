import sys
import os.path
import logging
from pytest import fixture
sys.path.insert(0, os.path.dirname(__file__))

try:
	import colorlog
	handler = colorlog.StreamHandler()

	formatter = colorlog.ColoredFormatter(
		"%(log_color)s%(levelname)-8s%(reset)s %(name)-32s %(message)s",
		datefmt=None,
		reset=True,
		log_colors={
			'DEBUG': 'cyan',
			'INFO': 'green',
			'WARNING': 'yellow',
			'ERROR': 'red',
			'CRITICAL': 'red,bg_white',
		},
		secondary_log_colors={},
		style='%',
	)
	handler.setFormatter(formatter)
	logger = colorlog.getLogger()
	logger.addHandler(handler)
	logger.setLevel(logging.DEBUG)
except ImportError:
	logging.basicConfig(
		level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

if os.name == 'nt':
	collect_ignore = ['quamash/_unix.py']
else:
	collect_ignore = ['quamash/_windows.py']


@fixture(scope='session')
def application():
	from quamash import QtCore
	return QtCore.QCoreApplication([])
