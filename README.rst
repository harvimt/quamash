=======
Quamash
=======
Implementation of the PEP 3156 Event-Loop with Qt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:author: Mark Harviston <mark.harviston@gmail.com>

Usage
=====

.. code:: python

    import quamash
    import tulip
    import time

    from PyQt4 import QtCore, QtGui
    # - or - #
    from PySide import QtCore, QtGui

    def identity(x):
        time.sleep(10)
        return x

    @quamash.task
    def my_task(loop, executor):
        for x in range(5):
            y = yield from loop.run_in_executor(executor, identity, x)
            assert x == y

        loop.stop()

    if __name__ == '__main__':
        app = QApplication
        loop = quamash.QEventLoop(app)
        executor = quamash.QThreadExecutor(5)

        win = QtGui.QMainWindow()
        win.show()

        with loop, executor:
            loop.call_soon(my_task, loop, executor)
            loop.run_forever()


Name
====
Tulip related projects are being named after other flowers, Quamash is one of the few flowers that starts with a "Q".

License
=======
BSD 2 Clause License


.. image:: https://d2weczhvl823v0.cloudfront.net/harvimt/quamash/trend.png
   :alt: Bitdeli badge
   :target: https://bitdeli.com/free

