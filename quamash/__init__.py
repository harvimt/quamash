#!/usr/bin/env python3
# -*- coding=utf-8 -*- #
# © 2013 Mark Harviston <mark.harviston@gmail.com>
# BSD License
"""
PEP
"""
__author__ = 'Mark Harviston <mark.harviston@gmail.com>'
__version__ = '0.1'
__license__ = 'BSD 2 Clause License'

import tulip as async

import time
from functools import partial, wraps
import sys
import logging  # noqa
import requests
import feedparser
from queue import Queue
from concurrent.futures import Future

from .guievents import GuiEventLoop

try:
	from PySide import QtGui, QtCore
except ImportError:
	from PyQt4 import QtGui, QtCore


class QThreadWorker(QtCore.QThread):
	"""
	Read from the queue.

	For use by the QThreadExecutor
	"""
	def __init__(self, queue):
		self.queue = queue
		self.STOP = False
		super().__init__()

	def run(self):
		while not self.STOP:
			future, fn, args, kwargs = self.queue.get()
			if future.set_running_or_notify_cancel():
				r = fn(*args, **kwargs)
				future.set_result(r)

	def stop(self):
		self.STOP = True


class QThreadExecutor(QtCore.QObject):
	"""
	ThreadExecutor that produces QThreads
	Same API as `concurrent.futures.Executor`

	>>> with QThreadExecutor(5) as executor:
	>>>     f = executor.submit(lambda x: 2 + x, x)
	>>>     r = f.result()
	>>>     assert r == 4
	"""
	def __init__(self, max_workers, parent=None):
		super().__init__(parent)
		self.max_workers = max_workers
		self.queue = Queue()
		self.workers = [QThreadWorker(self.queue, loop) for i in range(max_workers)]
		for w in self.workers:
			w.start()

	def submit(self, fn, *args, **kwargs):
		future = Future()
		self.queue.put((future, fn, args, kwargs))
		return future

	def map(self, func, *iterables, timeout=None):
		raise NotImplemented("use as_completed on the event loop")

	def shutdown(self, wait=True):
		map(lambda w: w.stop(), self.workers)

	def __enter__(self, *args):
		pass

	def __exit__(self, *args):
		self.shutdown()


class QEventLoop(QtCore.QObject, GuiEventLoop):
	"""
	Implementation of tulip event loop that uses the Qt Event loop
	>>> @qumash.task
	>>> def my_task(x):
	>>>     return x + 2
	>>>
	>>> app = QApplication()
	>>> with QEventLoop(app) as loop:
	>>>     y = loop.call_soon(my_task)
	>>>
	>>>     assert y == 4
	"""

	def __init__(self, app=None):
		super().__init__()
		self.timers = []

	# Event Loop API
	def run(self):
		"""Run the event loop.  Block until there is nothing left to do."""
		return self.run_forever()

	def __enter__(self):
		async.set_event_loop(self)

	def __exit__(self, *args):
		self.stop()
		async.set_event_loop(None)

	def close(self):
		self.stop()
		self.timers = []
		self.app = None

	@easycallback
	def call_soon_threadsafe(self, fn, *args):
		self.call_soon(fn, *args)

	def _create_timer(self, delay, fn, *args, singleshot):
		timer = QtCore.QTimer(self.app)
		timer.timeout.connect(partial(fn, *args))
		if singleshot:
			timer.timeout.connect(lambda: self.timers.remove(timer))
		timer.setSingleShot(singleshot)
		timer.start(delay * 1000)

		self.timers.append(timer)

		return Cancellable(timer)

	def call_later(self, delay, fn, *args):
		self._create_timer(delay, fn, *args, singleshot=True)

	def call_at(self, at, fn, *args):
		self.call_later(at - self.time(), fn, *args)

	def time(self):
		return time.monotonic()

	def run_forever(self):
		return self.app.exec_()

	def stop(self):
		super().stop()
		self.app.exit()

class Cancellable(object):
	def __init__(self, timer, loop):
		self.timer = timer
		self.loop = loop

	def cancel(self):
		self.loop.remove(timer)
		return self.timer.stop()

def easycallback(fn):
	"""
	Decorator that wraps a callback in a signal, and packs & unpacks arguments,
	Makes the wrapped function effectively threadsafe. If you call the function
	from one thread, it will be executed in the thread the QObject has affinity
	with.

	Remember: only objects that inherit from QObject can support signals/slots

	>>> class MyObject(QObject):
	>>>     @easycallback
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
	signal = QtCore.pyqtSignal(object, tuple, dict)

	def out_wrapper(self, args, kwargs):
		return fn(self, *args, **kwargs)

	@wraps(fn)
	def in_wrapper(self, *args, **kwargs):
		return signal.emit(self, args, kwargs)

	signal.connect(out_wrapper)
	return in_wrapper
