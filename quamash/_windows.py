# © 2014 Mark Harviston <mark.harviston@gmail.com>
# © 2014 Arve Knudsen <arve.knudsen@gmail.com>
# BSD License

"""Windows specific Quamash functionality."""

import asyncio

try:
	import _winapi
	from asyncio import windows_events
	from asyncio import _overlapped
except ImportError:  # noqa
	pass  # w/o guarding this import py.test can't gather doctests on platforms w/o _winapi

import math

from . import QtCore
from ._common import with_logger

UINT32_MAX = 0xffffffff


class _ProactorEventLoop(QtCore.QObject, asyncio.ProactorEventLoop):

	"""Proactor based event loop."""

	def __init__(self):
		QtCore.QObject.__init__(self)
		asyncio.ProactorEventLoop.__init__(self, _IocpProactor())

		self.__event_poller = _EventPoller()
		self.__event_poller.sig_events.connect(self._process_events)

	def _process_events(self, events):
		"""Process events from proactor."""
		for f, callback, transferred, key, ov in events:
			try:
				self._logger.debug('Invoking event callback {}'.format(callback))
				value = callback(transferred, key, ov)
			except OSError as e:
				self._logger.warn('Event callback failed: {}'.format(e))
				f.set_exception(e)
			else:
				f.set_result(value)

	def _before_run_forever(self):
		self.__event_poller.start(self._proactor)

	def _after_run_forever(self):
		self.__event_poller.stop()


baseclass = _ProactorEventLoop


@with_logger
class _IocpProactor(windows_events.IocpProactor):
	def __init__(self):
		self.__events = []
		super(_IocpProactor, self).__init__()

	def select(self, timeout=None):
		"""Override in order to handle events in a threadsafe manner."""
		if not self.__events:
			self._poll(timeout)
		tmp = self.__events
		self.__events = []
		return tmp

	def close(self):
		self._logger.debug('Closing')
		super(_IocpProactor, self).close()

	def _poll(self, timeout=None):
		"""Override in order to handle events in a threadsafe manner."""
		if timeout is None:
			ms = UINT32_MAX  # wait for eternity
		elif timeout < 0:
			raise ValueError("negative timeout")
		else:
			# GetQueuedCompletionStatus() has a resolution of 1 millisecond,
			# round away from zero to wait *at least* timeout seconds.
			ms = math.ceil(timeout * 1e3)
			if ms >= UINT32_MAX:
				raise ValueError("timeout too big")

		while True:
			# self._logger.debug('Polling IOCP with timeout {} ms in thread {}...'.format(
			# 	ms, threading.get_ident()))
			status = _overlapped.GetQueuedCompletionStatus(self._iocp, ms)
			if status is None:
				break

			err, transferred, key, address = status
			try:
				f, ov, obj, callback = self._cache.pop(address)
			except KeyError:
				# key is either zero, or it is used to return a pipe
				# handle which should be closed to avoid a leak.
				if key not in (0, _overlapped.INVALID_HANDLE_VALUE):
					_winapi.CloseHandle(key)
				ms = 0
				continue

			if obj in self._stopped_serving:
				f.cancel()
			# Futures might already be resolved or cancelled
			elif not f.done():
				self.__events.append((f, callback, transferred, key, ov))

			ms = 0


@with_logger
class _EventWorker(QtCore.QThread):
	def __init__(self, proactor, parent):
		super().__init__()

		self.__stop = False
		self.__proactor = proactor
		self.__sig_events = parent.sig_events
		self.__semaphore = QtCore.QSemaphore()

	def start(self):
		super().start()
		self.__semaphore.acquire()

	def stop(self):
		self.__stop = True
		# Wait for thread to end
		self.wait()

	def run(self):
		self._logger.debug('Thread started')
		self.__semaphore.release()

		while not self.__stop:
			events = self.__proactor.select(0.01)
			if events:
				self._logger.debug('Got events from poll: {}'.format(events))
				self.__sig_events.emit(events)

		self._logger.debug('Exiting thread')


@with_logger
class _EventPoller(QtCore.QObject):

	"""Polling of events in separate thread."""

	sig_events = QtCore.Signal(list)

	def start(self, proactor):
		self._logger.debug('Starting (proactor: {})...'.format(proactor))
		self.__worker = _EventWorker(proactor, self)
		self.__worker.start()

	def stop(self):
		self._logger.debug('Stopping worker thread...')
		self.__worker.stop()
