#!/bin/sh
kill $(ps aux | grep '[s]tartmjpg.sh' | awk '{print $2}')
kill $(ps aux | grep '[y]tchecker.sh' | awk '{print $2}')
kill $(ps aux | grep '[s]tartmotors.sh' | awk '{print $2}')
kill $(ps aux | grep '[s]tartgps.sh' | awk '{print $2}')
kill $(ps aux | grep '[f]fmpeg.sh' | awk '{print $2}')
kill $(ps aux | grep '[f]fmpeg' | awk '{print $2}')
kill $(ps aux | grep '[m]jpg_streamer' | awk '{print $2}')
kill $(ps aux | grep '[p]ython3 server3.py' | awk '{print $2}')