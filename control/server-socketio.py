from contextlib import nullcontext
import serial, struct, time, numpy # for hoverboard comms
import urllib.request
import urllib.parse
from aiohttp import web
import socketio, ssl, asyncio, logging
import re
import socket
from micropyGPS import MicropyGPS
import requests
import json
from shapely.geometry import shape, Point
import serial.tools.list_ports
import time
import board
import neopixel
import sys

socket.setdefaulttimeout(10)
lastgpstime = 0
my_gps = MicropyGPS()

#limits & configuration
maxfwdspeed = 50.0 #max fwd speed
maxrevspeed = 25.0 #max reverse speed
steerauth = 0.4 #adjust how much 100% steering actually steers (don't do nuffink)
speedsteercomp = 2.2 #more steering authority at speed. 2.0 = double steering authority at 100% speed (don't do nuffink)
global StopRetryCount 
StopRetryCount = 1 #how many times to send the stop signal in case the serial is awful
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

global clientConnected
clientConnected = False

#global motor halt vars for GPS/SONAR/BUMP
global haltMotors
haltMotors = False

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

#distance thresholds for SONAR to halt motors
frontThreshold = 15
rearThreshold = 15
leftThreshold = 15
rightThreshold = 15

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

#default the port states to false:
fourwd = False
NavsparkDetected = False
Steeringdetected = False
#connect to hoverboard
ser = serial.Serial(PortHoverboard1, 115200, timeout=5)  # open main serial port

# connect to ports (auto-detection)
try:
	ports = serial.tools.list_ports.comports()
	print("Begin Serial Autodetection")
	for port, desc, hwid in sorted(ports):
			if "USB" in port:
				print("{}: {} [{}]".format(port, desc, hwid))
				serialAttempt = serial.Serial(port, 115200, timeout=5)
				time.sleep(5)
				attempts = 0			
				while attempts < 3:
					try:
						attempts += 1
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
						elif "$STEER" in str(detection.decode('utf-8')) and Steeringdetected == False:
							Steeringdetected = True
							serSteering = serialAttempt
							print("Steering detected on port: " + port)	
							break		
					except:
						print("Can't determine port type. Is it connected? Port: " + port)	

except Exception as e:
	print("Port auto-detection failed.")

detectionSummary = "NavSpark detected: " + str(NavsparkDetected) + "\nSteering detected: " + str(Steeringdetected) + "\nHoverboard #2 detected: " + str(fourwd) + "\n"
print("PORT DETECTION SUMMARY:")
print(detectionSummary)
print("")
print("")

def adminEmail(sub, msg):
	if enableAdminEmail:
		try:
			encodedMsg = urllib.parse.quote(msg, safe='')
			encodedSub = urllib.parse.quote(sub, safe='')

			geturl = "https://roamer.fun/admin/mail.php?sec=PIPEallNIGHT&sub="+str(encodedSub)+"&msg="+str(encodedMsg)
			print (geturl)
			ua = 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.7) Gecko/2009021910 Firefox/3.0.7'
			r = requests.get(geturl,headers={"User-Agent": ua})
			print(r)
			print("email sent")
		except socket.error as socketerror:
			print("Error: ", socketerror)

if NavsparkDetected and Steeringdetected and fourwd:
	adminEmail("Roamer control started", detectionSummary)
else:
	adminEmail("Serial autodetection issue",detectionSummary)
##############################################

def sendcmd(steerin,speed):
	'''
	Sends a bytearray for controlling the hoverboard
	:param steer: -1000...1000	:param speed: -1000...1000	:
	'''
	#print("Sendcmd("+str(steerin)+","+str(speed)+")")

	global haltMotors
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
		if haltMotors == True and haltMotorOverride == False: # if the Motors are halted because of Geofencing then set speed to 0 unless it's overridden by the FE
			speed = 0

	if haltMotorsOnBump:
		if frontBumped == True and haltMotorOverride == False and speed > 0: # the front bump stop is pushed, set speed to 0 if they're trying to go forward. otherwise let it reverse
			speed = 0
		if rearBumped == True and haltMotorOverride == False and speed < 0: # the rear bump stop is pushed, set speed to 0 if they're trying to go in reverse. otherwise let it go forward
			speed = 0

	if haltMotorsOnProxBreach:
		if frontProxBreach == True and haltMotorOverride == False and speed > 0: # the front bump stop is pushed, set speed to 0 if they're trying to go forward. otherwise let it reverse
			speed = 0
		if rearProxBreach == True and haltMotorOverride == False and speed < 0: # the rear bump stop is pushed, set speed to 0 if they're trying to go in reverse. otherwise let it go forward
			speed = 0

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
		ser.write(startB+steerB+speedB+brakeB+driveModeB+crcB)
		if fourwd:
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
		if haltMotors == True and haltMotorOverride == False:
			steerin = 0
		serSteering.write((str(numpy.clip(100,-100,steerin))+"\n").encode('utf_8')) #old mode
	portbusy = False

	global lastSerialSendMs
	timez = current_milli_time()-lastSerialSendMs
	#print("ms since last serial: " + str(timez))
	if timez > 700:
		print("WARNING TIME SINCE LAST SERIAL SEND: "+ str(timez))
	lastSerialSendMs = current_milli_time()


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
	
	web.run_app(app, port=9876, ssl_context=ssl_context, loop=loop) #run sio in the loop

###create asyncio background tasks here###
async def telemetry():
	while True:
		await asyncio.sleep(1)
		if portbusy == False:
			feedback = ser.read_all()
			if feedback:
				if feedback[0] == 205 and feedback[1] == 171: #check start byte
					cmd1, cmd2, speedR_meas, speedL_meas, batVoltage, boardTemp, cmdLed = struct.unpack('<hhhhhhH', feedback[2:16])
					#print(f'cmd1: {cmd1}, cmd2: {cmd2}, speedR_meas: {speedR_meas}, speedL_meas: {speedL_meas}, batVoltage: {batVoltage}, boardTemp: {boardTemp}, cmdLed: {cmdLed}')	
					await sio.emit('telemetry', {"cmd1": cmd1, "cmd2": cmd2, "speedR_meas": speedR_meas, "speedL_meas": speedL_meas, "batVoltage": batVoltage/100, "boardTemp": boardTemp/10, "cmdLed": cmdLed})
			if fourwd == True:
				feedback2 = ser2.read_all()
				if feedback2:
					if feedback2[0] == 205 and feedback2[1] == 171: #check start byte
						cmd1, cmd2, speedR_meas, speedL_meas, batVoltage, boardTemp, cmdLed = struct.unpack('<hhhhhhH', feedback2[2:16])
						await sio.emit('telemetry2', {"cmd1": cmd1, "cmd2": cmd2, "speedR_meas": speedR_meas, "speedL_meas": speedL_meas, "batVoltage": batVoltage/100, "boardTemp": boardTemp/10, "cmdLed": cmdLed})

async def bodyControl():
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

async def steeringTelemetry():
	while True:
		await asyncio.sleep(0.2)
		if Steeringdetected:
			while serSteering.inWaiting():
				rawSteerData = serSteering.readline()
				#steeringTelemetry = (str(rawSteerData).replace("b'", "").replace("\\r\\n", "").replace("$", ""))[:-1]
				steeringTelemetry = rawSteerData.decode('utf-8')
				if "STEER" in steeringTelemetry: # just in case there's some other stuff in the chuffinch queue
					await handleSteerTelemetry(steeringTelemetry.replace('\x00',"")) #sometimes there's nulls in the serial. Can't figure out why. This'll do.

async def lightingControl():
	global leftIndicate
	global rightIndicate
	global hazards
	global headlights
	global braking
	global steeringLocal

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
	for j in range(255):
		for i in range(num_pixels):
			pixel_index = (i * 256 // num_pixels) + j
			pixels[i] = wheel(pixel_index & 255)
		pixels.show()
		await asyncio.sleep(wait)

async def handleGps(nmeaGpsString):	
	global lastgpstime
	global haltMotors
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
			await sio.emit('gpsData', {"lat": lat, "long": lng, "sats": sats, "speed": speed, "heading": my_gps.course, "fixtype": fixtype, "gpstime": timestr})	
			
			# only post the GPS data to the DB every 30 seconds, as it doesn't matter as much
			if (lastgpstime + 30) < time.time():
				lastgpstime = time.time()
				print ("Posting GPS to database")
				geturl = "http://roamer.fun/gps/uploadgps.php?lat="+str(lat)+"&lng="+str(lng)+"&sats="+str(sats)+"&speed="+str(speed)+"&heading="+str(my_gps.course)+"&fixtype="+fixtype+"&gpstime="+timestr
				print (geturl)
				ua = 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.7) Gecko/2009021910 Firefox/3.0.7'
				r = requests.get(geturl,headers={"User-Agent": ua})
				print(r)
				print("GPS data posted to database")

		except socket.error as socketerror:
			print("Error: ", socketerror)

		#geofencing
		point = Point(lng, lat)
		haltMotors = False
		GeoWarning = False
		GeowithinDataset = False
		for feature in js['features']:
			polygon = shape(feature['geometry'])
			if polygon.contains(point):
				GeowithinDataset = True
				if feature['properties']['type'] == "keepout":
					print('GPS is within Restricted zone: '+str(feature['properties']['level'])+' '+feature['properties']['type']+' named '+feature['properties']['title']+' the user will NOT be able to drive regardless of other conditions')
					haltMotors = haltMotors or True
					statusToSend = {"geofenceStatus": "keepout"}
					#await sio.emit('geofenceStatus', statusToSend)
				elif feature['properties']['type'] == "warning":
					print('GPS is in a warning zone: '+str(feature['properties']['level'])+' '+feature['properties']['type']+' named '+feature['properties']['title']+' the user will be able to drive if there are no keepouts')
					haltMotors = haltMotors or False
					GeoWarning = True
					#statusToSend = {"geofenceStatus": "warning"}
					#await sio.emit('geofenceStatus', statusToSend)
				elif feature['properties']['type'] == "keepin":
					#print('GPS is within bounds: '+str(feature['properties']['level'])+' '+feature['properties']['type']+' named '+feature['properties']['title']+' the user will be able to drive if there are no keepouts')
					haltMotors = haltMotors or False
					statusToSend = {"geofenceStatus": "keepin"}
					#await sio.emit('geofenceStatus', statusToSend)				
		if GeowithinDataset == False:
			print("Point was not within dataset, must assume offiste")
			haltMotors = haltMotors or True
			statusToSend = {"geofenceStatus": "outOfBounds"}
			#await sio.emit('geofenceStatus', statusToSend)
		GeoStatusText = "OK"
		if GeoWarning:
			GeoStatusText = "WARN"
		if haltMotors:
			GeoStatusText = "STOP"
		statusToSend = {"geofenceStatus": GeoStatusText}
		await sio.emit('geofenceStatus', statusToSend)
	else:
		print("Error in checksum for GPS data: %s" % (data))
		print("Checksum is:" + str(hex(int(cksum,16))) + " expected " + str(hex(int(calc_cksum,16))))


async def handleSonar(sonarString):
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
			elif angle == 0 and distance > frontThreshold:
				frontProxBreach = False

			if angle == 180 and distance < rearThreshold:
				rearProxBreach = True
			elif angle == 180 and distance > rearThreshold:
				rearProxBreach = False

			sonarToAdd = {"angle": int(angle), "distance": int(distance)}
			sonar_list.append(sonarToAdd)

		if sonar_list:
			await sio.emit('sonar', sonar_list)

	else:
		print("Error in checksum for SONAR data: %s" % (data))
		print("Checksums are %s and %s" % (cksum,calc_cksum))

async def handleBump(bumpString):
	global frontBumped
	global rearBumped
	data,cksum,calc_cksum = nmeaChecksum(bumpString)
	if cksum == calc_cksum: #how tf does this work
		bumpSplit = data.split(",")
		angle = int(bumpSplit[1])
		state = int(bumpSplit[2])
		bumpToSend = {"angle": angle, "state": state}

		if angle == 0 and state == 1:
			frontBumped = True
		elif angle == 0 and state == 0:
			frontBumped = False

		if angle == 180 and state == 1:
			rearBumped = True
		elif angle == 180 and state == 0:
			rearBumped = False

		if bumpToSend:
			await sio.emit('bump', bumpToSend)
	else:
		print("Error in checksum for BUMP data: %s" % (data))
		print("Checksums are %s and %s" % (cksum,calc_cksum))

async def handleSteerTelemetry(steerString):
	global braking
	global haltMotors
	global steeringLocal
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

			if steerLockout != 0:
				haltMotors = True
				print("Steering is locked out!")
			else:
				haltMotors = False

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

def uploadTelemetry():
	try:
		geturl = "http://roamer.fun/telemetry/uploadtelemetry.php?iSpeedL="+str(iSpeedL)+"&iSpeedR="+str(iSpeedR)+"&iTemp="+str(iTemp)+"&iVolt="+str(iVolt)+"&iAmpL="+str(iAmpL)+"&iAmpR="+str(iAmpR)
		r = urllib.request.Request(geturl)
		with urllib.request.urlopen(r) as response:
			the_page = response.read()
	except urllib.error.URLError as e:
		print(e.reason)  

if __name__ == '__main__':
	main()
