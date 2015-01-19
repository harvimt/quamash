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

.. image:: https://travis-ci.org/harvimt/quamash.svg?branch=master
    :target: https://travis-ci.org/harvimt/quamash
    :alt: Linux (Travis CI) Build Status

.. image:: https://ci.appveyor.com/api/projects/status/github/harvimt/quamash?branch=master&svg=true
    :target: https://ci.appveyor.com/project/harvimt/quamash/branch/master
    :alt: Windows (Appveyor) Build Status

.. image:: https://badges.gitter.im/Join%20Chat.svg
    :target: https://gitter.im/harvimt/quamash?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge
    :alt: Gitter

Requirements
============
Quamash requires Python 3.4 or Python 3.3 with the backported ``asycnio`` library and either PyQt4, PyQt5 or PySide.

Installation
============
``pip install quamash``

Upgrade from Version 0.4 to 0.5
===============================
The loop context manager will no longer set the event loop only close it.

Instead of:

.. code:: python

    with loop:
        loop.run_forever()

do:

.. code:: python

    asyncio.set_event_loop(loop)
    # ...
    with loop:
        loop.run_forever()

It is recommended that you call ``asyncio.set_event_loop`` as early as possible (immediately after instantiating the loop),
to avoid running asynchronous code before ``asyncio.set_event_loop`` is called.

If you're using multiple different loops in the same application, you know what you're doing (or at least you hope you do),
then you can ignore this advice.


Usage
=====

.. code:: python

    import sys
    import asyncio
    import time

    from PyQt5.QtWidgets import QApplication, QProgressBar
    from quamash import QEventLoop, QThreadExecutor

    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)  # NEW must set the event loop

    progress = QProgressBar()
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

    with loop: ## context manager calls .close() when loop completes, and releases all resources
        loop.run_until_complete(master())

Changelog
=========

Version 0.5.1
-------------
* Fixes rst syntax error in this README

Version 0.5
-----------
* Deprecation of event loop as means to ``asyncio.set_event_loop``, now must be called explicitly.
* Possible fix to notifiers being called out-of-order (see #25, #27, and e64119e)
* Better loop cleanup
* CI Tests pass on windows now
* Testing improvements
* Python 3.3 Support. (probably always supported, but it's offially supported/tested now)

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

Style testing is also handled by tox. Run ``tox -e flake8``.

Code Coverage
-------------
Getting a full coverage support is quite time consuming. In theory this could by done with `pytest-xdist`_,
but I haven't had time to make that work. Install ``pytest-cov`` with ``pip install pytest-cov`` then
run ``py.test --cov quamash`` then append a dot and an identifier the generated ``.coverage`` file. For example,
``mv .coverage .coverage.nix.p33.pyside`` then repeat on all the platforms you want to run on. (at least linux
and windows). Put all the ``.coverage.*`` files in one directory that also has quamash source code in it.
``cd`` to that directory and run ``coverage combine`` finally run ``coverage html`` for html based reports
or ``coverage report`` for a simple report. These last commands may fail with errors about not being able to
find source code. Use the ``.coveragerc`` file to specify equivelant paths.  The default configuration has linux
source code in ``/quamash`` and windows source at ``C:\quamash``.

Continuous Integration & Supported Platforms
--------------------------------------------
This project uses Travis CI to perform tests on linux (Ubuntu 12.04 LTS "Precise Pangolin") and
Appveyor (Windows Server 2012 R2, similar to Windows 8) to perform continuous integration.

On linux, Python 3.3 and 3.4 with PySide, PyQt4, and PyQt5 are tested. On windows, Python 3.4 with
PySide, PyQt4 and PyQt5 are tested, but Python 3.3 is only tested with PySide since binary installers
for PyQt are not provided for Python 3.3 (at least not the newest versions of PyQt), and compiling 
from source probably isn't worth it.

License
=======
You may use, modify, and redistribute this software under the terms of the `BSD License`_.
See LICENSE.

Name
====
Tulip related projects are being named after other flowers, Quamash is one of the few flowers that
starts with a "Q".

.. _`PEP 3156`: http://python.org/dev/peps/pep-3156/
.. _`pytest`: http://pytest.org
.. _`BSD License`: http://opensource.org/licenses/BSD-2-Clause
.. _tox: https://tox.readthedocs.org/
.. _pytest-xdist: https://pypi.python.org/pypi/pytest-xdist
