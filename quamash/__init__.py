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

import asyncio
from asyncio import tasks
import asyncio.events
import socket
import time
from functools import partial, wraps
import logging
from queue import Queue
from concurrent.futures import Future
import subprocess
import threading

try:
    from PySide import QtCore
except ImportError:
    from PyQt5 import QtCore

_logger = logging.getLogger(__name__)


class _QThreadWorker(QtCore.QThread):
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
    def __init__(self, max_workers=10, parent=None):
        super().__init__(parent)
        self.__max_workers = max_workers
        self.__queue = Queue()
        self.__workers = [_QThreadWorker(self.__queue) for i in range(max_workers)]
        for w in self.__workers:
            w.start()

    def submit(self, fn, *args, **kwargs):
        future = Future()
        self.__queue.put((future, fn, args, kwargs))
        return future

    def map(self, func, *iterables, timeout=None):
        raise NotImplemented("use as_completed on the event loop")

    def close(self):
        for w in self.__workers:
            w.stop()

    def __enter__(self, *args):
        pass

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
    def out_wrapper(self, args, kwargs):
        return fn(self, *args, **kwargs)

    @wraps(fn)
    def in_wrapper(self, *args, **kwargs):
        return signaler.signal.emit(self, args, kwargs)

    class Signaler(QtCore.QObject):
        signal = QtCore.pyqtSignal(object, tuple, dict)

    signaler = Signaler()
    signaler.signal.connect(out_wrapper)
    return in_wrapper


class QEventLoop(QtCore.QObject, asyncio.events.AbstractEventLoop):
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
        super().__init__()

        self.__start_io_event_loop()
        self.__timers = []
        self.__app = app
        self.__is_running = False
        self.__debug_enabled = False
        self.__default_executor = None

    def run_forever(self):
        self.__is_running = True
        _logger.debug('Starting Qt event loop')
        try:
            rslt = self.__app.exec_()
            return rslt
        finally:
            self.__is_running = False

    def run_until_complete(self, future):
        """Run until Future is complete."""
        future = tasks.async(future, loop=self)
        future.add_done_callback(self.stop)
        self.run_forever()
        future.remove_done_callback(self.stop)
        if not future.done():
            raise RuntimeError('Event loop stopped before Future completed.')

        return future.result()

    def stop(self):
        """Stop event loop."""
        _logger.debug('Stopping eventloop...')
        self.__io_event_loop.call_soon_threadsafe(self.__io_event_loop.stop)
        self.__app.exit()
        _logger.debug('Stopped eventloop')

    def is_running(self):
        """Is event loop running?"""
        return self.__is_running

    def close(self):
        """Close event loop."""
        self.stop()
        self.__timers = []
        self.__app = None

    def call_later(self, delay, callback, *args):
        """Register callback to be invoked after a certain delay."""
        self.__create_timer(delay, callback, *args)

    def time(self):
        """Get time according to event loop's clock."""
        return time.monotonic()

    # Methods for interacting with threads.

    @_easycallback
    def call_soon_threadsafe(self, callback, *args):
        """Thread-safe version of call_soon."""
        self.call_soon(callback, *args)

    def call_at(self, when, callback, *args):
        """Register callback to be invoked at a certain time."""
        self.call_later(when - self.time(), callback, *args)

    def run_in_executor(self, executor, callback, *args):
        if isinstance(callback, events.Handle):
            assert not args
            assert not isinstance(callback, events.TimerHandle)
            if callback.cancelled:
                f = futures.Future()
                f.set_result(None)
                return f
            callback, args = callback.callback, callback.args

        if executor is None:
            executor = self.__default_executor
            if executor is None:
                executor = self.__default_executor = QThreadExecutor()
        return self.wrap_future(executor.submit(callback, *args))

    def set_default_executor(self, executor):
        self.__default_executor = executor

    # Network I/O methods returning Futures.

    def getaddrinfo(self, host, port, *, family=0, type_=0, proto=0, flags=0):
        return self._io_helper(
            self.__io_event_loop.getaddrinfo, (host, port), {
                'family': family, 'type': type_, 'proto': proto, 'flags': flags,
            })

    def getnameinfo(self, sockaddr, flags=0):
        return self._io_helper(self.__io_event_loop.getnameinfo, (sockaddr, flags), {})

    def create_connection(self, protocol_factory, host=None, port=None, *,
                          ssl=None, family=0, proto=0, flags=0, sock=None,
                          local_addr=None, server_hostname=None):
        raise NotImplementedError

    def create_connection(
            self, protocol_factory, host=None, port=None, *, ssl=None, family=0, proto=0, flags=0,
            sock=None, local_addr=None, server_hostname=None
    ):
        return self._io_helper(
            self.__io_event_loop.create_connection,
            (protocol_factory, host, port), {
                'family': family, 'proto': proto, 'flags': flags, 'sock': sock
            })

    def create_server(self, protocol_factory, host=None, port=None, *,
                      family=socket.AF_UNSPEC, flags=socket.AI_PASSIVE,
                      sock=None, backlog=100, ssl=None, reuse_address=None):
        """A coroutine which creates a TCP server bound to host and port.

        The return value is a Server object which can be used to stop
        the service.

        If host is an empty string or None all interfaces are assumed
        and a list of multiple sockets will be returned (most likely
        one for IPv4 and another one for IPv6).

        family can be set to either AF_INET or AF_INET6 to force the
        socket to use IPv4 or IPv6. If not set it will be determined
        from host (defaults to AF_UNSPEC).

        flags is a bitmask for getaddrinfo().

        sock can optionally be specified in order to use a preexisting
        socket object.

        backlog is the maximum number of queued connections passed to
        listen() (defaults to 100).

        ssl can be set to an SSLContext to enable SSL over the
        accepted connections.

        reuse_address tells the kernel to reuse a local socket in
        TIME_WAIT state, without waiting for its natural timeout to
        expire. If not specified will automatically be set to True on
        UNIX.
        """
        raise NotImplementedError

    def create_unix_connection(self, protocol_factory, path, *,
                               ssl=None, sock=None,
                               server_hostname=None):
        raise NotImplementedError

    def create_unix_server(self, protocol_factory, path, *,
                           sock=None, backlog=100, ssl=None):
        """A coroutine which creates a UNIX Domain Socket server.

        The return value is a Server object, which can be used to stop
        the service.

        path is a str, representing a file systsem path to bind the
        server socket to.

        sock can optionally be specified in order to use a preexisting
        socket object.

        backlog is the maximum number of queued connections passed to
        listen() (defaults to 100).

        ssl can be set to an SSLContext to enable SSL over the
        accepted connections.
        """
        raise NotImplementedError

    def create_datagram_endpoint(self, protocol_factory,
                                 local_addr=None, remote_addr=None, *,
                                 family=0, proto=0, flags=0):
        raise NotImplementedError

    # Pipes and subprocesses.

    def connect_read_pipe(self, protocol_factory, pipe):
        """Register read pipe in event loop.

        protocol_factory should instantiate object with Protocol interface.
        pipe is file-like object already switched to nonblocking.
        Return pair (transport, protocol), where transport support
        ReadTransport interface."""
        # The reason to accept file-like object instead of just file descriptor
        # is: we need to own pipe and close it at transport finishing
        # Can got complicated errors if pass f.fileno(),
        # close fd in pipe transport then close f and vise versa.
        raise NotImplementedError

    def connect_write_pipe(self, protocol_factory, pipe):
        """Register write pipe in event loop.

        protocol_factory should instantiate object with BaseProtocol interface.
        Pipe is file-like object already switched to nonblocking.
        Return pair (transport, protocol), where transport support
        WriteTransport interface."""
        # The reason to accept file-like object instead of just file descriptor
        # is: we need to own pipe and close it at transport finishing
        # Can got complicated errors if pass f.fileno(),
        # close fd in pipe transport then close f and vise versa.
        raise NotImplementedError

    def subprocess_shell(self, protocol_factory, cmd, *, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         **kwargs):
        raise NotImplementedError

    def subprocess_exec(self, protocol_factory, *args, stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        **kwargs):
        raise NotImplementedError

    # Ready-based callback registration methods.
    # The add_*() methods return None.
    # The remove_*() methods return True if something was removed,
    # False if there was nothing to delete.

    def add_reader(self, fd, callback, *args):
        return _ready_helper(self.__io_event_loop.add_reader, fd, callback, *args)

    def remove_reader(self, fd):
        return _ready_helper(self.__io_event_loop.remove_reader, fd)

    def add_writer(self, fd, callback, *args):
        return _ready_helper(self.__io_event_loop.add_writer, fd, callback, *args)

    def remove_writer(self, fd):
        return _ready_helper(self.__io_event_loop.remove_writer, fd)

    # Completion based I/O methods returning Futures.

    def sock_recv(self, sock, nbytes):
        return self._io_helper(
            self.__io_event_loop.sock_recv,
            (sock, nbytes),
            {},
        )

    def sock_sendall(self, sock, data):
        return self._io_helper(self.__io_event_loop.sock_sendall, (sock, data), {})

    def sock_connect(self, sock, address):
        return self._io_helper(self.__io_event_loop.sock_connect, (sock, address), {})

    def sock_accept(self, sock):
        return self._io_helper(self.__io_event_loop.sock_accept, (sock, ), {})

    # Signal handling.

    def __handler_helper(self, target, *args):
        lock = threading.Lock()
        lock.acquire()
        handler = None

        def helper_target():
            nonlocal handler
            handler = target(*args)
            lock.release()

        self.__io_event_loop.call_soon_threadsafe(helper_target)
        lock.acquire()
        return handler

    def add_signal_handler(self, sig, callback, *args):
        return self.__handler_helper(self.add_signal_handler, sig, callback, *args)

    def remove_signal_handler(self, sig):
        return self.__handler_helper(self.remove_signal_handler, sig)

    # Error handlers.

    def set_exception_handler(self, handler):
        raise NotImplementedError

    def default_exception_handler(self, context):
        raise NotImplementedError

    def call_exception_handler(self, context):
        raise NotImplementedError

    # Debug flag management.

    def get_debug(self):
        return self.__debug_enabled

    def set_debug(self, enabled):
        self.__debug_enabled = enabled
        return self.run_forever()

    def __enter__(self):
        asyncio.set_event_loop(self)

    def __exit__(self, *args):
        try:
            self.stop()
        finally:
            asyncio.set_event_loop(None)
            if self.__default_executor is not None:
                self.__default_executor.close()

    def __create_timer(self, delay, fn, *args):
        timer = QtCore.QTimer(self.__app)
        timer.timeout.connect(lambda: fn(*args))
        timer.timeout.connect(lambda: self.__timers.remove(timer))
        timer.setSingleShot(True)
        timer.start(delay * 1000)
        self.__timers.append(timer)

        return _Cancellable(timer, self)

    def __start_io_event_loop(self):
        """Start the I/O event loop which we defer to for performing I/O on another thread.
        """
        self.__event_loop_started = threading.Lock()
        self.__event_loop_started.acquire()
        threading.Thread(None, self.__io_event_loop_thread).start()
        self.__event_loop_started.acquire()

    def __io_event_loop_thread(self):
        """Worker thread for running the I/O event loop."""
        io_event_loop = asyncio.get_event_loop_policy().new_event_loop()
        assert isinstance(io_event_loop, asyncio.AbstractEventLoop)
        io_event_loop.set_debug(True)
        asyncio.set_event_loop(io_event_loop)
        self.__io_event_loop = io_event_loop
        self.__event_loop_started.release()
        self.__io_event_loop.run_forever()


class _Cancellable(object):
    def __init__(self, timer, loop):
        self.__timer = timer
        self.__loop = loop

    def cancel(self):
        self.__loop.remove(timer)
        return self.__timer.stop()
