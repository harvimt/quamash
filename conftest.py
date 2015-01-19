import sys
import os.path
import logging
from importlib import import_module
from pytest import fixture
sys.path.insert(0, os.path.dirname(__file__))
logging.basicConfig(
	level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

if os.name == 'nt':
	collect_ignore = ['quamash/_unix.py']
else:
	collect_ignore = ['quamash/_windows.py']


def pytest_addoption(parser):
	parser.addoption("--qtimpl", default='PySide')


@fixture(scope='session')
def application(request):
	qtimpl = request.config.getoption('qtimpl')
	__import__(qtimpl)
	for module in ('.QtWidgets', '.QtGui'):
		try:
			return import_module(module, qtimpl).QApplication([])
		except (ImportError, AttributeError):
			continue


@fixture(scope='session')
def qtcore(request):
	qtimpl = request.config.getoption('qtimpl')
	__import__(qtimpl)
	return import_module('.QtCore', qtimpl)
