FROM ubuntu:14.04
RUN apt-get update -y && apt-get install -y curl build-essential software-properties-common python-software-properties

RUN \
  sudo mkdir -p /downloads && \
  sudo chmod a+rw /downloads && \
  if [ ! -f /downloads/sip.tar.gz ];   then curl -L -o /downloads/sip.tar.gz https://sourceforge.net/projects/pyqt/files/sip/sip-4.19.3/sip-4.19.3.tar.gz; fi && \
  if [ ! -f /downloads/pyqt4.tar.gz ]; then curl -L -o /downloads/pyqt4.tar.gz https://sourceforge.net/projects/pyqt/files/PyQt4/PyQt-4.12.1/PyQt4_gpl_x11-4.12.1.tar.gz; fi && \
  if [ ! -f /downloads/pyqt5.tar.gz ]; then curl -L -o /downloads/pyqt5.tar.gz https://sourceforge.net/projects/pyqt/files/PyQt5/PyQt-5.9/PyQt5_gpl-5.9.tar.gz; fi && \
  echo '4708187f74a4188cb4e294060707106f  /downloads/sip.tar.gz' | md5sum -c - && \
  echo '0112e15858cd7d318a09e7366922f874  /downloads/pyqt4.tar.gz' | md5sum -c - && \
  echo 'a409ac0d65ead9178b90c2822759a84b  /downloads/pyqt5.tar.gz' | md5sum -c - && \
  sudo mkdir -p /builds && \
  sudo chmod a+rw /builds && \
  cd /builds && \
  tar xzf /downloads/sip.tar.gz --keep-newer-files && \
  tar xzf /downloads/pyqt4.tar.gz --keep-newer-files && \
  tar xzf /downloads/pyqt5.tar.gz --keep-newer-files && \
  sudo apt-get install -y libqt4-dev && \
  sudo add-apt-repository -y ppa:beineri/opt-qt591-trusty && \
  sudo add-apt-repository -y ppa:deadsnakes/ppa && \
  sudo apt-get update && \
  sudo apt-get install -y qt59base python3.4-dev python3.5-dev python3.6-dev
SHELL ["/bin/bash", "-c"]
RUN \
  for python in python3.4 python3.5 python3.6; do \
    cd /builds/sip-4.19.3 && \
    $python configure.py && \
    make clean && make && make install && \
    cd /builds/PyQt4_gpl_x11-4.12.1 && \
    $python configure.py -c --confirm-license --no-designer-plugin -e QtCore -e QtGui && \
    make clean && make && make install && \
    cd /builds/PyQt5_gpl-5.9 && \
    ( \
    . /opt/qt59/bin/qt59-env.sh && \
    $python configure.py -c --confirm-license --no-designer-plugin -e QtCore -e QtGui -e QtWidgets && \
    make clean && make && make install; \
    ) \
  done
ADD . /quamash
WORKDIR /quamash
