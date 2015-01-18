import sys
import os.path
import logging
from pytest import fixture
sys.path.insert(0, os.path.dirname(__file__))
logging.basicConfig(
	level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

if os.name == 'nt':
	collect_ignore = ['quamash/_unix.py']
else:
	collect_ignore = ['quamash/_windows.py']


@fixture(scope='session')
def application():
	from quamash import QApplication
	return QApplication([])
