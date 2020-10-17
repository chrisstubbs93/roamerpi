import serial
import os
import time

ser = serial.Serial("/dev/ttyAMA0", 9600)

while 1:
	linein = str(ser.readline())
	print(linein)

ser.close()

