#!/bin/sh
sudo modprobe bcm2835-v4l2
cd jsmpeg/mjpg-streamer
sudo ./mjpg_streamer -i "./input_uvc.so -f 10 -r 640x360 -n -y" -o "./output_http.so -w ./www -p 80"