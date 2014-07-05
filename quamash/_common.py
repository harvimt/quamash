import logging
try:
	from PySide import QtCore
except ImportError:
	from PyQt5 import QtCore
	QtCore.Signal = QtCore.pyqtSignal


def with_logger(cls):
	"""Class decorator to add a logger to a class."""
	attr_name = '_logger'
	cls_name = cls.__qualname__
	module = cls.__module__
	if module is not None:
		cls_name = module + '.' + cls_name
	setattr(cls, attr_name, logging.getLogger(cls_name))
	return cls
