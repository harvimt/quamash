FROM ubuntu:12.04
RUN apt-get update
RUN apt-get install -y python-software-properties curl build-essential libgl1-mesa-dev xvfb
RUN add-apt-repository -y ppa:beineri/opt-qt542
RUN add-apt-repository -y ppa:fkrull/deadsnakes
RUN apt-get update
RUN apt-get install -y libqt4-dev qt54base python3.3-dev python3.4-dev python3.5-dev curl
RUN mkdir /downloads
RUN mkdir /builds
RUN curl -L -o /downloads/sip.tar.gz http://sourceforge.net/projects/pyqt/files/sip/sip-4.16.5/sip-4.16.5.tar.gz
RUN curl -L -o /downloads/pyqt4.tar.gz http://sourceforge.net/projects/pyqt/files/PyQt4/PyQt-4.11.3/PyQt-x11-gpl-4.11.3.tar.gz
RUN curl -L -o /downloads/pyqt5.tar.gz http://sourceforge.net/projects/pyqt/files/PyQt5/PyQt-5.4/PyQt-gpl-5.4.tar.gz
RUN curl -L -o /downloads/get-pip.py https://bootstrap.pypa.io/get-pip.py
RUN echo '6d01ea966a53e4c7ae5c5e48c40e49e5  /downloads/sip.tar.gz' | md5sum -c -
RUN echo '997c3e443165a89a559e0d96b061bf70  /downloads/pyqt4.tar.gz' | md5sum -c -
RUN echo '7f2eb79eaf3d7e5e7df5a4e9c8c9340e  /downloads/pyqt5.tar.gz' | md5sum -c -
RUN echo 'abc87074bdfe760f7f136713f0e40199  /downloads/get-pip.py' | md5sum -c -
WORKDIR /builds
RUN tar xzf /downloads/sip.tar.gz --keep-newer-files
RUN tar xzf /downloads/pyqt4.tar.gz --keep-newer-files
RUN tar xzf /downloads/pyqt5.tar.gz --keep-newer-files
WORKDIR /builds/sip-4.16.5
RUN python3.3 configure.py && make && make install
RUN python3.4 configure.py && make && make install
RUN python3.5 configure.py && make && make install
WORKDIR /builds/PyQt-x11-gpl-4.11.3
RUN python3.3 configure.py --confirm-license --no-designer-plugin -e QtCore -e QtGui --destdir=/usr/lib/python3.3/dist-packages && make && make install
RUN python3.4 configure.py --confirm-license --no-designer-plugin -e QtCore -e QtGui --destdir=/usr/lib/python3.4/dist-packages && make && make install
RUN python3.5 configure.py --confirm-license --no-designer-plugin -e QtCore -e QtGui --destdir=/usr/lib/python3.5/dist-packages && make && make install
WORKDIR /builds/PyQt-gpl-5.4
RUN python3.3 configure.py --confirm-license --qmake /opt/qt54/bin/qmake --no-designer-plugin -e QtCore -e QtGui -e QtWidgets --destdir=/usr/lib/python3.3/dist-packages && make && make install
RUN python3.4 configure.py --confirm-license --qmake /opt/qt54/bin/qmake --no-designer-plugin -e QtCore -e QtGui -e QtWidgets --destdir=/usr/lib/python3.4/dist-packages && make && make install
RUN python3.5 configure.py --confirm-license --qmake /opt/qt54/bin/qmake --no-designer-plugin -e QtCore -e QtGui -e QtWidgets --destdir=/usr/lib/python3.5/dist-packages && make && make install
RUN python3.3 /downloads/get-pip.py
RUN python3.4 /downloads/get-pip.py
RUN python3.5 /downloads/get-pip.py
RUN mkdir /quamash
WORKDIR /quamash
#RUN python3.4 -m pip install pytest flake8 pep8-naming flake8-debugger flake8-docstrings
#CMD sh runtest.sh
