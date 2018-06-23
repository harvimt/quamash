import os
import logging
logger = logging.getLogger('quamash')


class QtModule:
	def __init__(self):
		self.name = os.environ.get('QUAMASH_QTIMPL', None)
		if self.name is None:
			self.root = None
		else:
			logger.info('Forcing use of {} as Qt Implementation'.format(self.name))
			self.root = __import__(self.name)

		if self.root is None:
			for name in ('PyQt5', 'PyQt4', 'PySide'):
				try:
					self.root = __import__(name)
					self.name = name
				except ImportError:
					continue
				else:
					break
			else:
				raise ImportError('No Qt implementations found')
		logger.info('Using Qt Implementation: {}'.format(self.name))

		self.signal = self._signal()
		self.qapplication = self._qapplication()

	def import_(self, name):
		return __import__('{}.{}'.format(self.name, name), fromlist=(self.name,))

	def _qapplication(self):
		if self.name == 'PyQt5':
			module = 'QtWidgets'
		else:
			module = 'QtGui'
		return self.import_(module).QApplication

	def _signal(self):
		core = self.import_('QtCore')
		try:
			return core.Signal
		except AttributeError:
			return core.pyqtSignal
