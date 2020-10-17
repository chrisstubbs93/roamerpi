import socket
import urllib.request
from micropyGPS import MicropyGPS
import serial
import os
import time
import requests

socket.setdefaulttimeout(10)
my_gps = MicropyGPS()
ser = serial.Serial("/dev/ttyAMA0", 9600)
lasttime = 0

while 1:
	linein = str(ser.readline())
	#print("line")
	for x in linein:
		my_gps.update(x)
	if (lasttime + 30) < time.time():
		lasttime = time.time()
		#process the NMEA coords to decimal
		lat = round(my_gps.latitude[0] + (my_gps.latitude[1]/60),8)
		lng = round(my_gps.longitude[0] + (my_gps.longitude[1]/60),8)
		if my_gps.longitude[2] == "W":
			lng = 0 - lng
		if my_gps.latitude[2] == "S":
			lat = 0 - lat
		timestr = str(my_gps.timestamp[0]).zfill(2) + str(my_gps.timestamp[1]).zfill(2) + str(int(my_gps.timestamp[2])).zfill(2)
		sats = my_gps.satellites_in_use
		speed = my_gps.speed[2]*1000/60
		if my_gps.fix_type == 1:
			fixtype = "NO"
		if my_gps.fix_type == 2:
			fixtype = "2D"
		if my_gps.fix_type == 3:
			fixtype = "3D"
		print("I can see " + str(my_gps.satellites_in_use) + " satellites. My fix is: " + fixtype + "  My coordinates are: " + str(lat) + "," + str(lng) + " The time is: " + timestr)
		try:
			print ("posting the shit")
			#contents = urllib.request.urlopen("http://roamer.tk/gps/uploadgps.php?lat="+str(lat)+"&lng="+str(lng)+"&sats="+str(sats)+"&speed="+str(speed)+"&heading="+str(my_gps.course)+"&fixtype="+fixtype+"&gpstime="+timestr).read()
			#print("http://roamer.tk/gps/uploadgps.php?lat="+str(lat)+"&lng="+str(lng)+"&sats="+str(sats)+"&speed="+str(speed)+"&heading="+str(my_gps.course)+"&fixtype="+fixtype+"&gpstime="+timestr, headers={'User-Agent': 'Mozilla/5.0'})
			geturl = "http://tn22.com/emf/emfroamer/gps/uploadgps.php?lat="+str(lat)+"&lng="+str(lng)+"&sats="+str(sats)+"&speed="+str(speed)+"&heading="+str(my_gps.course)+"&fixtype="+fixtype+"&gpstime="+timestr
			r = requests.get(geturl)
			print(r)
			print("shit posted")
			print("")
		except socket.error as socketerror:
			print("Error: ", socketerror)

ser.close()

