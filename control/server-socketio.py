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



global portbusy
portbusy = False

lasttime = 0

ser = serial.Serial('/dev/serial0', 115200, timeout=1)  # open front/main serial port
ser2 = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)  # open rear serial port 

def sendcmd(steer,speed):
	'''
	Sends a bytearray for controlling the hoverboard

	:param steer: -1000...1000
	:param speed: -1000...1000
	:returns: command bytes
	'''
	portbusy = True
	startB = bytes.fromhex('ABCD')[::-1] # lower byte first
	#steerB = (steer).to_bytes(2, byteorder='little', signed=True) #16 bits
	#speedB = (speed).to_bytes(2, byteorder='little', signed=True) #16 bits
	steerB = struct.pack('h', steer)
	speedB = struct.pack('h', speed)
	#crcB = zlib.crc32(steerB+speedB).to_bytes(4, byteorder='little') #32 bit CRC of byte-joined command
	crcB = bytes(a^b^c for (a, b, c) in zip(startB, steerB, speedB))

	ser.write(startB)
	ser.write(steerB)
	ser.write(speedB)
	ser.write(crcB)

	ser2.write(startB)
	ser2.write(steerB)
	ser2.write(speedB)
	ser2.write(crcB)

	portbusy = False

def rxcmd():
	if portbusy == False:
		# global lasttime
		# global iSpeedL
		# global iSpeedR
		# global iHallSkippedL
		# global iHallSkippedR
		# global iTemp
		# global iVolt
		# global iAmpL
		# global iAmpR
		'''
		SerialFeedbackLen = 20
		buf = bytearray()
		if ser.inWaiting() >= SerialFeedbackLen:
			for x in range(0, SerialFeedbackLen, 1):
				buf += bytearray(ser.read())
			crcR = zlib.crc32(buf[0:SerialFeedbackLen-4]).to_bytes(4, byteorder='little')
			if crcR == buf[SerialFeedbackLen-4:SerialFeedbackLen]:
				print("Checksum OK")
				iSpeedL = ((int.from_bytes(buf[0:2], byteorder='little', signed=True))/100)
				iSpeedR = ((int.from_bytes(buf[2:4], byteorder='little', signed=True))/100)
				iHallSkippedL = (int.from_bytes(buf[4:6], byteorder='little', signed=False))
				iHallSkippedR = (int.from_bytes(buf[6:8], byteorder='little', signed=False))
				iTemp = (int.from_bytes(buf[8:10], byteorder='little', signed=False))
				iVolt = ((int.from_bytes(buf[10:12], byteorder='little', signed=False))/100)
				iAmpL = ((int.from_bytes(buf[12:14], byteorder='little', signed=True))/100)
				iAmpR = ((int.from_bytes(buf[14:16], byteorder='little', signed=True))/100)
				print("iSpeedL (km/h): ", iSpeedL)
				print("iSpeedR (km/h): ", iSpeedR)
				print("iHallSkippedL: ", iHallSkippedL)
				print("iHallSkippedR: ", iHallSkippedR)
				print("iTemp: (degC)", iTemp)
				print("iVolt: (V)", iVolt)
				print("iAmpL: (A)", iAmpL)
				print("iAmpR: (A)", iAmpR)
				print("Buffer: ", buf)
				print("=========================================")
				#uploadTelemetry()
			else:
				print("!!-CHECKSUM FAIL-!!")
		'''
		feedback = ser.read_all()
		#print(feedback)
		if feedback:
			cmd1, cmd2, speedR_meas, speedL_meas, batVoltage, boardTemp, cmdLed = struct.unpack('<hhhhhhH', feedback[2:16])
			print(f'cmd1: {cmd1}, cmd2: {cmd2}, speedR_meas: {speedR_meas}, speedL_meas: {speedL_meas}, batVoltage: {batVoltage}, boardTemp: {boardTemp}, cmdLed: {cmdLed}')


#define motor controls
def stp():
    sendcmd(0,0)
    print("stop")
def fwd():
        sendcmd(0,100)
        global lasttime
        lasttime = int(time.time())
def bck():
        sendcmd(0,-250)
        global lasttime
        lasttime = int(time.time())
def right(): #on the spot turn right
        sendcmd(350,0)
        global lasttime
        lasttime = int(time.time())
def left(): #on the spot turn left
        sendcmd(-350,0)
        global lasttime
        lasttime = int(time.time())
def fr(): #forward right turn
        sendcmd(350,200)
        global lasttime
        lasttime = int(time.time())
def fl(): #forward left turn
        sendcmd(-350,200)
        global lasttime
        lasttime = int(time.time())
def br(): #reverse right turn
        sendcmd(-350,-200)
        global lasttime
        lasttime = int(time.time())
def bl(): #reverse left turn
        sendcmd(350,-200)
        global lasttime
        lasttime = int(time.time())

### SOCKETIO STUFF ###

## creates a new Async Socket IO Server
sio = socketio.AsyncServer(cors_allowed_origins='*')
## Creates a new Aiohttp Web Application
app = web.Application()
# Binds our Socket.IO server to our Web App
## instance
sio.attach(app)

ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
ssl_context.load_cert_chain('/etc/letsencrypt/live/bigclamps.loseyourip.com/fullchain.pem', '/etc/letsencrypt/live/bigclamps.loseyourip.com/privkey.pem')

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

#@periodic(interval=1)
def task1():
	try:
		global lasttime
		print("Lasttime:" + str(lasttime) + " Now:" + str(int(time.time())))
		rxcmd()
		if (int(time.time())>=int(lasttime+2)):
			print("timeout")
			stp()
	except:
		print("closing task1 (e)")

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

class motorTelemetry(Thread):
	def __init__(self):
		Thread.__init__(self)
		self.daemon = True
		self.start()
	def run(self):
		while True:
			#time.sleep(1)
			rxcmd()


control()
motorTelemetry()

if __name__ == '__main__':
    web.run_app(app, port=9876, ssl_context=ssl_context)

while True:
	pass
