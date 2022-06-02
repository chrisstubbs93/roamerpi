#!/bin/sh
while true
do
	cd /home/pi/roamerpi/control
	sudo python server-socketio.py
	sleep 10
done
