#!/bin/sh
while true
do
	cd /home/pi/roamerpi/control
	python3 server-socketio.py
	sleep 10
done
