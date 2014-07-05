import asyncio
import os.path
import logging
import sys
import locale
try:
	from PyQt5.QtWidgets import QApplication
except ImportError:
	from PySide.QtGui import QApplication
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import quamash


logging.basicConfig(
	level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')


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


class TestQEventLoop:
	def test_can_run_tasks_in_default_executor(self, loop):
		"""Verify that tasks can be run in default (threaded) executor."""
		def blocking_func():
			nonlocal was_invoked
			was_invoked = True

		@asyncio.coroutine
		def blocking_task():
			yield from loop.run_in_executor(None, blocking_func)

		was_invoked = False
		loop.run_until_complete(blocking_task())

		assert was_invoked

	def test_can_execute_subprocess(self, loop):
		"""Verify that a subprocess can be executed."""
		transport, protocol = loop.run_until_complete(loop.subprocess_exec(
			_SubprocessProtocol, 'python', '-c', 'print(\'Hello async world!\')'))
		loop.run_forever()
		assert transport.get_returncode() == 0
		assert protocol.received_stdout == 'Hello async world!'

	def test_can_terminate_subprocess(self, loop):
		"""Verify that a subprocess can be terminated."""
		# Start a never-ending process
		transport = loop.run_until_complete(loop.subprocess_exec(
				_SubprocessProtocol, 'python', '-c', 'import time\nwhile True: time.sleep(1)'))[0]
		# Terminate!
		transport.kill()
		# Wait for process to die
		loop.run_forever()

		assert transport.get_returncode() != 0

	def test_can_function_as_context_manager(self, application):
		"""Verify that a QEventLoop can function as its own context manager."""
		with quamash.QEventLoop(application) as loop:
			assert isinstance(loop, quamash.QEventLoop)
			loop.call_soon(loop.stop)
			loop.run_forever()
