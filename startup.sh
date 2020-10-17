#!/bin/sh
cd /home/pi/roamerpi
sleep 10
./pull.sh
sleep 5
./startmjpg.sh&
./ytchecker.sh&
./startmotors.sh&
./startgps.sh&
