=======
Quamash
=======
Implementation of the `PEP 3156`_ Event-Loop with Qt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
:author: Mark Harviston <mark.harviston@gmail.com>, Arve Knudsen <arve.knudsen@gmail.com>

.. image:: https://img.shields.io/pypi/v/quamash.svg
    :target: https://pypi.python.org/pypi/quamash/
    :alt: Latest Version

.. image:: https://img.shields.io/pypi/dm/quamash.svg
    :target: https://pypi.python.org/pypi/quamash/
    :alt: Downloads

.. image:: https://img.shields.io/pypi/pyversions/quamash.svg
    :target: https://pypi.python.org/pypi/quamash/
    :alt: Supported Python versions

.. image:: https://img.shields.io/pypi/l/quamash.svg
    :target: https://pypi.python.org/pypi/quamash/
    :alt: License

.. image:: https://img.shields.io/pypi/status/quamash.svg
    :target: https://pypi.python.org/pypi/quamash/
    :alt: Development Status

.. image:: https://travis-ci.org/harvimt/quamash.svg?branch=master
    :target: https://travis-ci.org/harvimt/quamash
    :alt: Linux (Travis CI) Build Status

.. image:: https://img.shields.io/appveyor/ci/harvimt/quamash.svg
    :target: https://ci.appveyor.com/project/harvimt/quamash/branch/master
    :alt: Windows (Appveyor) Build Status

.. image:: https://badges.gitter.im/Join%20Chat.svg
    :target: https://gitter.im/harvimt/quamash?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge
    :alt: Gitter

Requirements
============
Quamash requires Python 3.6 or later with PyQt5 or PySide2.

Installation
============
Quamash without dependencies:

``pip install quamash``

Quamash with PySide2 dependency for use in a PySide2 project:

``pip install quamash[pyside2]``

Quamash with PyQT5 dependency for use in a PyQT5 project:

``pip install quamash[pyqt5]``


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

    async def master():
        await first_50()
        with QThreadExecutor(1) as exec:
            await loop.run_in_executor(exec, last_50)
        # TODO announce completion?

    async def first_50():
        for i in range(50):
            progress.setValue(i)
            await asyncio.sleep(.1)

    def last_50():
        for i in range(50,100):
            loop.call_soon_threadsafe(progress.setValue, i)
            time.sleep(.1)

    with loop: ## context manager calls .close() when loop completes, and releases all resources
        loop.run_until_complete(master())

Changelog
=========
Version 0.7.0
-------------
* Dropped support for Python 3.3, 3.4, and 3.5 
* Dropped support for PyQt4 and PySide 
* Added support for PySide2 
* Tests now uses `tox` and wheels, no weird dependency management. 
* Now uses poetry to manage deps (though this transparent to users, who can use whatever) 
* setup.py no longer imports the package

Version 0.6.1
-------------
* Python 3.7 support (no automated test coverage)

Version 0.6.0
-------------
* Lots of bugfixes and performance improvements.

Version 0.5.5
-------------
* Fix `#62`_ a serious memory leak by switching from ``QTimer`` to ``QObject.timerEvent``.

Version 0.5.4
-------------
* Remove unnecessary QObjects
* Officially add Python 3.5 support (CI configuration and setup.py change)
* Fix `#55`_
* Better compatibility with behavior of default event loop (`#59`_)
* Remove _easycallback and replace with _makeSignaller

Version 0.5.3
-------------
* Fix to `#34`_

Version 0.5.2
-------------
* Fixes to tests, and CI configuration
* Fixes `#35`_ and `#31`_ (both minor bugs)
* Uploade wheels to PyPI

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
The full suite of tests can be run for the current platform with `tox`

If you have docker/docker-compose installed, `docker-compose run tox` will run the tests on linux (in docker).

Style testing is also handled by tox. Run ``tox -e flake8`` to run the style tests only.


Continuous Integration & Supported Platforms
--------------------------------------------
This project uses Travis CI to perform tests on linux and
Appveyor  to perform continuous integration.


License
=======
You may use, modify, and redistribute this software under the terms of the `BSD 2 Clause License`_.
See LICENSE.

Name
====
Tulip related projects are being named after other flowers, Quamash is one of the few flowers that
starts with a "Q".

.. _`PEP 3156`: http://python.org/dev/peps/pep-3156/
.. _`pytest`: http://pytest.org
.. _`BSD 2 Clause License`: http://opensource.org/licenses/BSD-2-Clause
.. _tox: https://tox.readthedocs.org/
.. _pytest-xdist: https://pypi.python.org/pypi/pytest-xdist
.. _#31: https://github.com/harvimt/quamash/issues/31
.. _#34: https://github.com/harvimt/quamash/issues/34
.. _#35: https://github.com/harvimt/quamash/issues/35
.. _#55: https://github.com/harvimt/quamash/issues/55
.. _#59: https://github.com/harvimt/quamash/pull/59
.. _#62: https://github.com/harvimt/quamash/pull/62
