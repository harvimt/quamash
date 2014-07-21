# © 2014 Mark Harviston <mark.harviston@gmail.com>
# © 2014 Arve Knudsen <arve.knudsen@gmail.com>
# BSD License
"""
Implementation of the PEP 3156 Event-Loop with Qt
"""
__author__ = 'Mark Harviston <mark.harviston@gmail.com>, Arve Knudsen <arve.knudsen@gmail.com>'
__version__ = '0.3'
__license__ = 'BSD'

import sys
import os
import asyncio
import time
from functools import wraps
from queue import Queue
from concurrent.futures import Future

for QtModuleName in ('PyQt5', 'PyQt4', 'PySide'):
	try:
		QtModule = __import__(QtModuleName)
	except ImportError:
		continue
	else:
		break
else:
	raise ImportError('No Qt implementations found')

QtCore = __import__(QtModuleName + '.QtCore', fromlist=(QtModuleName,))

try:
	QtGui = __import__(QtModuleName + '.QtWidgets', fromlist=(QtModuleName,))
except ImportError:
	QtGui = __import__(QtModuleName + '.QtGui', fromlist=(QtModuleName,))


if not hasattr(QtCore, 'Signal'):
	QtCore.Signal = QtCore.pyqtSignal


from ._common import with_logger


@with_logger
class _QThreadWorker(QtCore.QThread):
	"""
	Read from the queue.

	For use by the QThreadExecutor
	"""
	def __init__(self, queue, num):
		self.__queue = queue
		self.__stop = False
		self.__num = num
		super().__init__()

	def run(self):
		queue = self.__queue
		while True:
			command = queue.get()
			if command is None:
				# Stopping...
				break

			future, callback, args, kwargs = command
			self._logger.debug(
				'#{} got callback {} with args {} and kwargs {} from queue'
				.format(self.__num, callback, args, kwargs)
			)
			if future.set_running_or_notify_cancel():
				self._logger.debug('Invoking callback')
				try:
					r = callback(*args, **kwargs)
				except Exception as err:
					self._logger.debug('Setting Future exception: {}'.format(err))
					future.set_exception(err)
				else:
					self._logger.debug('Setting Future result: {}'.format(r))
					future.set_result(r)
			else:
				self._logger.debug('Future was cancelled')

		self._logger.debug('Thread #{} stopped'.format(self.__num))

	def wait(self):
		self._logger.debug('Waiting for thread #{} to stop...'.format(self.__num))
		super().wait()


@with_logger
class QThreadExecutor(QtCore.QObject):
	"""
	ThreadExecutor that produces QThreads
	Same API as `concurrent.futures.Executor`

	>>> from quamash import QThreadExecutor
	>>> with QThreadExecutor(5) as executor:
	...     f = executor.submit(lambda x: 2 + x, 2)
	...     r = f.result()
	...     assert r == 4
	"""
	def __init__(self, max_workers=10, parent=None):
		super().__init__(parent)
		self.__max_workers = max_workers
		self.__queue = Queue()
		self.__workers = [_QThreadWorker(self.__queue, i + 1) for i in range(max_workers)]
		self.__been_shutdown = False

		for w in self.__workers:
			w.start()

	def submit(self, callback, *args, **kwargs):
		if self.__been_shutdown:
			raise RuntimeError("QThreadExecutor has been shutdown")

		future = Future()
		self._logger.debug(
			'Submitting callback {} with args {} and kwargs {} to thread worker queue'
			.format(callback, args, kwargs))
		self.__queue.put((future, callback, args, kwargs))
		return future

	def map(self, func, *iterables, timeout=None):
		raise NotImplementedError("use as_completed on the event loop")

	def shutdown(self):
		if self.__been_shutdown:
			raise RuntimeError("QThreadExecutor has been shutdown")

		self.__been_shutdown = True

		self._logger.debug('Shutting down')
		for i in range(len(self.__workers)):
			# Signal workers to stop
			self.__queue.put(None)
		for w in self.__workers:
			w.wait()

	def __enter__(self, *args):
		if self.__been_shutdown:
			raise RuntimeError("QThreadExecutor has been shutdown")
		return self

	def __exit__(self, *args):
		self.shutdown()


def _easycallback(fn):
	"""
	Decorator that wraps a callback in a signal, and packs & unpacks arguments,
	Makes the wrapped function effectively threadsafe. If you call the function
	from one thread, it will be executed in the thread the QObject has affinity
	with.

	Remember: only objects that inherit from QObject can support signals/slots

	>>> import asyncio
	>>>
	>>> import quamash
	>>> from quamash import QEventLoop, QtCore, QtGui
	>>> QThread, QObject = quamash.QtCore.QThread, quamash.QtCore.QObject
	>>>
	>>> app = QtCore.QCoreApplication.instance() or QtGui.QApplication([])
	>>>
	>>> global_thread = QThread.currentThread()
	>>> class MyObject(QObject):
	...     @_easycallback
	...     def mycallback(self):
	...         global global_thread, mythread
	...         cur_thread = QThread.currentThread()
	...         assert cur_thread is not global_thread
	...         assert cur_thread is mythread
	>>>
	>>> mythread = QThread()
	>>> mythread.start()
	>>> myobject = MyObject()
	>>> myobject.moveToThread(mythread)
	>>>
	>>> @asyncio.coroutine
	... def mycoroutine():
	...     myobject.mycallback()
	>>>
	>>> loop = QEventLoop(app)
	>>> with loop:
	...     loop.run_until_complete(mycoroutine())
	"""
	@wraps(fn)
	def in_wrapper(self, *args, **kwargs):
		return signaler.signal.emit(self, args, kwargs)

	class Signaler(QtCore.QObject):
		signal = QtCore.Signal(object, tuple, dict)

	signaler = Signaler()
	signaler.signal.connect(lambda self, args, kwargs: fn(self, *args, **kwargs))
	return in_wrapper


if os.name == 'nt':
	from . import _windows
	_baseclass = _windows.baseclass
else:
	from . import _unix
	_baseclass = _unix.baseclass


@with_logger
class QEventLoop(_baseclass):
	"""
	Implementation of asyncio event loop that uses the Qt Event loop

	>>> import quamash, asyncio
	>>> from quamash import QtCore, QtGui
	>>> app = QtCore.QCoreApplication.instance() or QtGui.QApplication([])
	>>>
	>>> @asyncio.coroutine
	... def xplusy(x, y):
	...     yield from asyncio.sleep(.1)
	...     assert x + y == 4
	...     yield from asyncio.sleep(.1)
	>>>
	>>> with QEventLoop(app) as loop:
	...     loop.run_until_complete(xplusy(2, 2))
	"""
	def __init__(self, app=None):
		self.__timers = []
		self.__app = app or QtCore.QCoreApplication.instance()
		self.__is_running = False
		self.__debug_enabled = False
		self.__default_executor = None
		self.__exception_handler = None

		assert self.__app is not None

		super().__init__()

	def run_forever(self):
		"""Run eventloop forever."""
		self.__is_running = True
		self._before_run_forever()
		try:
			self._logger.debug('Starting Qt event loop')
			rslt = self.__app.exec_()
			self._logger.debug('Qt event loop ended with result {}'.format(rslt))
			return rslt
		finally:
			self._after_run_forever()
			self.__is_running = False

	def run_until_complete(self, future):
		"""Run until Future is complete."""
		self._logger.debug('Running {} until complete'.format(future))
		future = asyncio.async(future, loop=self)
		stop = lambda *args: self.stop()
		future.add_done_callback(stop)
		try:
			self.run_forever()
		finally:
			future.remove_done_callback(stop)
		if not future.done():
			raise RuntimeError('Event loop stopped before Future completed.')

		self._logger.debug('Future {} finished running'.format(future))
		return future.result()

	def stop(self):
		"""Stop event loop."""
		if not self.__is_running:
			self._logger.debug('Already stopped')
			return

		self._logger.debug('Stopping event loop...')
		self.__app.exit()
		self._logger.debug('Stopped event loop')

	def is_running(self):
		"""Is event loop running?"""
		return self.__is_running

	def close(self):
		"""Close event loop."""
		self.__timers = []
		self.__app = None
		if self.__default_executor is not None:
			self.__default_executor.shutdown()
		super().close()

	def call_later(self, delay, callback, *args):
		"""Register callback to be invoked after a certain delay."""
		if asyncio.iscoroutinefunction(callback):
			raise TypeError("coroutines cannot be used with call_later")
		if not callable(callback):
			raise TypeError('callback must be callable: {}'.format(type(callback).__name__))

		self._logger.debug(
			'Registering callback {} to be invoked with arguments {} after {} second(s)'
			.format(callback, args, delay))
		return self._add_callback(asyncio.Handle(callback, args, self), delay)

	def _add_callback(self, handle, delay=0):
		def upon_timeout():
			self.__timers.remove(timer)
			self._logger.debug('Callback timer fired, calling {}'.format(handle))
			handle._run()

		self._logger.debug('Adding callback {} with delay {}'.format(handle, delay))
		timer = QtCore.QTimer(self.__app)
		timer.timeout.connect(upon_timeout)
		timer.setSingleShot(True)
		timer.start(delay * 1000)
		self.__timers.append(timer)

		return _Cancellable(timer, self)

	def call_soon(self, callback, *args):
		return self.call_later(0, callback, *args)

	def call_at(self, when, callback, *args):
		"""Register callback to be invoked at a certain time."""
		return self.call_later(when - self.time(), callback, *args)

	def time(self):
		"""Get time according to event loop's clock."""
		return time.monotonic()

	# Methods for interacting with threads.

	@_easycallback
	def call_soon_threadsafe(self, callback, *args):
		"""Thread-safe version of call_soon."""
		self.call_soon(callback, *args)

	def run_in_executor(self, executor, callback, *args):
		"""Run callback in executor.

		If no executor is provided, the default executor will be used, which defers execution to
		a background thread.
		"""
		self._logger.debug('Running callback {} with args {} in executor'.format(callback, args))
		if isinstance(callback, asyncio.Handle):
			assert not args
			assert not isinstance(callback, asyncio.TimerHandle)
			if callback.cancelled:
				f = asyncio.Future()
				f.set_result(None)
				return f
			callback, args = callback.callback, callback.args

		executor = executor or self.__default_executor
		if executor is None:
			self._logger.debug('Creating default executor')
			executor = self.__default_executor = QThreadExecutor()
		self._logger.debug('Using default executor')

		return asyncio.wrap_future(executor.submit(callback, *args))

	def set_default_executor(self, executor):
		self.__default_executor = executor

	# Error handlers.

	def set_exception_handler(self, handler):
		self.__exception_handler = handler

	def default_exception_handler(self, context):
		"""Default exception handler.

		This is called when an exception occurs and no exception
		handler is set, and can be called by a custom exception
		handler that wants to defer to the default behavior.

		context parameter has the same meaning as in
		`call_exception_handler()`.
		"""
		self._logger.debug('Default exception handler executing')
		message = context.get('message')
		if not message:
			message = 'Unhandled exception in event loop'

		try:
			exception = context['exception']
		except KeyError:
			exc_info = False
		else:
			exc_info = (type(exception), exception, exception.__traceback__)

		log_lines = [message]
		for key in [k for k in sorted(context) if k not in {'message', 'exception'}]:
			log_lines.append('{}: {!r}'.format(key, context[key]))

		self.__log_error('\n'.join(log_lines), exc_info=exc_info)

	def call_exception_handler(self, context):
		if self.__exception_handler is None:
			try:
				self.default_exception_handler(context)
			except Exception:
				# Second protection layer for unexpected errors
				# in the default implementation, as well as for subclassed
				# event loops with overloaded "default_exception_handler".
				self.__log_error('Exception in default exception handler', exc_info=True)

			return

		try:
			self.__exception_handler(self, context)
		except Exception as exc:
			# Exception in the user set custom exception handler.
			try:
				# Let's try the default handler.
				self.default_exception_handler({
					'message': 'Unhandled error in custom exception handler',
					'exception': exc,
					'context': context,
				})
			except Exception:
				# Guard 'default_exception_handler' in case it's
				# overloaded.
				self.__log_error(
					'Exception in default exception handler while handling an unexpected error '
					'in custom exception handler', exc_info=True)

	# Debug flag management.

	def get_debug(self):
		return self.__debug_enabled

	def set_debug(self, enabled):
		super().set_debug(enabled)
		self.__debug_enabled = enabled

	def __enter__(self):
		asyncio.set_event_loop(self)
		return self

	def __exit__(self, *args):
		try:
			self.stop()
			self.close()
		finally:
			asyncio.set_event_loop(None)

	@classmethod
	def __log_error(cls, *args, **kwds):
		# In some cases, the error method itself fails, don't have a lot of options in that case
		try:
			cls._logger.error(*args, **kwds)
		except:
			sys.stderr.write('{!r}, {!r}\n'.format(args, kwds))


class _Cancellable:
	def __init__(self, timer, loop):
		self.__timer = timer
		self.__loop = loop

	def cancel(self):
		self.__timer.stop()
