from contextlib import nullcontext
import serial, struct, time, numpy # for hoverboard comms
import urllib.request
from aiohttp import web
import socketio, ssl, asyncio, logging
import re

#limits & configuration
maxfwdspeed = 150.0 #max fwd speed
maxrevspeed = 100.0 #max reverse speed
steerauth = 0.4 #adjust how much 100% steering actually steers
speedsteercomp = 2.2 #more steering authority at speed. 2.0 = double steering authority at 100% speed
PortHoverboard1 = '/dev/serial0'
PortHoverboard2 = '/dev/ttyUSB9999'
PortSteering = '/dev/ttyUSB0'
PortSONAR = '/dev/ttyUSB9999'
fullchainlocation = '/etc/letsencrypt/live/bigclamps.loseyourip.com/fullchain.pem'
privkeylocation = '/etc/letsencrypt/live/bigclamps.loseyourip.com/privkey.pem'

global portbusy
portbusy = False

lasttime = 0
fourwd = False

#connect to hoverboard
ser = serial.Serial(PortHoverboard1, 115200, timeout=1)  # open main serial port
try:
	
	ser2 = serial.Serial(PortHoverboard2, 115200, timeout=1)  # open secondary serial port 
	fourwd = True
	print("4WD detected")
except:
	fourwd = False
	print("2WD only detected")

#connect to sonar
try:
	serSONAR = serial.Serial(PortSONAR, 115200, timeout=1)  # open sonar serial port 
	SONARdetected = True
	print("SONAR detected")
except:
	SONARdetected = False
	print("SONAR not detected")

#connect to steering
try:
	serSteering = serial.Serial(PortSteering, 115200, timeout=1)  # open steering serial port 
	Steeringdetected = True
	print("Steering detected")
except:
	Steeringdetected = False
	print("Steering not detected")

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
	steer = 0

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
		serSteering.write((str(numpy.clip(100,-100,steerin))+"\n").encode('utf_8'))
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

	loop.create_task(temeletry()) #add background task
	loop.create_task(timeoutstop()) #add background task
	loop.create_task(sonar())

	web.run_app(app, port=9876, ssl_context=ssl_context, loop=loop) #run sio in the loop

###create asyncio background tasks here###
async def temeletry():
	while True:
		await asyncio.sleep(1)
		if portbusy == False:
			feedback = ser.read_all()
			if feedback:
				if feedback[0] == 205 and feedback[1] == 171: #check start byte
					cmd1, cmd2, speedR_meas, speedL_meas, batVoltage, boardTemp, cmdLed = struct.unpack('<hhhhhhH', feedback[2:16])
					#print(f'cmd1: {cmd1}, cmd2: {cmd2}, speedR_meas: {speedR_meas}, speedL_meas: {speedL_meas}, batVoltage: {batVoltage}, boardTemp: {boardTemp}, cmdLed: {cmdLed}')	
					await sio.emit('telemetry', {"cmd1": cmd1, "cmd2": cmd2, "speedR_meas": speedR_meas, "speedL_meas": speedL_meas, "batVoltage": batVoltage/100, "boardTemp": boardTemp/10, "cmdLed": cmdLed})

async def sonar():
	while True:
		await asyncio.sleep(0.5)
		rawSonarData = serSONAR.readline()
		strSonarData = str(rawSonarData)
		if "SONAR" in strSonarData:
			sonarData = strSonarData.replace("b'SONAR{", "").replace("}","").replace("\\r\\n", "").replace("'", "")
			sonarSplit = sonarData.split(",")
			sonar_list = []
			for pair in sonarSplit:
				angle,distance = pair.split(":")
				sonarToAdd = {"angle": int(angle), "distance": int(distance)}
				sonar_list.append(sonarToAdd)

			if sonar_list:
				await sio.emit('sonar', sonar_list)


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