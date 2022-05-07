from contextlib import nullcontext
import serial, struct, time, numpy # for hoverboard comms
import urllib.request
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

socket.setdefaulttimeout(10)
lastgpstime = 0
my_gps = MicropyGPS()

#limits & configuration
maxfwdspeed = 50.0 #max fwd speed
maxrevspeed = 25.0 #max reverse speed
steerauth = 0.4 #adjust how much 100% steering actually steers (don't do nuffink)
speedsteercomp = 2.2 #more steering authority at speed. 2.0 = double steering authority at 100% speed (don't do nuffink)
PortHoverboard1 = '/dev/serial0'

fullchainlocation = '/etc/letsencrypt/live/bigclamps.loseyourip.com/fullchain.pem'
privkeylocation = '/etc/letsencrypt/live/bigclamps.loseyourip.com/privkey.pem'

global portbusy
portbusy = False

lasttime = 0
fourwd = False

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

pixels = neopixel.NeoPixel(
	pixel_pin, num_pixels, brightness=0.2, auto_write=False, pixel_order=ORDER
)

global braking
braking = False

global hazards
hazards = False

global leftIndicate
leftIndicate = False

global rightIndicate
rightIndicate = False

global headlights
headlights = False

global idleAnimation
idleAnimation = False

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
				time.sleep(3)	
				attempts = 0			
				while attempts < 5:
					attempts += 1		
					detection = serialAttempt.read_all()
					try:
						if detection[0] == 205 and detection[1] == 171 and fourwd == False:
							fourwd = True
							ser2 = serialAttempt
							print("4WD Mode - 2nd Hoverboard detected on port:" + port)		
							break		
						elif "$SONAR" in str(serialAttempt.readline()).replace("b'", "") and NavsparkDetected == False:
							NavsparkDetected = True
							serNavspark = serialAttempt
							print("NavSpark detected on port:" + port)	
							break
						elif Steeringdetected == False:
							Steeringdetected = True
							serSteering = serialAttempt
							print("Steering detected on port: " + port)	
							break		
					except:
						print("Can't determine port type. Is it connected? Port: " + port)	

except Exception as e:
	print("Port auto-detection failed.")

print("")
print("")
print("PORT DETECTION SUMMARY:")
print("NavSpark detected: " + str(NavsparkDetected))
print("Steering detected: " + str(Steeringdetected))
print("Hoverboard #2 detected: " + str(fourwd))
print("")
print("")
##############################################

def sendcmd(steerin,speed):
	'''
	Sends a bytearray for controlling the hoverboard
	:param steer: -1000...1000	:param speed: -1000...1000	:
	'''
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

	portbusy = True
	startB = bytes.fromhex('ABCD')[::-1] # lower byte first
	steerB = struct.pack('h', steer)
	speedB = struct.pack('h', speed)
	brakeB = struct.pack('h', 0) #don't bother with braking in speed mode
	driveModeB = struct.pack('h', 2) #2=speed, 3=torque
	crcB = bytes(a^b^c^d^e for (a, b, c, d, e) in zip(startB, steerB, speedB, brakeB, driveModeB))
	ser.write(startB+steerB+speedB+brakeB+driveModeB+crcB)
	if fourwd:
		ser2.write(startB+steerB+speedB+brakeB+driveModeB+crcB)


	#do the arduino steering
	if Steeringdetected:
		steerin = steerin * -1 #because it's backwards
		if haltMotors == True and haltMotorOverride == False:
			steerin = 0
		serSteering.write((str(numpy.clip(100,-100,steerin))+"\n").encode('utf_8')) #old mode
	portbusy = False


def SendAndResetTimeout(steer,speed):
	sendcmd(steer,speed)
	global lasttime
	lasttime = int(time.time())

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

	loop.create_task(telemetry()) #add background task
	loop.create_task(timeoutstop()) #add background task
	loop.create_task(bodyControl())

	loop.create_task(indicate_right())
	loop.create_task(indicate_left())

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
		await asyncio.sleep(0.5)
		if NavsparkDetected:
			while serNavspark.inWaiting():
				rawNavSparkData = serNavspark.readline()
				bodyControlData = (str(rawNavSparkData).replace("b'", "").replace("\\r\\n", "").replace("$", ""))[:-1]

				if "SONAR" in bodyControlData: # SONAR data			
					await handleSonar(bodyControlData)

				if "BUMP" in bodyControlData: # Bumpstop data
					await handleBump(bodyControlData)

				if "BUMP" not in bodyControlData and "SONAR" not in bodyControlData: # neither Bump or SONAR so we'll treat this as GPS data
					handleGps(bodyControlData)

async def lightingControl():
	indicate_right()
	indicate_left()

async def indicate_right():
	while True:
		await sweep_fill_range(pixels, ORANGE, Right_Front_Indicate_Start, Right_Front_Indicate_End, True)
		await asyncio.sleep(0.5)
		for n in reversed(range(Right_Front_Indicate_Start,Right_Front_Indicate_End+1)):
			pixels[n] = WHITE
 
async def indicate_left():
	while True:
		await sweep_fill_range(pixels, ORANGE, Left_Front_Indicate_Start, Left_Front_Indicate_End)
		await asyncio.sleep(0.5)
		for n in range(Left_Front_Indicate_Start,Left_Front_Indicate_End+1):
			pixels[n] = WHITE

async def sweep_fill_range(neo,color=(255,0,0),start=0,end=7,reversedir=False,delay=0.05):
    if reversedir:
        for n in reversed(range(start,end+1)):
            neo[n]=color
            neo.show()
            await asyncio.sleep(delay)
    else:
        for n in range(start, end+1):
            neo[n]=color
            neo.show()
            await asyncio.sleep(delay)

def handleGps(nmeaGpsString):	
	global lastgpstime
	data,cksum,calc_cksum = nmeaChecksum(nmeaGpsString)
	if cksum == calc_cksum:
		for x in nmeaGpsString:
			my_gps.update(x)
		if (lastgpstime + 30) < time.time():
			lastgpstime = time.time()
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
			
			#geofencing
			point = Point(lng, lat)
			for feature in js['features']:
				polygon = shape(feature['geometry'])
				if polygon.contains(point):
					if feature['properties']['type'] == "keepout":
						print('GPS is within Restricted zone: '+str(feature['properties']['level'])+' '+feature['properties']['type']+' named '+feature['properties']['title']+' the user will NOT be able to drive regardless of other conditions')
						haltMotors = True
						statusToSend = {"geofenceStatus": "keepout"}
						sio.emit('geofenceStatus', statusToSend)
					elif feature['properties']['type'] == "warning":
						print('GPS is in a warning zone: '+str(feature['properties']['level'])+' '+feature['properties']['type']+' named '+feature['properties']['title']+' the user will be able to drive if there are no keepouts')
						haltMotors = False
						statusToSend = {"geofenceStatus": "warning"}
						sio.emit('geofenceStatus', statusToSend)
					elif feature['properties']['type'] == "keepin":
						print('GPS is within bounds: '+str(feature['properties']['level'])+' '+feature['properties']['type']+' named '+feature['properties']['title']+' the user will be able to drive if there are no keepouts')
						haltMotors = False
						statusToSend = {"geofenceStatus": "keepin"}
						sio.emit('geofenceStatus', statusToSend)				
					else:
						print('GPS is out of the keep in zone: '+str(feature['properties']['level'])+' '+feature['properties']['type']+' named '+feature['properties']['title']+' the user will be able to drive if there are no keepouts')
						haltMotors = True
						statusToSend = {"geofenceStatus": "outOfBounds"}
						sio.emit('geofenceStatus', statusToSend)

			try:
				print ("posting the shit")

				geturl = "http://roamer.chris-stubbs.co.uk/gps/uploadgps.php?lat="+str(lat)+"&lng="+str(lng)+"&sats="+str(sats)+"&speed="+str(speed)+"&heading="+str(my_gps.course)+"&fixtype="+fixtype+"&gpstime="+timestr
				r = requests.get(geturl)
				print(r)
				print("shit posted")
				print("")
			except socket.error as socketerror:
				print("Error: ", socketerror)
	else:
		print("Error in checksum for GPS data: %s" % (data))
		print("Checksums are %s and %s" % (cksum,calc_cksum))

async def handleSonar(sonarString):
	data,cksum,calc_cksum = nmeaChecksum(sonarString)
	if cksum == calc_cksum:
		sonarSplit = data.replace("SONAR,", "").split(",")
		sonar_list = []
		for pair in sonarSplit:
			angle,distance = pair.split(":")

			if angle == 0 and distance < frontThreshold:
				frontProxBreach = True
			else:
				frontProxBreach = False

			if angle == 180 and distance < rearThreshold:
				rearProxBreach = True
			else:
				rearProxBreach = False

			sonarToAdd = {"angle": int(angle), "distance": int(distance)}
			sonar_list.append(sonarToAdd)

		if sonar_list:
			await sio.emit('sonar', sonar_list)

	else:
		print("Error in checksum for SONAR data: %s" % (data))
		print("Checksums are %s and %s" % (cksum,calc_cksum))

async def handleBump(bumpString):
	data,cksum,calc_cksum = nmeaChecksum(bumpString)
	if cksum == calc_cksum:
		bumpSplit = data.split(",")
		angle = int(bumpSplit[1])
		state = int(bumpSplit[2])
		bumpToSend = {"angle": angle, "state": state}

		if angle == 0 and state == 1:
			frontBumped = True
		else:
			frontBumped = False

		if angle == 180 and state == 1:
			rearBumped = True
		else:
			rearBumped = False

		if bumpToSend:
			await sio.emit('bump', bumpToSend)
	else:
		print("Error in checksum for BUMP data: %s" % (data))
		print("Checksums are %s and %s" % (cksum,calc_cksum))

def nmeaChecksum(sentence):
	if re.search("\n$", sentence):
		sentence = sentence[:-1]

	nmeadata,cksum = re.split('\*', sentence)

	calc_cksum = 0
	for s in nmeadata:
		calc_cksum ^= ord(s)

	return nmeadata,('0x'+cksum).lower(),'0x'+"{:02x}".format(calc_cksum).lower()

async def timeoutstop():
	while True:
		await asyncio.sleep(0.5)
		try:
			global lasttime
			if (int(time.time())>=int(lasttime+2)):
				print("----Control Timeout!!---- Lasttime:" + str(lasttime) + " Now:" + str(int(time.time())) + " ----Motors Stopped!!----")
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
	SendAndResetTimeout(int(control.split(',')[0]),int(control.split(',')[1]))

@sio.on('haltmotoroverride')
async def handle_haltmotoroverride(sid, override):
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

@sio.event
async def disconnect(sid):
	print('Client Disconnected: ', sid)
	print("motors stop")
	stp()

def uploadTelemetry():
	try:
		geturl = "http://roamer.chris-stubbs.co.uk/telemetry/uploadtelemetry.php?iSpeedL="+str(iSpeedL)+"&iSpeedR="+str(iSpeedR)+"&iTemp="+str(iTemp)+"&iVolt="+str(iVolt)+"&iAmpL="+str(iAmpL)+"&iAmpR="+str(iAmpR)
		r = urllib.request.Request(geturl)
		with urllib.request.urlopen(r) as response:
 			the_page = response.read()
	except urllib.error.URLError as e:
		print(e.reason)  

if __name__ == '__main__':
	main()