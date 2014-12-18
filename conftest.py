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

_app = None

@fixture
def app():
	from PyQt5.QtWidgets import QApplication
	global _app
	if _app is None:
		_app = QApplication([])
	return _app
