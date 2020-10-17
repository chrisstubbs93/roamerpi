from micropyGPS import MicropyGPS
import serial
import os
import time

my_gps = MicropyGPS()

ser = serial.Serial("/dev/ttyAMA0", 9600)

while 1:
	linein = str(ser.readline())
	for x in linein:
		my_gps.update(x)
	print(my_gps.latitude)

ser.close()

