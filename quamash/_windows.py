import threading
import _winapi
import asyncio
from asyncio import windows_events
from asyncio import _overlapped
import math

from ._common import with_logger, QtCore


class _ProactorEventLoop(QtCore.QObject, asyncio.ProactorEventLoop):
	def __init__(self):
		QtCore.QObject.__init__(self)
		asyncio.ProactorEventLoop.__init__(self, _IocpProactor())

		self.__event_poller = _EventPoller()
		self.__event_poller.sig_events.connect(self._process_events)

	def _process_events(self, events):
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
		self.__event_poller.start(self._selector)

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
		INFINITE = 0xffffffff

		if timeout is None:
			ms = INFINITE
		elif timeout < 0:
			raise ValueError("negative timeout")
		else:
			# GetQueuedCompletionStatus() has a resolution of 1 millisecond,
			# round away from zero to wait *at least* timeout seconds.
			ms = math.ceil(timeout * 1e3)
			if ms >= INFINITE:
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
			elif not f.cancelled():
				self.__events.append((f, callback, transferred, key, ov))

			ms = 0


@with_logger
class _EventWorker(QtCore.QThread):
	def __init__(self, selector, parent):
		super().__init__()

		self.__stop = False
		self.__selector = selector
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
			events = self.__selector.select(0.01)
			if events:
				self._logger.debug('Got events from poll: {}'.format(events))
				self.__sig_events.emit(events)

		self._logger.debug('Exiting thread')


@with_logger
class _EventPoller(QtCore.QObject):
	"""Polling of events in separate thread."""
	sig_events = QtCore.Signal(list)

	def start(self, selector):
		self._logger.debug('Starting (selector: {})...'.format(selector))
		self.__worker = _EventWorker(selector, self)
		self.__worker.start()

	def stop(self):
		self._logger.debug('Stopping worker thread...')
		self.__worker.stop()
