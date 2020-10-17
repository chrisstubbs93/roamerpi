#!/bin/sh
sleep 5
ffmpeg -re -f mjpeg -r 10 -i "http://localhost/?action=stream" -ar 44100 -ac 2 -acodec pcm_s16le -f s16le -ac 2 -i /dev/zero -acodec aac -ab 1k -strict experimental -s 640x360 -vcodec h264 -pix_fmt yuv420p -g 20 -vb 500k -preset ultrafast -crf 31 -r 10 -f flv "rtmp://a.rtmp.youtube.com/live2/38ex-59gh-v159-q46z-feam" 2> /home/pi/roamerpi/ffmpeg.log