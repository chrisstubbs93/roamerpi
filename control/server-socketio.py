from contextlib import nullcontext
import serial, struct, time, numpy # for hoverboard comms
import urllib.request
import urllib.parse
from aiohttp import web
from aiohttp import ClientSession
import aiohttp
import socketio, ssl, asyncio, logging
import re
import socket
from micropyGPS import MicropyGPS
#import requests
import json
from shapely.geometry import shape, Point
import serial.tools.list_ports
import time
import board
import neopixel
import sys
import datetime

socket.setdefaulttimeout(10)
lastgpstime = 0
lastGpsSocketTime = 0
lastGpsGeofenceSocketTime = 0
my_gps = MicropyGPS()

#limits & configuration
maxfwdspeed = 25.0 #max fwd speed
maxrevspeed = 10.0 #max reverse speed
steerauth = 1 #adjust how much 100% steering actually steers (don't do nuffink)
speedsteercomp = 1 #more steering authority at speed. 2.0 = double steering authority at 100% speed (don't do nuffink)
global StopRetryCount 
StopRetryCount = 1 #how many times to send the stop signal in case the serial is awful

batteryWarningThreshold = 37*100 # voltage that we'll send a warning at (in 100/ths of a volt)
telemetryWarningTimeout = 10 # in seconds, how long until we send an email panicking about not having any telemetry

# 24-hour clock, this is used to dim the lights during the day
daytimeHourStart = 5
daytimeHourEnd = 20

PortHoverboard1 = '/dev/serial0'
enableAdminEmail = False
if enableAdminEmail == False:
	print("Warning - admin email disabled")

fullchainlocation = '/etc/letsencrypt/live/bigclamps.loseyourip.com/fullchain.pem'
privkeylocation = '/etc/letsencrypt/live/bigclamps.loseyourip.com/privkey.pem'

global portbusy
portbusy = False

global lastSerialSendMs
lastSerialSendMs = 0

lasttime = 0
fourwd = False

global hover1LastTime
global hover2LastTime
hover1LastTime = 0
hover2LastTime = 0

global hover1BatteryWarned
global hover2BatteryWarned
hover1BatteryWarned = False
hover2BatteryWarned = False

global hover1TelemetryWarned
global hover2TelemetryWarned
hover1TelemetryWarned = False
hover2TelemetryWarned = False

global steerLockoutWarned
steerLockoutWarned = False

global clientConnected
clientConnected = False

#global motor halt vars for GPS/SONAR/BUMP
global steerHaltMotors
steerHaltMotors = False

global geoHaltMotors
geoHaltMotors = False

global haltMotorOverride
haltMotorOverride = False

global frontBumped
frontBumped = False

global rearBumped
rearBumped = False

global frontProxBreach
frontProxBreach = False

global rearProxBreach
rearProxBreach = False

#config for SONAR, GPS and Bump stops
haltMotorsOnBump = True
haltMotorsOnProxBreach = True
haltMotorsOnGeofenceBreach = True
haltMotorsOnSteerLockout = True

#distance thresholds for SONAR to halt motors
frontThreshold = 50
rearThreshold = 30
sideThreshold = 50


# Lighting
# Choose an open pin connected to the Data In of the NeoPixel strip, i.e. board.D18
# NeoPixels must be connected to D10, D12, D18 or D21 to work.
pixel_pin = board.D18

# The number of NeoPixels
num_pixels = 270

# The order of the pixel colors - RGB or GRB. Some NeoPixels have red and green reversed!
# For RGBW NeoPixels, simply change the ORDER to RGBW or GRBW.
ORDER = neopixel.GRB

# colours
ORANGE = (255,140,0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
DIMRED = (30, 0, 0)
OFF = (0, 0, 0)

pixels = neopixel.NeoPixel(
	pixel_pin, num_pixels, brightness=0.2, auto_write=False, pixel_order=ORDER
)

global braking
braking = True

global hazards
hazards = False

global leftIndicate
leftIndicate = False

global rightIndicate
rightIndicate = False

global headlights
headlights = True

global idleAnimation
idleAnimation = False

global steeringLocal
steeringLocal = False

# Pixel Positions
# Indicators
Left_Front_Indicate_Start = 36
Left_Front_Indicate_End = 44

Right_Front_Indicate_Start = 0
Right_Front_Indicate_End = 7

Right_Rear_Indicate_Start = Left_Front_Indicate_End + 1
Right_Read_Indicate_End = 64

Left_Rear_Indicate_Start = Right_Read_Indicate_End + 1
Left_Rear_Indicate_End = 83

# Underglow
Underglow_Start = Left_Rear_Indicate_End + 1
Underglow_End = num_pixels

# headlight
Front_Headlight_Start = 8
Front_Headlight_End = 35

#load the JSON geofencing data
with open('geo.json') as f:
	js = json.load(f)

async def adminEmail(sub, msg):
	if enableAdminEmail:
		try:
			encodedMsg = urllib.parse.quote(msg, safe='')
			encodedSub = urllib.parse.quote(sub, safe='')

			geturl = "https://roamer.fun/admin/mail.php?sec=PIPEallNIGHT&sub="+str(encodedSub)+"&msg="+str(encodedMsg)
			async with ClientSession() as session:
				async with session.get(geturl) as response:
					response = await response.read()			
					print("Email Sent")
		except Exception as socketerror:
			print("Email Send Error: ", socketerror)

#default the port states to false:
fourwd = False
NavsparkDetected = False
Steeringdetected = False
#connect to hoverboard
ser = serial.Serial(PortHoverboard1, 115200, timeout=5)  # open main back serial port

#set up variables for ports
global ser2
global serNavspark
global serSteering

def serialAutoDetect():
	global fourwd
	global NavsparkDetected
	global Steeringdetected

	global ser2
	global serNavspark
	global serSteering

	# connect to ports (auto-detection)
	try:
		ports = serial.tools.list_ports.comports()
		print("Begin Serial Autodetection")
		serialAttempt = None
		for port, desc, hwid in sorted(ports):
				if "USB" in port:
					print("{}: {} [{}]".format(port, desc, hwid))				
					attempts = 0			
					while attempts < 3:
						try:
							attempts += 1	
							if serialAttempt is not None and attempts > 1 and (NavsparkDetected == False or Steeringdetected == False or fourwd == False):
								serialAttempt.reset_input_buffer()
								serialAttempt.close()
								print("Closed Port for next port: " + str(port))							
							serialAttempt = serial.Serial(port, 115200, timeout=5)
							time.sleep(2)
							print("Attempt " + str(attempts) + " on " + port)
							detection = serialAttempt.read_all()
							if detection[0] == 205 and detection[1] == 171 and fourwd == False:
								fourwd = True
								ser2 = serialAttempt
								print("4WD Mode - 2nd Hoverboard detected on port:" + port)		
								break		
							elif "$GPGGA" in str(detection.decode('utf-8')) and NavsparkDetected == False:
								NavsparkDetected = True
								serNavspark = serialAttempt
								print("NavSpark detected on port:" + port)	
								break
							elif "$STEER" in str(detection.decode('utf-8').replace('\x00',"")) and Steeringdetected == False:
								Steeringdetected = True
								serSteering = serialAttempt
								print("Steering detected on port: " + port)	
								break									
						except Exception as e:
							print('AUTODETECT EXCEPTION RAISED: {}'.format(e))

	except Exception as e:
			print('AUTODETECT EXCEPTION RAISED: {}'.format(e))

def checkHBStartBytes(detx):
	try:
		if detx[0] == 205 and detx[1] == 171:
			return True
		else:
			return False
	except:
		return False

def startRearHB():
	print("About to start rear HB")
	time.sleep(2)
	detection = ser.read_all()
	if checkHBStartBytes(detection):
		#it's already on, do nothing
		print("Rear HB already on")
	else:
		if Steeringdetected:
			#start it
			print("Starting rear HB")
			serSteering.write((str(8888)+"\n").encode('utf_8')) #8888 means power cycle rear
			print("Waiting for startup")
			time.sleep(10)
			detection = ser.read_all()#clear the buffer?
			time.sleep(3)
			detection = ser.read_all()
			print ''.join(format(x, '02x') for x in detection)
			if checkHBStartBytes(detection):
				print("Rear HB started")
			else:
				print("Rear HB did not respond")
		else:
			print("No steering, canne start")
	print("Exiting startRearHB")


def startFrontHB():
	if fourwd:
		print("About to start front HB")
		time.sleep(2)
		detection = ser2.read_all()
		if checkHBStartBytes(detection):
			#it's already on, do nothing
			print("Front HB already on")
		else:
			if Steeringdetected:
				#start it
				print("Starting front HB")
				serSteering.write((str(9999)+"\n").encode('utf_8')) #9999 means power cycle front
				print("Waiting for startup")
				time.sleep(10)
				detection = ser.read_all()#clear the buffer?
				time.sleep(3)
				detection = ser.read_all()
				if checkHBStartBytes(detection):
					print("Front HB started")
				else:
					print("Front HB did not respond")
			else:
				print("No steering, canne start")
	else:
		#no port, start it and hope for the best
		print("We don't know the port, but about to try starting front HB")
		if Steeringdetected:
			print("Starting front HB and hoping for the best")
			serSteering.write((str(9999)+"\n").encode('utf_8')) #9999 means power cycle front
		else:
			print("No steering, canne start")
	print("Exiting startFrontHB")


serialAutoDetect() #find the navspark and steering and maybe 4wd HB
detectionSummary = "NavSpark detected: " + str(NavsparkDetected) + "\nSteering detected: " + str(Steeringdetected) + "\nHoverboard #2 detected: " + str(fourwd) + "\n"
print("PORT DETECTION SUMMARY:")
print(detectionSummary)


if Steeringdetected:
	print("Attempting to start hoverboards")
	startRearHB()
	startFrontHB()
else:
	print("No steering. Can't autostart anything. Good luck!")

serialAutoDetect() #try again now we've maybe powered things on

detectionSummary = "NavSpark detected: " + str(NavsparkDetected) + "\nSteering detected: " + str(Steeringdetected) + "\nHoverboard #2 detected: " + str(fourwd) + "\n"
print("PORT DETECTION SUMMARY:")
print(detectionSummary)

if NavsparkDetected and Steeringdetected and fourwd:
	loop = asyncio.get_event_loop()
	loop.run_until_complete(adminEmail("Roamer control started", detectionSummary))
else:
	loop = asyncio.get_event_loop()
	loop.run_until_complete(adminEmail("Serial autodetection issue",detectionSummary))
	print("One or more serial devices not found.")
	print("====================================================================")
	print("====================================================================")
	time.sleep(5)

##############################################

def sendcmd(steerin,speed):
	'''
	Sends a bytearray for controlling the hoverboard
	:param steer: -1000...1000	:param speed: -1000...1000	:
	'''
	#print("Sendcmd("+str(steerin)+","+str(speed)+")")
	try:
		global steerHaltMotors
		global geoHaltMotors
		global haltMotorOverride
		global frontBumped
		global rearBumped
		global frontProxBreach
		global rearProxBreach
		global leftIndicate
		global rightIndicate
		global StopRetryCount

		if speed > 0:
			speed = int((numpy.clip(100,-100,speed)/100.0)*maxfwdspeed)
		else:
			speed = int((numpy.clip(100,-100,speed)/100.0)*maxrevspeed)
		#steer = int((numpy.clip(100,-100,steerin)*steerauth*(1+((speedsteercomp-1)*abs(speed)/100)))) #disable diff steering
		steer = 0 #don't skid steer using the hoverboards

		if haltMotorsOnGeofenceBreach:
			if geoHaltMotors == True and haltMotorOverride == False: # if the Motors are halted because of Geofencing then set speed to 0 unless it's overridden by the FE
				speed = 0
				print("Motors stopped due to geoHaltMotors")

		if haltMotorsOnSteerLockout:
			if steerHaltMotors == True and haltMotorOverride == False: # if the Motors are halted because of Geofencing then set speed to 0 unless it's overridden by the FE
				speed = 0
				print("Motors stopped due to steerHaltMotors")		

		if haltMotorsOnBump:
			if frontBumped == True and haltMotorOverride == False and speed > 0: # the front bump stop is pushed, set speed to 0 if they're trying to go forward. otherwise let it reverse
				speed = 0
				print("Motors stopped due to frontBumped")
			if rearBumped == True and haltMotorOverride == False and speed < 0: # the rear bump stop is pushed, set speed to 0 if they're trying to go in reverse. otherwise let it go forward
				speed = 0
				print("Motors stopped due to rearBumped")

		if haltMotorsOnProxBreach:
			if frontProxBreach == True and haltMotorOverride == False and speed > 0: # the front bump stop is pushed, set speed to 0 if they're trying to go forward. otherwise let it reverse
				speed = 0
				print("Motors stopped due to frontProxBreach")
			if rearProxBreach == True and haltMotorOverride == False and speed < 0: # the rear bump stop is pushed, set speed to 0 if they're trying to go in reverse. otherwise let it go forward
				speed = 0
				print("Motors stopped due to rearProxBreach")

		#calculate packet
		portbusy = True
		startB = bytes.fromhex('ABCD')[::-1] # lower byte first
		steerB = struct.pack('h', steer)
		speedB = struct.pack('h', speed)
		brakeB = struct.pack('h', 0) #don't bother with braking in speed mode
		driveModeB = struct.pack('h', 2) #2=speed, 3=torque
		crcB = bytes(a^b^c^d^e for (a, b, c, d, e) in zip(startB, steerB, speedB, brakeB, driveModeB))

		#send it
		if speed == 0:
			SerialSendRetries = StopRetryCount
		else:
			SerialSendRetries = 1
		for cnt in range(SerialSendRetries):
			if ser.is_open:
				ser.write(startB+steerB+speedB+brakeB+driveModeB+crcB)
			if fourwd:
				if ser2.is_open:
					ser2.write(startB+steerB+speedB+brakeB+driveModeB+crcB)
			time.sleep(0.07)


		#do the arduino steering
		if Steeringdetected:
			steerin = steerin * -1 #because it's backwards
			if steerin < -20:
				rightIndicate = True
				leftIndicate = False
			elif steerin > 20:
				rightIndicate = False
				leftIndicate = True
			else:
				rightIndicate = False
				leftIndicate = False		
			if steerHaltMotors == True and haltMotorOverride == False:
				steerin = 0 #steer to zero when disabled so it can at least be pushed in a straight line.

			serSteering.write((str(numpy.clip(100,-100,steerin))+"\n").encode('utf_8')) #old mode
			
		portbusy = False

		global lastSerialSendMs
		timez = current_milli_time()-lastSerialSendMs
		#print("ms since last serial: " + str(timez))
		if timez > 700:
			print("WARNING TIME SINCE LAST SERIAL SEND: "+ str(timez))
		lastSerialSendMs = current_milli_time()
	except serial.SerialException as serExc:
		print('SENDCMD (Serial): EXCEPTION RAISED: {}'.format(serExc))
	except Exception as e:
		print('SENDCMD: EXCEPTION RAISED: {}'.format(e))


def SendAndResetTimeout(steer,speed):
	sendcmd(steer,speed)
	global lasttime
	lasttime = current_milli_time()

def stp():
	sendcmd(0,0)

## create a new Async Socket IO Server
sio = socketio.AsyncServer(cors_allowed_origins='*')
ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
ssl_context.load_cert_chain(fullchainlocation, privkeylocation)

async def init():
	app = web.Application()
	sio.attach(app)
	return app

def main():
	logging.basicConfig(level=logging.ERROR)
	loop = asyncio.get_event_loop()
	app = loop.run_until_complete(init()) #init sio in the loop

	loop.create_task(telemetry())
	loop.create_task(timeoutstop()) 
	loop.create_task(bodyControl())
	loop.create_task(lightingControl())
	loop.create_task(steeringTelemetry())
	loop.create_task(underglowControl())
	
	web.run_app(app, port=9876, ssl_context=ssl_context, loop=loop) #run sio in the loop

###create asyncio background tasks here###
async def telemetry():
	try:
		global hover1LastTime
		global hover2LastTime
		global hover1BatteryWarned
		global hover2BatteryWarned
		global hover1TelemetryWarned
		global hover2TelemetryWarned
		while True:
			await asyncio.sleep(1)
			
			if portbusy == False:
				feedback = ser.read_all()
				if feedback:
					if feedback[0] == 205 and feedback[1] == 171: #check start byte
						cmd1, cmd2, speedR_meas, speedL_meas, batVoltage, boardTemp, cmdLed = struct.unpack('<hhhhhhH', feedback[2:16])
						#print(f'cmd1: {cmd1}, cmd2: {cmd2}, speedR_meas: {speedR_meas}, speedL_meas: {speedL_meas}, batVoltage: {batVoltage}, boardTemp: {boardTemp}, cmdLed: {cmdLed}')	
						await sio.emit('telemetry', {"cmd1": cmd1, "cmd2": cmd2, "speedR_meas": speedR_meas, "speedL_meas": speedL_meas, "batVoltage": batVoltage/100, "boardTemp": boardTemp/10, "cmdLed": cmdLed})
						hover1LastTime = current_milli_time()
						if batVoltage < batteryWarningThreshold and hover1BatteryWarned == False:
							asyncio.create_task(adminEmail("HOVER #1 BATTERY LOW", "Hoverboard #1 Battery Voltage is low. Voltage: " + str(batVoltage) + " Threshold: " + str(batteryWarningThreshold)))
							hover1BatteryWarned = True
						if batVoltage > batteryWarningThreshold and hover1BatteryWarned == True:
							hover1BatteryWarned = False
							asyncio.create_task(adminEmail("HOVER #1 battery restored", "Hoverboard #1 Battery Voltage is normal. Voltage: " + str(batVoltage) + " Threshold: " + str(batteryWarningThreshold)))
				if fourwd == True:
					feedback2 = ser2.read_all()
					if feedback2:
						if feedback2[0] == 205 and feedback2[1] == 171: #check start byte
							cmd1, cmd2, speedR_meas, speedL_meas, batVoltage, boardTemp, cmdLed = struct.unpack('<hhhhhhH', feedback2[2:16])
							await sio.emit('telemetry2', {"cmd1": cmd1, "cmd2": cmd2, "speedR_meas": speedR_meas, "speedL_meas": speedL_meas, "batVoltage": batVoltage/100, "boardTemp": boardTemp/10, "cmdLed": cmdLed})
							hover2LastTime = current_milli_time()
							if batVoltage < batteryWarningThreshold and hover2BatteryWarned == False:
								asyncio.create_task(adminEmail("HOVER #2 BATTERY LOW", "Hoverboard #2 Battery Voltage is low. Voltage: " + str(batVoltage) + " Threshold: " + str(batteryWarningThreshold)))
								hover2BatteryWarned = True
							if batVoltage > batteryWarningThreshold and hover2BatteryWarned == True:
								hover2BatteryWarned = False
								asyncio.create_task(adminEmail("HOVER #2 battery restored", "Hoverboard #2 Battery Voltage is normal. Voltage: " + str(batVoltage) + " Threshold: " + str(batteryWarningThreshold)))

			if (current_milli_time()>=hover1LastTime+(telemetryWarningTimeout * 1000)) and hover1TelemetryWarned == False:			
				asyncio.create_task(adminEmail("HOVER #1 TELEMETRY TIMEOUT", "Hoverboard #1 TELEMETRY TIMEOUT. No telemetry has been received for this many seconds: " + str(telemetryWarningTimeout)))
				hover1TelemetryWarned = True
			elif (current_milli_time()<hover1LastTime+(telemetryWarningTimeout * 1000)) and hover1TelemetryWarned == True:
				hover1TelemetryWarned = False
				asyncio.create_task(adminEmail("HOVER #1 Telemetry Restored", "Hoverboard #1 Telemetry Restored."))
			
			if (current_milli_time()>=hover2LastTime+(telemetryWarningTimeout * 1000)) and hover2TelemetryWarned == False:			
				asyncio.create_task(adminEmail("HOVER #2 TELEMETRY TIMEOUT", "Hoverboard #2 TELEMETRY TIMEOUT. No telemetry has been received for this many seconds: " + str(telemetryWarningTimeout)))
				hover2TelemetryWarned = True
			elif (current_milli_time()<hover2LastTime+(telemetryWarningTimeout * 1000)) and hover2TelemetryWarned == True:
				hover2TelemetryWarned = False
				asyncio.create_task(adminEmail("HOVER #2 Telemetry Restored", "Hoverboard #2 Telemetry Restored."))

			if hover1TelemetryWarned or hover2TelemetryWarned:
				await sio.emit('warning', {"message": "Roamer has detected a traction power fault and may be disabled."})

			if hover1BatteryWarned or hover2BatteryWarned:
				await sio.emit('warning', {"message": "Roamer has a low battery and may die soon."})

	except Exception as e:
		print('TELEMETRY THREAD: EXCEPTION RAISED: {}'.format(e))
		

async def bodyControl():
	try:
		while True:
			await asyncio.sleep(0.2)
			if NavsparkDetected:
				while serNavspark.inWaiting():
					rawNavSparkData = serNavspark.readline()
					bodyControlData = (str(rawNavSparkData).replace("b'", "").replace("\\r\\n", "").replace("$", ""))[:-1]

					if "SONAR" in bodyControlData: # SONAR data			
						await handleSonar(bodyControlData)

					if "BUMP" in bodyControlData: # Bumpstop data
						await handleBump(bodyControlData)

					if "BUMP" not in bodyControlData and "SONAR" not in bodyControlData: # neither Bump or SONAR so we'll treat this as GPS data
						await handleGps(rawNavSparkData.decode('utf-8')) #send raw NMEA to GPS parser
	except Exception as e:
		print('EXCEPTION RAISED: {}'.format(e))

async def steeringTelemetry():
	try:
		while True:
			await asyncio.sleep(0.2)
			if Steeringdetected:
				while serSteering.inWaiting():
					rawSteerData = serSteering.readline()
					#steeringTelemetry = (str(rawSteerData).replace("b'", "").replace("\\r\\n", "").replace("$", ""))[:-1]
					steeringTelemetry = rawSteerData.decode('utf-8').replace('\x00',"") #sometimes there's nulls in the serial. Can't figure out why. This'll do.
					if "STEER" in steeringTelemetry: # just in case there's some other stuff in the chuffinch queue
						await handleSteerTelemetry(steeringTelemetry) 
	except Exception as e:
		print('STEERING TELEMETRY THREAD: EXCEPTION RAISED: {}'.format(e))

async def lightingControl():
	try:
		global leftIndicate
		global rightIndicate
		global hazards
		global headlights
		global braking
		global steeringLocal
		global clientConnected

		while True: #the loop time is NOT GOOD brian			
			if clientConnected or steeringLocal:
				for n in reversed(range(0, 9)):
					if rightIndicate or hazards:
						pixels[n] = ORANGE		
						pixels[Right_Rear_Indicate_Start + n] = ORANGE

					if leftIndicate or hazards:
						pixels[Left_Front_Indicate_End - n] = ORANGE		
						pixels[Left_Rear_Indicate_End - n] = ORANGE

					pixels.show()
					await asyncio.sleep(0.05)
				await asyncio.sleep(0.5)

				if headlights:
					for n in range(0, Left_Front_Indicate_End+1):
						pixels[n] = WHITE #set front bar to white	

				if braking:
					for n in range(Right_Rear_Indicate_Start, Left_Rear_Indicate_End+1):
						pixels[n] = RED #set rear bar to red
				else:
					for n in range(Right_Rear_Indicate_Start, Left_Rear_Indicate_End+1):
						pixels[n] = DIMRED #set rear bar to red
				
			else:
				await rainbow_cycle(0.003)
				await asyncio.sleep(0.81)

			pixels.show()
	except Exception as e:
		print('LIGHTING THREAD: EXCEPTION RAISED: {}'.format(e))

async def underglowControl():
	global clientConnected
	while True:
		if clientConnected:
			now = datetime.datetime.now()
			if now.hour >= daytimeHourStart and now.hour <= daytimeHourEnd: # it's daytime, dim the underglow.
				for n in range(Underglow_Start, Underglow_End):
					pixels[n] = OFF #Underglow off during the day
			else:				
				await underglow_rainbow_cycle(0.003)
		await asyncio.sleep(0.81)
				#print("nothing")

def wheel(pos):
	# Input a value 0 to 255 to get a color value.
	# The colours are a transition r - g - b - back to r.
	if pos < 0 or pos > 255:
		r = g = b = 0
	elif pos < 85:
		r = int(pos * 3)
		g = int(255 - pos * 3)
		b = 0
	elif pos < 170:
		pos -= 85
		r = int(255 - pos * 3)
		g = 0
		b = int(pos * 3)
	else:
		pos -= 170
		r = 0
		g = int(pos * 3)
		b = int(255 - pos * 3)
	return (r, g, b) if ORDER in (neopixel.RGB, neopixel.GRB) else (r, g, b, 0)

async def rainbow_cycle(wait):
	global clientConnected
	now = datetime.datetime.now()
	if now.hour >= daytimeHourStart and now.hour <= daytimeHourEnd: # daytime we only want to rainbow the headlight and rear bar
		for j in range(255):
			for i in range(Right_Front_Indicate_Start, Left_Rear_Indicate_End):
				if clientConnected:
					break
				pixel_index = (i * 256 // num_pixels) + j
				pixels[i] = wheel(pixel_index & 255)
			pixels.show()
			if clientConnected:
				break
			await asyncio.sleep(wait)
	else:
		for j in range(255):
			for i in range(num_pixels):
				if clientConnected:
					break
				pixel_index = (i * 256 // num_pixels) + j
				pixels[i] = wheel(pixel_index & 255)
			pixels.show()
			if clientConnected:
				break
			await asyncio.sleep(wait)

async def underglow_rainbow_cycle(wait):
	global clientConnected
	for j in range(255):
		for i in range(Underglow_Start, Underglow_End):
			if clientConnected == False:
				break
			pixel_index = (i * 256 // num_pixels) + j
			pixels[i] = wheel(pixel_index & 255)
		pixels.show()
		await asyncio.sleep(wait)

async def handleGps(nmeaGpsString):	
	try:
		global lastgpstime
		global lastGpsGeofenceSocketTime
		global lastGpsSocketTime
		global geoHaltMotors
		data,cksum,calc_cksum = nmeaChecksum(nmeaGpsString)
		if int(cksum,16) == int(calc_cksum,16):
			for x in nmeaGpsString:
				my_gps.update(x)

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
			#print("I can see " + str(my_gps.satellites_in_use) + " satellites. My fix is: " + fixtype + "  My coordinates are: " + str(lat) + "," + str(lng) + " The time is: " + timestr)
			try:	
				# post the GPS to the sockets at the highest rate we can
				if (lastGpsSocketTime + 2) < time.time():	
					lastGpsSocketTime = time.time()	
					await sio.emit('gpsData', {"lat": lat, "long": lng, "sats": sats, "speed": speed, "heading": my_gps.course, "fixtype": fixtype, "gpstime": timestr})	
				
				# only post the GPS data to the DB every 30 seconds, as it doesn't matter as much
				if (lastgpstime + 30) < time.time():
					lastgpstime = time.time()
					asyncio.create_task(postGpsData(lat, lng, sats, speed, fixtype, timestr, my_gps))

			except socket.error as socketerror:
				print("Error: ", socketerror)

			#geofencing
			point = Point(lng, lat)
			geoWarning = False
			geoHaltMotors = False
			geoWithinDataset = False
			for feature in js['features']:
				polygon = shape(feature['geometry'])
				if polygon.contains(point):
					geoWithinDataset = True
					if feature['properties']['type'] == "keepout":
						if (lastGpsGeofenceSocketTime + 1) < time.time():
							print('GPS is within Restricted zone: '+str(feature['properties']['level'])+' '+feature['properties']['type']+' named '+feature['properties']['title']+' the user will NOT be able to drive regardless of other conditions')
						geoHaltMotors = True
					elif feature['properties']['type'] == "warning":
						if (lastGpsGeofenceSocketTime + 1) < time.time():
							print('GPS is in a warning zone: '+str(feature['properties']['level'])+' '+feature['properties']['type']+' named '+feature['properties']['title']+' the user will be able to drive if there are no keepouts')
						geoWarning = True
					#elif feature['properties']['type'] == "keepin":
						#print('GPS is within bounds: '+str(feature['properties']['level'])+' '+feature['properties']['type']+' named '+feature['properties']['title']+' the user will be able to drive if there are no keepouts')	
			if geoWithinDataset == False:
				print("Point was not within dataset, must assume offsite")
				geoHaltMotors = True

			geoStatusText = "OK"
			if geoWarning:
				geoStatusText = "WARN"
			if geoHaltMotors:
				geoStatusText = "STOP"
			statusToSend = {"geofenceStatus": geoStatusText}
			if (lastGpsGeofenceSocketTime + 1) < time.time():
				lastGpsGeofenceSocketTime = time.time()
				await sio.emit('geofenceStatus', statusToSend)
		else:
			print("Error in checksum for GPS data: %s" % (data))
			print("Checksum is:" + str(hex(int(cksum,16))) + " expected " + str(hex(int(calc_cksum,16))))
	except Exception as e:
		print('GPS THREAD: EXCEPTION RAISED: {}'.format(e))

async def postGpsData(lat, lng, sats, speed, fixtype, timestr, my_gpsobj):
	print ("Posting GPS to database")
	geturl = "http://roamer.fun/gps/uploadgps.php?lat="+str(lat)+"&lng="+str(lng)+"&sats="+str(sats)+"&speed="+str(speed)+"&heading="+str(my_gpsobj.course)+"&fixtype="+fixtype+"&gpstime="+timestr
	async with ClientSession() as session:
		async with session.get(geturl) as response:
			response = await response.read()			
			print("GPS data posted to database")

async def handleSonar(sonarString):
	try:
		global frontProxBreach
		global rearProxBreach
		data,cksum,calc_cksum = nmeaChecksum(sonarString)
		if cksum == calc_cksum: #how tf does this work
			sonarSplit = data.replace("SONAR,", "").split(",")
			sonar_list = []
			for pair in sonarSplit:
				angleStr,distanceStr = pair.split(":")
				angle = int(angleStr)
				distance = int(distanceStr)
				if angle == 0 and distance < frontThreshold:
					frontProxBreach = True
					await sio.emit('warning', {"message": "Font proximity sensor has been breached. Please reverse."})
				elif angle == 0 and distance > frontThreshold:
					frontProxBreach = False

				if angle == 180 and distance < rearThreshold:
					rearProxBreach = True
					await sio.emit('warning', {"message": "Rear proximity sensor has been breached. Please reverse."})
				elif angle == 180 and distance > rearThreshold:
					rearProxBreach = False

				if angle == 90 and distance < sideThreshold:
					await sio.emit('warning', {"message": "Right proximity sensor warning. Please be careful."})
				if angle == 270 and distance < sideThreshold:
					await sio.emit('warning', {"message": "Left proximity sensor warning. Please be careful."})

				sonarToAdd = {"angle": int(angle), "distance": int(distance)}
				sonar_list.append(sonarToAdd)

			if sonar_list:
				await sio.emit('sonar', sonar_list)

		else:
			print("Error in checksum for SONAR data: %s" % (data))
			print("Checksums are %s and %s" % (cksum,calc_cksum))
	except Exception as e:
		print('SONAR THREAD: EXCEPTION RAISED: {}'.format(e))

async def handleBump(bumpString):
	try:
		global frontBumped
		global rearBumped
		data,cksum,calc_cksum = nmeaChecksum(bumpString)
		if cksum == calc_cksum: #how tf does this work
			bumpSplit = data.split(",")
			angle = int(bumpSplit[1])
			state = int(bumpSplit[2])
			#bumpToSend = {"angle": angle, "state": state}

			if angle == 0 and state == 1:
				frontBumped = True
				await sio.emit('warning', {"message": "Font bumpswitch has been activated. Please reverse."})
			elif angle == 0 and state == 0:
				frontBumped = False

			if angle == 180 and state == 1:
				rearBumped = True
				await sio.emit('warning', {"message": "Rear bumpswitch has been activated. Please move forward."})
			elif angle == 180 and state == 0:
				rearBumped = False

			#if bumpToSend:
			#	await sio.emit('bump', bumpToSend)
		else:
			print("Error in checksum for BUMP data: %s" % (data))
			print("Checksums are %s and %s" % (cksum,calc_cksum))
	except Exception as e:
		print('BUMP THREAD: EXCEPTION RAISED: {}'.format(e))

async def handleSteerTelemetry(steerString):
	global braking
	global steerHaltMotors
	global steeringLocal
	global steerLockoutWarned
	data,cksum,calc_cksum = nmeaChecksum(steerString)
	if int(cksum,16) == int(calc_cksum,16):
		steerSplit = data.split(",")
		if data.isprintable() == False:
			print("Nonprintable data found in sentence")
			print("data is " + data.encode('unicode_escape').decode('ascii'))
			print("data array is " , steerSplit)
		else:
			steerInput = int(steerSplit[1])
			steerGear = str(steerSplit[2])
			steerManualBrake = int(steerSplit[3])
			steerPedalAvg = int(steerSplit[4])
			steerSteerSp = steerSplit[5]
			steerSteerIp = steerSplit[6]
			steerSteerOp = steerSplit[7]
			steerCurrentIp = steerSplit[8]
			steerCurrentOp = steerSplit[9]
			steerCurrentLimiting = int(steerSplit[10])
			steerLockout = int(steerSplit[11])
			steerSentSpeed = int(steerSplit[12])
			steerSentBrake = int(steerSplit[13])

			#print("Steering current: ", steerCurrentIp)
			#print("steerCurrentLimiting : ", steerCurrentLimiting)
			#print("data is " + data.encode('unicode_escape').decode('ascii'))

			if steerLockout != 0:
				steerHaltMotors = True
				print("Steering is locked out!")
				await sio.emit('warning', {"message": "Roamer has detected a steering fault and has been disabled."})
				if steerLockoutWarned == False:
					asyncio.create_task(adminEmail("Steering Locked Out", "The steering has been locked out"))
				steerLockoutWarned = True
			
			else:
				steerHaltMotors = False
				steerLockoutWarned = False

			if steerManualBrake > 0 or steerManualBrake > 0:
				braking = True
			else:
				braking = False

			if steerInput == 0:
				steeringLocal = True
			else:
				steeringLocal = False

	else:
		print("Error in checksum for STEER data: %s" % (data))
		print("raw data dump: " + data.encode('unicode_escape').decode('ascii'))
		print("Checksums are %s and %s" % (cksum,calc_cksum))
		time.sleep(3)

def nmeaChecksum(sentence):
	#if re.search("\n$", sentence):
	#	sentence = sentence[:-1]

	#sentence = sentence.replace('$', '')
	#print("sentence " + sentence)

	if "*" in sentence:
		nmeadata,cksum = re.split('\*', sentence)
	else:
		print("Sentence was missing checksum.")
		return sentence,('0xDE').lower(),('0xAD').lower()

	#print("nmeadata " + nmeadata)
	#print("cksum " + cksum)
	calc_cksum = 0
	for s in nmeadata.replace('$', ''):
		calc_cksum ^= ord(s)

	return nmeadata,('0x'+cksum).lower(),'0x'+"{:02x}".format(calc_cksum).lower()

def current_milli_time():
	return round(time.time_ns() / 1000000)

async def timeoutstop():
	while True:
		await asyncio.sleep(0.25)
		try:
			global lasttime
			if (current_milli_time()>=lasttime+500):
				#print("----Control Timeout!!---- Lasttime:" + str(lasttime) + " Now:" + str(current_milli_time()) + " ----Motors Stopped!!----")
				stp()
		except BaseException as error:
			print('An exception occurred in timeoutstop: {}'.format(error))

#handle socket events
@sio.on('control')
async def handle_control(sid, control):
	print("CTRL msg from: " , sid)
	if control == "s":
		print("motors stop")
		stp() #motors STOP
	if control == "f":
		SendAndResetTimeout(0,50)
	if control == "b":
		SendAndResetTimeout(0,-50)
	if control == "l":
		SendAndResetTimeout(-50,0)
	if control == "r":
		SendAndResetTimeout(50,0)
	if control == "fl":
		SendAndResetTimeout(-50,20)
	if control == "fr":
		SendAndResetTimeout(50,20)
	if control == "bl":
		SendAndResetTimeout(50,-20)
	if control == "br":
		SendAndResetTimeout(-50,-20)

@sio.on('analog')
async def handle_analog(sid, control):
	print("ANALOG msg from: " , sid)
	print("steer: " + str(int(control.split(',')[0])))
	print("speed: " + str(int(control.split(',')[1])))
	SendAndResetTimeout(int(control.split(',')[0]),int(control.split(',')[1]))

@sio.on('haltmotoroverride')
async def handle_haltmotoroverride(sid, override):
	global haltMotorOverride
	print("MOTOR HALT OVERRIDE RECEIVED: ", override)
	if override == True:
		haltMotorOverride = True
		print("Halt Motor BOOL IS OVERRIDDEN")
	else:
		haltMotorOverride = False
		print("Halt Motor BOOL IS NOT OVERRIDDEN")

@sio.on('haltmotorreset')
async def handle_haltmotorreset(sid, resetflg):
	global steerHaltMotors
	print("MOTOR HALT RESET RECEIVED: ", resetflg)
	if resetflg == True:
		steerHaltMotors = False
		print("Halt Motor BOOL has been reset")

@sio.event
async def connect(sid, environ):
	print('Client Connected: ', sid)
	global clientConnected
	clientConnected = True

@sio.event
async def disconnect(sid):
	print('Client Disconnected: ', sid)
	global clientConnected
	clientConnected = False
	print("motors stop")
	stp()

# def uploadTelemetry():
# 	try:
# 		geturl = "http://roamer.fun/telemetry/uploadtelemetry.php?iSpeedL="+str(iSpeedL)+"&iSpeedR="+str(iSpeedR)+"&iTemp="+str(iTemp)+"&iVolt="+str(iVolt)+"&iAmpL="+str(iAmpL)+"&iAmpR="+str(iAmpR)
# 		r = urllib.request.Request(geturl)
# 		with urllib.request.urlopen(r) as response:
# 			the_page = response.read()
# 	except urllib.error.URLError as e:
# 		print(e.reason)  

if __name__ == '__main__':
	main()
