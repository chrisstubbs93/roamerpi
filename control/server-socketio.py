import socket, hashlib, base64, threading
import time
from collections import namedtuple
from functools import wraps
from threading import Timer
from threading import Thread
from functools import partial

import serial
import zlib
import struct # for values to bytes

#import socket as telemsocket
import urllib.request

from aiohttp import web
import socketio
import ssl
import asyncio

import numpy

import logging

#import requests
#telemsocket.setdefaulttimeout(10)

# global lasttime
# global iSpeedL
# global iSpeedR
# global iHallSkippedL
# global iHallSkippedR
# global iTemp
# global iVolt
# global iAmpL
# global iAmpR

# iSpeedL = 0.0
# iSpeedR = 0.0
# iHallSkippedL = 0.0
# iHallSkippedR = 0.0
# iTemp = 0.0
# iVolt = 0.0
# iAmpL = 0.0
# iAmpR = 0.0

#limits
maxfwdspeed = 150.0 #max fwd speed
maxrevspeed = 100.0 #max reverse speed
steerauth = 0.4 #adjust how much 100% steering actually steers
speedsteercomp = 2.2 #more steering authority at speed. 2.0 = double steering authority at 100% speed

global portbusy
portbusy = False

lasttime = 0
fourwd = False

ser = serial.Serial('/dev/serial0', 115200, timeout=1)  # open main serial port
try:
	ser2 = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)  # open secondary serial port 
	fourwd = True
	print("4WD detected")
except:
	fourwd = False
	print("2WD only detected")


def sendcmd(steer,speed):
	'''
	Sends a bytearray for controlling the hoverboard

	:param steer: -1000...1000
	:param speed: -1000...1000
	:returns: command bytes
	'''
	
	if speed > 0:
		speed = int((numpy.clip(100,-100,speed)/100.0)*maxfwdspeed)
	else:
		speed = int((numpy.clip(100,-100,speed)/100.0)*maxrevspeed)
	steer = int((numpy.clip(100,-100,steer)*steerauth*(1+((speedsteercomp-1)*abs(speed)/100))))


	portbusy = True
	startB = bytes.fromhex('ABCD')[::-1] # lower byte first
	#steerB = (steer).to_bytes(2, byteorder='little', signed=True) #16 bits
	#speedB = (speed).to_bytes(2, byteorder='little', signed=True) #16 bits
	steerB = struct.pack('h', steer)
	speedB = struct.pack('h', speed)
	#crcB = zlib.crc32(steerB+speedB).to_bytes(4, byteorder='little') #32 bit CRC of byte-joined command
	crcB = bytes(a^b^c for (a, b, c) in zip(startB, steerB, speedB))

	ser.write(startB+steerB+speedB+crcB)

	if fourwd:
		ser2.write(startB+steerB+speedB+crcB)

	portbusy = False




#define motor controls
def stp():
	sendcmd(0,0)
	print("stop")
def fwd():
		sendcmd(0,50)
		global lasttime
		lasttime = int(time.time())
def bck():
		sendcmd(0,-50)
		global lasttime
		lasttime = int(time.time())
def right(): #on the spot turn right
		sendcmd(50,0)
		global lasttime
		lasttime = int(time.time())
def left(): #on the spot turn left
		sendcmd(-50,0)
		global lasttime
		lasttime = int(time.time())
def fr(): #forward right turn
		sendcmd(50,20)
		global lasttime
		lasttime = int(time.time())
def fl(): #forward left turn
		sendcmd(-50,20)
		global lasttime
		lasttime = int(time.time())
def br(): #reverse right turn
		sendcmd(-50,-20)
		global lasttime
		lasttime = int(time.time())
def bl(): #reverse left turn
		sendcmd(50,-20)
		global lasttime
		lasttime = int(time.time())


def sendana(x,y): #handle joystick command
		sendcmd(x,y)
		global lasttime
		lasttime = int(time.time())

### SOCKETIO STUFF ###

## creates a new Async Socket IO Server
sio = socketio.AsyncServer(cors_allowed_origins='*')
## Creates a new Aiohttp Web Application
#app = web.Application()
# Binds our Socket.IO server to our Web App
## instance
#sio.attach(app)

ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
ssl_context.load_cert_chain('/etc/letsencrypt/live/bigclamps.loseyourip.com/fullchain.pem', '/etc/letsencrypt/live/bigclamps.loseyourip.com/privkey.pem')

async def init():
	app = web.Application()
	sio.attach(app)
	return app

def main():
	logging.basicConfig(level=logging.DEBUG)
	loop = asyncio.get_event_loop()
	app = loop.run_until_complete(init())

	loop.create_task(temeletry())
	print("running app")
	web.run_app(app, port=9876, ssl_context=ssl_context, loop=loop) 

async def temeletry():
	while True:
		if portbusy == False:
			feedback = ser.read_all()
			#print(feedback)
			if feedback:
				cmd1, cmd2, speedR_meas, speedL_meas, batVoltage, boardTemp, cmdLed = struct.unpack('<hhhhhhH', feedback[2:16])
				print(f'cmd1: {cmd1}, cmd2: {cmd2}, speedR_meas: {speedR_meas}, speedL_meas: {speedL_meas}, batVoltage: {batVoltage}, boardTemp: {boardTemp}, cmdLed: {cmdLed}')	
				await sio.emit('telemetry', {"cmd1": cmd1, "cmd2": cmd2, "speedR_meas": speedR_meas, "speedL_meas": speedL_meas, "batVoltage": batVoltage, "boardTemp": boardTemp, "cmdLed": cmdLed})
				print("Telemetry Emitted")
				await asyncio.sleep(1)

@sio.on('control')
async def handle_control(sid, control):
	print("CTRL msg from: " , sid)
	if control == "s":
		print("motors stop")
		stp() #motors STOP
	if control == "f":
		print("motors forward")
		fwd() #motors go forward for 0.5s
	if control == "b":
		print("motors rev")
		bck() #motors go rev for 0.5s
	if control == "l":
		print("motors left")
		left() #motors go left for 0.5s
	if control == "r":
		print("motors right")
		right() #motors go right for 0.5s
	if control == "fl":
		print("motors forward-left")
		fl() #motors go forward-left for 0.5s
	if control == "fr":
		print("motors forward-right")
		fr() #motors go forward-right for 0.5s
	if control == "bl":
		print("motors rev-left")
		bl() #motors go rev-left for 0.5s
	if control == "br":
		print("motors rev-right")
		br() #motors go rev-right for 0.5s

@sio.on('analog')
async def handle_analog(sid, control):
	print("ANALOG msg from: " , sid)
	sendana(int(control.split(',')[0]),int(control.split(',')[1]))


@sio.event
async def connect(sid, environ):
	print('Client Connected: ', sid)

@sio.event
async def disconnect(sid):
	print('Client Disconnected: ', sid)
	print("motors stop")
	stp()

@sio.event
async def message(sid, data):
	print('message from ', sid)
	print(data)

### END SOCKETIO ###



# def rxcmd():
# 	if portbusy == False:
# 		feedback = ser.read_all()
# 		#print(feedback)
# 		if feedback:
# 			cmd1, cmd2, speedR_meas, speedL_meas, batVoltage, boardTemp, cmdLed = struct.unpack('<hhhhhhH', feedback[2:16])
# 			print(f'cmd1: {cmd1}, cmd2: {cmd2}, speedR_meas: {speedR_meas}, speedL_meas: {speedL_meas}, batVoltage: {batVoltage}, boardTemp: {boardTemp}, cmdLed: {cmdLed}')
# 			#asyncio.run(do_stuff_every_x_seconds(1)) #this kinda worked but made everything horribly slow


# async def do_stuff_every_x_seconds(timeout):  #this kinda worked but made everything horribly slow
# 	while True:
# 		#await asyncio.sleep(timeout)
# 		await sio.emit('telemetry', 'testing telem')
# 		#print("sent the shit")


#@periodic(interval=1)
def task1():
	try:
		global lasttime
		print("Lasttime:" + str(lasttime) + " Now:" + str(int(time.time())))
		##rxcmd()
		if (int(time.time())>=int(lasttime+2)):
			print("timeout")
			stp()
	except BaseException as error:
		print('Closing task1 An exception occurred: {}'.format(error))

#def taskstart():
#    for t in tasks:
#        if t.start:
#            loop.call_soon(t.task)
#        else:
#            loop.call_later(t.interval, t.task)
#    try:
#        loop.run_forever()
#    finally:
#        loop.close()


#t1=threading.Thread(target=taskstart)
#t1.start()


class Interval(object):

	def __init__(self, interval, function, args=[], kwargs={}):
		"""
		Runs the function at a specified interval with given arguments.
		"""
		self.interval = interval
		self.function = partial(function, *args, **kwargs)
		self.running  = False 
		self._timer   = None 

	def __call__(self):
		"""
		Handler function for calling the partial and continuting. 
		"""
		self.running = False  # mark not running
		self.start()          # reset the timer for the next go 
		self.function()       # call the partial function 

	def start(self):
		"""
		Starts the interval and lets it run. 
		"""
		if self.running:
			# Don't start if we're running! 
			return 
			
		# Create the timer object, start and set state. 
		self._timer = Timer(self.interval, self)
		self._timer.start() 
		self.running = True

	def stop(self):
		"""
		Cancel the interval (no more function calls).
		"""
		if self._timer:
			self._timer.cancel() 
		self.running = False 
		self._timer  = None

# try:
# 	interval = Interval(0.5, task1,)
# 	# print "Starting Interval, press CTRL+C to stop."
# 	interval.start() 
# except:
# 	print("closing interval (e)")
# 	interval.stop()
# finally:
# 	print("closing interval (f)")
# 	#wrapup()

def uploadTelemetry():
	try:
		print ("posting the shit")
		#contents = urllib.request.urlopen("http://roamer.tk/gps/uploadgps.php?lat="+str(lat)+"&lng="+str(lng)+"&sats="+str(sats)+"&speed="+str(speed)+"&heading="+str(my_gps.course)+"&fixtype="+fixtype+"&gpstime="+timestr).read()
		#print("http://roamer.tk/gps/uploadgps.php?lat="+str(lat)+"&lng="+str(lng)+"&sats="+str(sats)+"&speed="+str(speed)+"&heading="+str(my_gps.course)+"&fixtype="+fixtype+"&gpstime="+timestr, headers={'User-Agent': 'Mozilla/5.0'})
		geturl = "http://roamer.chris-stubbs.co.uk/telemetry/uploadtelemetry.php?iSpeedL="+str(iSpeedL)+"&iSpeedR="+str(iSpeedR)+"&iTemp="+str(iTemp)+"&iVolt="+str(iVolt)+"&iAmpL="+str(iAmpL)+"&iAmpR="+str(iAmpR)
		print("Volt: ",iVolt)
		print(geturl)
		r = urllib.request.Request(geturl)
		print(r)
		print("shit posted")
		print("")
		with urllib.request.urlopen(r) as response:
 			the_page = response.read()
	except urllib.error.URLError as e:
		print(e.reason)  


class control(Thread):
	def __init__(self):
		Thread.__init__(self)
		self.daemon = True
		self.start()
	def run(self):
		#print 'A'
		try:
			interval = Interval(0.5, task1,)
			# print "Starting Interval, press CTRL+C to stop."
			interval.start() 
		except:
			print("closing interval (e)")
			interval.stop()
		finally:
			print("closing interval (f)")
			#wrapup()

# class motorTelemetry(Thread):
# 	def __init__(self):
# 		Thread.__init__(self)
# 		self.daemon = True
# 		self.start()
# 	def run(self):
# 		while True:
# 			#time.sleep(1)
# 			rxcmd()


control()
#motorTelemetry()



if __name__ == '__main__':
	#web.run_app(app, port=9876, ssl_context=ssl_context)
	main()

while True:
	pass
