export DISPLAY=:99.0
Xvfb $DISPLAY -screen 0 1024x768x16 2>&1 >/dev/null &
python3.4 -m py.test
