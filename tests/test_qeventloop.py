import asyncio
import os.path
import logging
import sys
try:
    from PyQt5.QtWidgets import QApplication
except ImportError:
    from PySide.QtGui import QApplication
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import quamash


logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')


@pytest.fixture
def loop(request):
    app = QApplication([])
    lp = quamash.QEventLoop(app)
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

    def test_can_function_as_context_manager(self):
        app = QApplication([])

        with quamash.QEventLoop(app) as loop:
            assert isinstance(loop, quamash.QEventLoop)
            loop.call_soon(loop.stop)
            loop.run_forever()
