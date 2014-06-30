import asyncio
import os.path
import logging
import sys
from PyQt5.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import quamash


logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')


class TestQEventLoop:
    def test_can_run_tasks_in_default_executor(self):
        """Verify that tasks can be run in default (threaded) executor."""
        def blocking_func():
            nonlocal was_invoked
            was_invoked = True

        @asyncio.coroutine
        def blocking_task():
            yield from loop.run_in_executor(None, blocking_func)

        app = QApplication([])
        was_invoked = False

        loop = quamash.QEventLoop(app)
        with loop:
            loop.run_until_complete(blocking_task())

        assert was_invoked