=======
Quamash
=======
Implementation of the `PEP 3156`_ Event-Loop with Qt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:author: Mark Harviston <mark.harviston@gmail.com>, Arve Knudsen <arve.knudsen@gmail.com>

.. image:: https://pypip.in/version/quamash/badge.svg
    :target: https://pypi.python.org/pypi/quamash/
    :alt: Latest Version

.. image:: https://pypip.in/download/quamash/badge.svg
    :target: https://pypi.python.org/pypi//quamash/
    :alt: Downloads

.. image:: https://pypip.in/py_versions/quamash/badge.svg
    :target: https://pypi.python.org/pypi/quamash/
    :alt: Supported Python versions

.. image:: https://pypip.in/license/quamash/badge.svg
    :target: https://pypi.python.org/pypi/quamash/
    :alt: License

.. image:: https://pypip.in/status/quamash/badge.svg
    :target: https://pypi.python.org/pypi/quamash/
    :alt: Development Status

.. image:: https://travis-ci.org/harvimt/quamash.png?branch=master
    :target: https://travis-ci.org/harvimt/quamash
    :alt: Build Status

Requirements
============
Quamash requires Python 3.4 and either PyQt4, PyQt5 or PySide.

Installation
============
``pip install quamash``

Usage
=====

.. code:: python

    import sys
    import asyncio
    import time

    from PyQt5.QtWidgets import QApplication, QProgressBar
    from quamash import QEventLoop, QThreadExecutor

    app = QApplication(sys.argv)
    progress = QProgressBar()
    loop = QEventLoop(app)

    progress.setRange(0, 99)
    progress.show()

    @asyncio.coroutine
    def master():
        yield from first_50()
        with QThreadExecutor(1) as exec:
            yield from loop.run_in_executor(exec, last_50)
        # TODO announce completion?

    @asyncio.coroutine
    def first_50():
        for i in range(50):
            progress.setValue(i)
            yield from asyncio.sleep(.1)

    def last_50():
        for i in range(50,100):
            loop.call_soon_threadsafe(progress.setValue, i)
            time.sleep(.1)

    with loop:
        loop.run_until_complete(master())

Changelog
=========

Version 0.4.1
-------------

* Improvements to PEP-3156 Conformance
* Minor Test Improvements

Version 0.4
-----------
* Major improvements to tests
    - integration with Travis CI
    - more tests
    - all tests pass
    - cross platform/configuration tests
* Bug #13 discovered and fixed
* Force which Qt Implementation to use with ``QUQMASH_QTIMPL`` environment variable.
* Implement ``QEventLoop.remove_reader`` and ``QEventLoop.remove_writer``
* PyQt4 Support
* PyQt5 Support
* Support ``multiprocessing`` executors (``ProcessPoolExecutor``))
* Improvements to code quality

Version 0.3
-----------
First version worth using.


Testing
=======
Quamash is tested with pytest_; in order to run the test suite, just install pytest
and execute py.test on the commandline. The tests themselves are beneath the 'tests' directory.

Testing can also be done with tox_. The current tox setup in tox.ini requires PyQT4/5 and PySide to
be installed globally. (pip can't install PyQt into a virtualenv which is what tox will try to do).
For this reason it may be good to run tox tests while specificying which environments to run. e.g.
``tox -e py34-pyqt5`` to test python 3.4 with PyQt5. It is unlikely this tox configuration will
work well on Windows especially since PyQt5 and PyQt4 cannot coexist in the same python installation
on Windows. Also the PyQt4 w/ Qt5 oddity appears to be mostly a windows only thing too.

Style testing is also handled by tox. Run ``tox -e flake8``. Similarly run ``tox -e coverage`` to
generate a coverage report.

Continuous Integration & Supported Platforms
--------------------------------------------
This project uses Travis CI to perform continuous integration. This works well, but has some limited
scope. Travis only tests PySide on Linux so this is the best tested platform. Windows is fairly well
tested semi-manually, but as yet no fully-automated Windows tests exist. FreeBSD, Mac OS X, and other
\*nix platforms should work, but haven't been thorougly tested.

License
=======
You may use, modify, and redistribute this software under the terms of the `BSD License`_.
See LICENSE.

Name
====
Tulip related projects are being named after other flowers, Quamash is one of the few flowers that
starts with a "Q".

.. _`PEP 3156`: http://legacy.python.org/dev/peps/pep-3156/
.. _`pytest`: http://pytest.org
.. _`BSD License`: http://opensource.org/licenses/BSD-2-Clause
.. _tox: https://tox.readthedocs.org/
