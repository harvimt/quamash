import asyncio
import locale
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor  # noqa

try:
	from PyQt5.QtWidgets import QApplication
except ImportError:
	from PySide.QtGui import QApplication
import pytest

import quamash


class _SubprocessProtocol(asyncio.SubprocessProtocol):
	def __init__(self, *args, **kwds):
		super(_SubprocessProtocol, self).__init__(*args, **kwds)
		self.received_stdout = None

	def pipe_data_received(self, fd, data):
		text = data.decode(locale.getpreferredencoding(False))
		if fd == 1:
			self.received_stdout = text.strip()

	def process_exited(self):
		asyncio.get_event_loop().stop()


@pytest.fixture(scope='session')
def application():
	app = QApplication([])
	return app


@pytest.fixture
def loop(request, application):
	lp = quamash.QEventLoop(application)
	asyncio.set_event_loop(lp)

	def fin():
		try:
			lp.close()
		finally:
			asyncio.set_event_loop(None)

	request.addfinalizer(fin)
	return lp


@pytest.fixture(
	params=[None, quamash.QThreadExecutor, ThreadPoolExecutor],
	#  ProcessPoolExecutor may never work
)
def executor(request):
	exc_cls = request.param
	if exc_cls is None:
		return None

	exc = exc_cls(1)  # FIXME? fixed number of workers?
	request.addfinalizer(exc.shutdown)
	return exc


def test_can_run_tasks_in_executor(loop, executor):
	"""Verify that tasks can be run in an executor."""
	logging.debug('Executor: {!r}'.format(executor))

	def blocking_func():
		logging.debug('start blocking_func()')
		nonlocal was_invoked
		was_invoked = True
		logging.debug('end blocking_func()')

	@asyncio.coroutine
	def blocking_task():
		logging.debug('start blocking task()')
		fut = loop.run_in_executor(executor, blocking_func)
		yield from asyncio.wait_for(fut, timeout=1.0)
		logging.debug('start blocking task()')

	was_invoked = False
	logging.debug('running until complete')
	loop.run_until_complete(blocking_task())
	logging.debug('ran')

	assert was_invoked


def test_can_handle_exception_in_default_executor(loop):
	"""Verify that exceptions from tasks run in default (threaded) executor are handled."""
	def blocking_func():
		raise Exception('Testing')

	with pytest.raises(Exception) as excinfo:
		loop.run_until_complete(loop.run_in_executor(None, blocking_func))

	assert str(excinfo.value) == 'Testing'


def test_can_execute_subprocess(loop):
	"""Verify that a subprocess can be executed."""
	transport, protocol = loop.run_until_complete(loop.subprocess_exec(
		_SubprocessProtocol, sys.executable or 'python', '-c', 'print(\'Hello async world!\')'))
	loop.run_forever()
	assert transport.get_returncode() == 0
	assert protocol.received_stdout == 'Hello async world!'


def test_can_terminate_subprocess(loop):
	"""Verify that a subprocess can be terminated."""
	# Start a never-ending process
	transport = loop.run_until_complete(
		loop.subprocess_exec(
			_SubprocessProtocol, sys.executable or 'python', '-c', 'import time\nwhile True: time.sleep(1)',
		),
	)[0]
	# Terminate!
	transport.kill()
	# Wait for process to die
	loop.run_forever()

	assert transport.get_returncode() != 0


def test_loop_running(loop):
	"""Verify that loop.is_running returns True when running"""
	@asyncio.coroutine
	def is_running():
		nonlocal loop
		assert loop.is_running()

	loop.run_until_complete(is_running())


def test_loop_not_running(loop):
	"""Verify that loop.is_running returns False when not running"""
	assert not loop.is_running()


def test_can_function_as_context_manager(application):
	"""Verify that a QEventLoop can function as its own context manager."""
	with quamash.QEventLoop(application) as loop:
		assert isinstance(loop, quamash.QEventLoop)
		loop.call_soon(loop.stop)
		loop.run_forever()


def test_future_not_done_on_loop_shutdown(loop):
	"""Verify RuntimError occurs when loop stopped before Future completed with run_until_complete."""
	loop.call_later(1, loop.stop)
	fut = asyncio.Future()
	with pytest.raises(RuntimeError):
		loop.run_until_complete(fut)


def test_call_later_must_not_coroutine(loop):
	"""Verify TypeError occurs call_later is given a coroutine."""
	mycoro = asyncio.coroutine(lambda: None)

	with pytest.raises(TypeError):
		loop.call_soon(mycoro)


def test_call_later_must_be_callable(loop):
	"""Verify TypeError occurs call_later is not given a callable."""
	not_callable = object()
	with pytest.raises(TypeError):
		loop.call_soon(not_callable)


def test_call_at(loop):
	"""Verify that loop.call_at works as expected."""
	def mycallback():
		nonlocal was_invoked
		was_invoked = True
	was_invoked = False

	loop.call_at(loop.time() + .1, mycallback)
	loop.run_until_complete(asyncio.sleep(.5))

	assert was_invoked


def test_get_set_debug(loop):
	"""Verify get_debug and set_debug work as expected."""
	loop.set_debug(True)
	assert loop.get_debug()
	loop.set_debug(False)
	assert not loop.get_debug()
