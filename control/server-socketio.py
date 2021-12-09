import serial, struct, time # for hoverboard comms
import urllib.request
from aiohttp import web
import socketio, ssl, asyncio, logging
import numpy

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
	:param steer: -1000...1000	:param speed: -1000...1000	:
	'''
	if speed > 0:
		speed = int((numpy.clip(100,-100,speed)/100.0)*maxfwdspeed)
	else:
		speed = int((numpy.clip(100,-100,speed)/100.0)*maxrevspeed)
	steer = int((numpy.clip(100,-100,steer)*steerauth*(1+((speedsteercomp-1)*abs(speed)/100))))

	portbusy = True
	startB = bytes.fromhex('ABCD')[::-1] # lower byte first
	steerB = struct.pack('h', steer)
	speedB = struct.pack('h', speed)
	crcB = bytes(a^b^c for (a, b, c) in zip(startB, steerB, speedB))
	ser.write(startB+steerB+speedB+crcB)
	if fourwd:
		ser2.write(startB+steerB+speedB+crcB)
	portbusy = False

#define motor controls
def stp():
	sendcmd(0,0)
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

## create a new Async Socket IO Server
sio = socketio.AsyncServer(cors_allowed_origins='*')
ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
ssl_context.load_cert_chain('/etc/letsencrypt/live/bigclamps.loseyourip.com/fullchain.pem', '/etc/letsencrypt/live/bigclamps.loseyourip.com/privkey.pem')

async def init():
	app = web.Application()
	sio.attach(app)
	return app

def main():
	logging.basicConfig(level=logging.DEBUG)
	loop = asyncio.get_event_loop()
	app = loop.run_until_complete(init()) #init sio in the loop

	loop.create_task(temeletry()) #add background task
	loop.create_task(timeoutstop()) #add background task

	web.run_app(app, port=9876, ssl_context=ssl_context, loop=loop) #run sio in the loop

###create asyncio background tasks here###
async def temeletry():
	while True:
		await asyncio.sleep(1)
		if portbusy == False:
			feedback = ser.read_all()
			#print(feedback)
			if feedback:
				cmd1, cmd2, speedR_meas, speedL_meas, batVoltage, boardTemp, cmdLed = struct.unpack('<hhhhhhH', feedback[2:16])
				print(f'cmd1: {cmd1}, cmd2: {cmd2}, speedR_meas: {speedR_meas}, speedL_meas: {speedL_meas}, batVoltage: {batVoltage}, boardTemp: {boardTemp}, cmdLed: {cmdLed}')	
				await sio.emit('telemetry', {"cmd1": cmd1, "cmd2": cmd2, "speedR_meas": speedR_meas, "speedL_meas": speedL_meas, "batVoltage": batVoltage, "boardTemp": boardTemp, "cmdLed": cmdLed})
async def timeoutstop():
	while True:
		await asyncio.sleep(0.5)
		try:
			global lasttime
			if (int(time.time())>=int(lasttime+2)):
				print("----Timeout!!---- Lasttime:" + str(lasttime) + " Now:" + str(int(time.time())) + "----Timeout!!----")
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