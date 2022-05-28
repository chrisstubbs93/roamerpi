#!/bin/sh
kill $(ps aux | grep '[s]tartmjpg.sh' | awk '{print $2}')
kill $(ps aux | grep '[y]tchecker.sh' | awk '{print $2}')
kill $(ps aux | grep '[s]tartmotors.sh' | awk '{print $2}')
kill $(ps aux | grep '[s]tartgps.sh' | awk '{print $2}')
kill $(ps aux | grep '[p]ython.* .*server-socketio.py' | awk '{print $2}')