# © 2013 Mark Harviston <mark.harviston@gmail.com>
# © 2014 Arve Knudsen <arve.knudsen@gmail.com>
# BSD License
import asyncio
import locale
import logging
import sys
import ctypes
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import socket

import quamash

import pytest


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
	return quamash.QApplication.instance() or quamash.QApplication([])


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
	params=[None, quamash.QThreadExecutor, ThreadPoolExecutor, ProcessPoolExecutor]
)
def executor(request):
	exc_cls = request.param
	if exc_cls is None:
		return None

	exc = exc_cls(1)  # FIXME? fixed number of workers?
	request.addfinalizer(exc.shutdown)
	return exc


class TestCanRunTasksInExecutor:
	"""
	This needs to be a class because pickle can't serialize closures,
	but can serialize bound methods.
	multiprocessing can only handle pickleable functions.
	"""
	def test_can_run_tasks_in_executor(self, loop, executor):
		"""Verify that tasks can be run in an executor."""
		logging.debug('Loop: {!r}'.format(loop))
		logging.debug('Executor: {!r}'.format(executor))

		manager = multiprocessing.Manager()
		was_invoked = manager.Value(ctypes.c_int, 0)
		logging.debug('running until complete')
		loop.run_until_complete(self.blocking_task(loop, executor, was_invoked))
		logging.debug('ran')

		assert was_invoked.value == 1

	def blocking_func(self, was_invoked):
		logging.debug('start blocking_func()')
		was_invoked.value = 1
		logging.debug('end blocking_func()')

	@asyncio.coroutine
	def blocking_task(self, loop, executor, was_invoked):
		logging.debug('start blocking task()')
		fut = loop.run_in_executor(executor, self.blocking_func, was_invoked)
		yield from asyncio.wait_for(fut, timeout=5.0)
		logging.debug('start blocking task()')


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


@pytest.fixture
def sock_pair(request):
	"""Create socket pair.

	If socket.socketpair isn't available, we emulate it.
	"""
	def fin():
		if client_sock is not None:
			client_sock.close()
		if srv_sock is not None:
			srv_sock.close()

	client_sock = srv_sock = None
	request.addfinalizer(fin)

	# See if socketpair() is available.
	have_socketpair = hasattr(socket, 'socketpair')
	if have_socketpair:
		client_sock, srv_sock = socket.socketpair()
		return client_sock, srv_sock

	# Create a non-blocking temporary server socket
	temp_srv_sock = socket.socket()
	temp_srv_sock.setblocking(False)
	temp_srv_sock.bind(('', 0))
	port = temp_srv_sock.getsockname()[1]
	temp_srv_sock.listen(1)

	# Create non-blocking client socket
	client_sock = socket.socket()
	client_sock.setblocking(False)
	try:
		client_sock.connect(('localhost', port))
	except socket.error as err:
		# Error 10035 (operation would block) is not an error, as we're doing this with a
		# non-blocking socket.
		if err.errno != 10035:
			raise

	# Use select to wait for connect() to succeed.
	import select
	timeout = 1
	readable = select.select([temp_srv_sock], [], [], timeout)[0]
	if temp_srv_sock not in readable:
		raise Exception('Client socket not connected in {} second(s)'.format(timeout))
	srv_sock, _ = temp_srv_sock.accept()

	return client_sock, srv_sock


def test_can_add_reader(loop, sock_pair):
	"""Verify that we can add a reader callback to an event loop."""
	def can_read():
		data = srv_sock.recv(1)
		if len(data) != 1:
			return

		nonlocal got_msg
		got_msg = data
		# Indicate that we're done
		fut.set_result(None)

	def write():
		client_sock.send(ref_msg)
		client_sock.close()

	ref_msg = b'a'
	client_sock, srv_sock = sock_pair
	loop.call_soon(write)

	got_msg = None
	fut = asyncio.Future()
	loop.add_reader(srv_sock.fileno(), can_read)
	assert len(loop._read_notifiers) == 1, 'Notifier should be added'
	loop.run_until_complete(asyncio.wait_for(fut, timeout=1.0))

	assert got_msg == ref_msg


def test_can_remove_reader(loop, sock_pair):
	"""Verify that we can remove a reader callback from an event loop."""
	def can_read():
		data = srv_sock.recv(1)
		if len(data) != 1:
			return

		nonlocal got_msg
		got_msg = data

	client_sock, srv_sock = sock_pair

	got_msg = None
	loop.add_reader(srv_sock.fileno(), can_read)
	loop.remove_reader(srv_sock.fileno())
	assert not loop._read_notifiers, 'Notifier should be removed'
	client_sock.send(b'a')
	client_sock.close()
	# Run for a short while to see if we get a read notification
	loop.call_later(0.1, loop.stop)
	loop.run_forever()

	assert got_msg is None, 'Should not have received a read notification'


def test_can_add_writer(loop, sock_pair):
	"""Verify that we can add a writer callback to an event loop."""
	def can_write():
		# Indicate that we're done
		fut.set_result(None)

	client_sock, srv_sock = sock_pair
	fut = asyncio.Future()
	loop.add_writer(client_sock.fileno(), can_write)
	assert len(loop._write_notifiers) == 1, 'Notifier should be added'
	loop.run_until_complete(asyncio.wait_for(fut, timeout=1.0))


def test_can_remove_writer(loop, sock_pair):
	"""Verify that we can remove a writer callback from an event loop."""
	def can_write():
		pass

	client_sock, srv_sock = sock_pair
	loop.add_writer(client_sock.fileno(), can_write)
	loop.remove_writer(client_sock.fileno())
	assert not loop._write_notifiers, 'Notifier should be removed'
