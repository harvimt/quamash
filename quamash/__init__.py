#!/usr/bin/env python3
# -*- coding=utf-8 -*- #
# © 2013 Mark Harviston <mark.harviston@gmail.com>
# © 2014 Arve Knudsen <arve.knudsen@gmail.com>
# BSD License
"""
Implementation of the PEP 3156 Event-Loop with Qt
"""
__author__ = 'Mark Harviston <mark.harviston@gmail.com>, Arve Knudsen <arve.knudsen@gmail.com>'
__version__ = '0.2'
__license__ = 'BSD 2 Clause License'

import sys
import os
import asyncio
import time
from functools import wraps
from queue import Queue
from concurrent.futures import Future
import threading

try:
	from PySide import QtCore
except ImportError:
	from PyQt5 import QtCore
	QtCore.Signal = QtCore.pyqtSignal

from ._common import with_logger


@with_logger
class _EventPoller(QtCore.QObject):
	"""Polling of events in separate thread."""
	sig_events = QtCore.Signal(list)

	def __init__(self, selector):
		super(_EventPoller, self).__init__()
		self.__semaphore = threading.Semaphore(0)
		self.__selector = selector

	def start(self):
		self.__canceled = False
		self._logger.debug('Starting')
		threading.Thread(target=self.__run).start()
		# Wait for thread to start
		self.__semaphore.acquire()

	def stop(self):
		self._logger.debug('Stopping')
		self.__canceled = True
		# Wait for thread to end
		self.__semaphore.acquire()

	def __run(self):
		self.__semaphore.release()

		while not self.__canceled:
			events = self.__selector.select(0.01)
			if events:
				self._logger.debug('Got events {}'.format(events))
			if events:
				self.sig_events.emit(events)

		self.__semaphore.release()


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
		while not self.__stop:
			future, callback, args, kwargs = self.__queue.get()
			self._logger.debug('#{} got callback {} with args {} and kwargs {} from queue'
				.format(self.__num, callback, args, kwargs))
			if future.set_running_or_notify_cancel():
				self._logger.debug('Invoking callback')
				r = callback(*args, **kwargs)
				self._logger.debug('Setting Future result: {}'.format(r))
				future.set_result(r)
			else:
				self._logger.debug('Future was cancelled')

		self._logger.debug('#{} stopped'.format(self.__num))

	def stop(self):
		self._logger.debug('#{} stopping...'.format(self.__num))
		self.__stop = True


@with_logger
class QThreadExecutor(QtCore.QObject):
	"""
	ThreadExecutor that produces QThreads
	Same API as `concurrent.futures.Executor`

	>>> with QThreadExecutor(5) as executor:
	>>>     f = executor.submit(lambda x: 2 + x, x)
	>>>     r = f.result()
	>>>     assert r == 4
	"""
	def __init__(self, max_workers=10, parent=None):
		super().__init__(parent)
		self.__max_workers = max_workers
		self.__queue = Queue()
		self.__workers = [_QThreadWorker(self.__queue, i+1) for i in range(max_workers)]
		for w in self.__workers:
			w.start()

	def submit(self, callback, *args, **kwargs):
		future = Future()
		self._logger.debug(
			'Submitting callback {} with args {} and kwargs {} to thread worker queue'
			.format(callback, args, kwargs))
		self.__queue.put((future, callback, args, kwargs))
		return future

	def map(self, func, *iterables, timeout=None):
		raise NotImplemented("use as_completed on the event loop")

	def close(self):
		self._logger.debug('Closing')
		for w in self.__workers:
			w.stop()

	def __enter__(self, *args):
		return self

	def __exit__(self, *args):
		self.close()


def _easycallback(fn):
	"""
	Decorator that wraps a callback in a signal, and packs & unpacks arguments,
	Makes the wrapped function effectively threadsafe. If you call the function
	from one thread, it will be executed in the thread the QObject has affinity
	with.

	Remember: only objects that inherit from QObject can support signals/slots

	>>> class MyObject(QObject):
	>>>     @_easycallback
	>>>     def mycallback(self):
	>>>         dostuff()
	>>>
	>>> myobject = MyObject()
	>>>
	>>> @task
	>>> def mytask():
	>>>     myobject.mycallback()
	>>>
	>>> loop = QEventLoop()
	>>> with loop:
	>>>     loop.call_soon(mytask)
	>>>     loop.run_forever()
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
	_selector_cls = _windows.selector_cls
else:
	from . import _unix
	_baseclass = _unix.baseclass
	_selector_cls = _unix.selector_cls


@with_logger
class QEventLoop(QtCore.QObject, _baseclass):
	"""
	Implementation of asyncio event loop that uses the Qt Event loop
	>>> @quamash.task
	>>> def my_task(x):
	>>>     return x + 2
	>>>
	>>> app = QApplication()
	>>> with QEventLoop(app) as loop:
	>>>     y = loop.call_soon(my_task)
	>>>
	>>>     assert y == 4
	"""
	def __init__(self, app):
		self.__timers = []
		self.__app = app
		self.__is_running = False
		self.__debug_enabled = False
		self.__default_executor = None
		self.__exception_handler = None

		super(QEventLoop, self).__init__()
		_baseclass.__init__(self, _selector_cls())

		self.__event_poller = _EventPoller(self._selector)
		self.__event_poller.sig_events.connect(self.__on_events)

	def run_forever(self):
		"""Run eventloop forever."""
		def stop_io_event_loop():
			self.__io_event_loop.stop()
			self._logger.debug('IO event loop stopped')
			semaphore.release()

		self.__start_io_event_loop()

		semaphore = threading.Semaphore(0)
		self.__is_running = True
		self._logger.debug('Starting Qt event loop')
		try:
			self._logger.debug('Starting event poller')
			self.__event_poller.start()
			rslt = self.__app.exec_()
			self._logger.debug('Qt event loop ended with result {}'.format(rslt))
			return rslt
		finally:
			self._logger.debug('Stopping event poller')
			self.__event_poller.stop()
			self._logger.debug('Stopping IO event loop...')
			self.__io_event_loop.call_soon_threadsafe(stop_io_event_loop)
			with semaphore:
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
			self._logger.debug('Not running')
			return

		self._logger.debug('Stopping eventloop...')
		self.__app.exit()
		self._logger.debug('Stopped eventloop')

	def is_running(self):
		"""Is event loop running?"""
		return self.__is_running

	def close(self):
		"""Close event loop."""
		self.__timers = []
		self.__app = None
		if self.__default_executor is not None:
			self.__default_executor.close()
		super(QEventLoop, self).close()

	def call_later(self, delay, callback, *args):
		"""Register callback to be invoked after a certain delay."""
		if asyncio.iscoroutinefunction(callback):
			raise TypeError("coroutines cannot be used with call_later")
		if not callable(callback):
			raise TypeError('callback must be callable: {}'.format(type(callback).__name__))

		self._logger.debug(
			'Registering callback {} to be invoked with arguments {} after {} second(s)'
			.format(
				callback, args, delay
			))

		def upon_timeout():
			self.__timers.remove(timer)
			self._logger.debug('Callback timer fired, calling {} with args {}'.format(
				callback, args))
			callback(*args)

		timer = QtCore.QTimer(self.__app)
		timer.timeout.connect(upon_timeout)
		timer.setSingleShot(True)
		timer.start(delay * 1000)
		self.__timers.append(timer)

		return _Cancellable(timer, self)

	def call_soon(self, callback, *args):
		self.call_later(0, callback, *args)

	def call_at(self, when, callback, *args):
		"""Register callback to be invoked at a certain time."""
		self.call_later(when - self.time(), callback, *args)

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

		if executor is None:
			executor = self.__default_executor
			if executor is None:
				self._logger.debug('Creating default executor')
				executor = self.__default_executor = QThreadExecutor()
			self._logger.debug('Using default executor')

		return asyncio.wrap_future(executor.submit(callback, *args))

	def set_default_executor(self, executor):
		self.__default_executor = executor

	# Signal handling.

	def add_signal_handler(self, sig, callback, *args):
		return self.__handler_helper(self.add_signal_handler, sig, callback, *args)

	def remove_signal_handler(self, sig):
		return self.__handler_helper(self.remove_signal_handler, sig)

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
		self._logger.debug('Executing default exception handler')
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
		super(QEventLoop, self).set_debug(enabled)
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

	def __on_events(self, events):
		for f, callback, transferred, key, ov in events:
			try:
				self._logger.debug('Invoking event callback {}'.format(callback))
				value = callback(transferred, key, ov)
			except OSError as e:
				self._logger.warn('Event callback failed: {}'.format(e))
				f.set_exception(e)
			else:
				f.set_result(value)

	def __handler_helper(self, target, *args):
		semaphore = threading.Semaphore(0)
		handler = None

		def helper_target():
			nonlocal handler
			handler = target(*args)
			semaphore.release()

		self.__io_event_loop.call_soon_threadsafe(helper_target)
		with semaphore:
			return handler

	def __start_io_event_loop(self):
		"""Start the I/O event loop which we defer to for performing I/O on another thread.
		"""
		self._logger.debug('Starting IO event loop...')
		self.__event_loop_started = threading.Semaphore(0)
		threading.Thread(target=self.__io_event_loop_thread).start()
		with self.__event_loop_started:
			self._logger.debug('IO event loop started')

	def __io_event_loop_thread(self):
		"""Worker thread for running the I/O event loop."""
		io_event_loop = asyncio.get_event_loop_policy().new_event_loop()
		assert isinstance(io_event_loop, asyncio.AbstractEventLoop)
		io_event_loop.set_debug(self.__debug_enabled)
		asyncio.set_event_loop(io_event_loop)
		self.__io_event_loop = io_event_loop
		self.__io_event_loop.call_soon(self.__event_loop_started.release)
		self.__io_event_loop.run_forever()

	@staticmethod
	def __log_error(*args, **kwds):
		# In some cases, the error method itself fails, don't have a lot of options in that case
		try:
			self._logger.error(*args, **kwds)
		except:
			sys.stderr.write('{}, {}\n'.format(args, kwds))


class _Cancellable:
	def __init__(self, timer, loop):
		self.__timer = timer
		self.__loop = loop

	def cancel(self):
		self.__loop.remove(timer)
		self.__timer.stop()
