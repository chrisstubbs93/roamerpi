import socket
import urllib.request
import serial
import os
import time

ser = serial.Serial("/dev/ttyAMA0", 9600)

socket.setdefaulttimeout(10)

while 1:
	linein = str(ser.readline())
	print("serial rx: " + linein)
	if linein.startswith("b'$GPGGA"):
		print(linein)
		gpsdata = linein.split(",")
		tim = gpsdata[1][:6]
		lats = gpsdata[2]
		lngs = gpsdata[4]
		fix = gpsdata[5]
		sats = gpsdata[6]
		print("Fix quality" + fix)
		print ("time:" + tim)
		#process the NMEA coords to decimal
		latdecs = ""
		latdecs2 = ""
		for i in range(0, lats.index('.') - 2):
			latdecs = latdecs + lats[i]
		for i in range(lats.index('.') - 2, len(lats) - 1):
			latdecs2 = latdecs2 + lats[i]
		lat = float(latdecs) + float(str((float(latdecs2)/60))[:8])
		lngdecs = ""
		lngdecs2 = ""
		for i in range(0, lngs.index('.') - 2):
			lngdecs = lngdecs + lngs[i]
		for i in range(lngs.index('.') - 2, len(lngs) - 1):
			lngdecs2 = lngdecs2 + lngs[i]
		lng = float(lngdecs) + float(str((float(lngdecs2)/60))[:8])
		if gpsdata[3] == "W":
			lat = 0 - lat
		if gpsdata[5] == "S":
			lng = 0 - lng
		#NMEA coords have been converted to dec coords lat/lng
		print("lat:" + str(lat))
		print ("lng:" + str(lng))
		try:
			print ("posting the shit")
			contents = urllib.request.urlopen("http://roamer.tk/gps/uploadgps.php?lat="+str(lat)+"&lng="+str(lng)+"&sats="+str(sats)+"&speed="+str(4)+"&heading="+str(5)+"&gpstime="+tim).read()
			print("shit posted")
		except socket.error as socketerror:
		        print("Error: ", socketerror)
	time.sleep(10)
	ser.flushInput()


ser.close()

