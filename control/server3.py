import socket, hashlib, base64, threading
import time
from collections import namedtuple
from functools import wraps
from threading import Timer
from threading import Thread
from functools import partial

import serial
import zlib

#import socket as telemsocket
import urllib.request
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

ser = serial.Serial('/dev/serial0', 9600)  # open front serial port
#ser.open()
ser2 =serial.Serial('/dev/ttyUSB0', 9600)  # open rear serial port 
#ser2.open()

def sendcmd(steer,speed):
	portbusy = True
	steerB = (steer).to_bytes(2, byteorder='little', signed=True) #16 bits
	speedB = (speed).to_bytes(2, byteorder='little', signed=True) #16 bits
	crcB = zlib.crc32(steerB+speedB).to_bytes(4, byteorder='little') #32 bit CRC of byte-joined command
	ser.write(steerB)
	ser.write(speedB)
	ser.write(crcB)

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


#define motor controls
def stp():
	#GPIO.output(pin_list, [0,0,0,0,0])
    sendcmd(0,0)
    print("stop")
def fwd():
        #GPIO.output(pin_list, [1,0,1,0,1])
        sendcmd(0,250)
        global lasttime
        lasttime = int(time.time())
def bck():
        #GPIO.output(pin_list, [1,1,0,1,0])
        sendcmd(0,-250)
        global lasttime
        lasttime = int(time.time())
def right(): #on the spot turn right
        #GPIO.output(pin_list, [1,0,1,1,0])
        sendcmd(350,0)
        global lasttime
        lasttime = int(time.time())
def left(): #on the spot turn left
        #GPIO.output(pin_list, [1,1,0,0,1])
        sendcmd(-350,0)
        global lasttime
        lasttime = int(time.time())
def fr(): #forward right turn
        #GPIO.output(pin_list, [1,0,1,0,0])
        sendcmd(350,200)
        global lasttime
        lasttime = int(time.time())
def fl(): #forward left turn
        #GPIO.output(pin_list, [1,0,0,0,1])
        sendcmd(-350,200)
        global lasttime
        lasttime = int(time.time())
def br(): #reverse right turn
        #GPIO.output(pin_list, [1,1,0,0,0])
        sendcmd(-350,-200)
        global lasttime
        lasttime = int(time.time())
def bl(): #reverse left turn
        #GPIO.output(pin_list, [1,0,0,1,0])
        sendcmd(350,-200)
        global lasttime
        lasttime = int(time.time())



class PyWSock:
    MAGIC = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
    MAGIC = MAGIC.encode('utf-8') #p3
    HSHAKE_RESP = "HTTP/1.1 101 Switching Protocols\r\n" + \
                "Upgrade: websocket\r\n" + \
                "Connection: Upgrade\r\n" + \
                "Sec-WebSocket-Accept: %s\r\n" + \
                "\r\n"
    HSHAKE_RESP = HSHAKE_RESP.encode('utf-8') #p3
    LOCK = threading.Lock()

    clients = []

    def recv_data (self, client):
        # as a simple server, we expect to receive:
        #    - all data at one go and one frame
        #    - one frame at a time
        #    - text protocol
        #    - no ping pong messages
        data = bytearray(client.recv(512))
        if(len(data) < 6):
            raise Exception("Error reading data")
        # FIN bit must be set to indicate end of frame
        assert(0x1 == (0xFF & data[0]) >> 7)
        # data must be a text frame
        # 0x8 (close connection) is handled with assertion failure
        assert(0x1 == (0xF & data[0]))

        # assert that data is masked
        assert(0x1 == (0xFF & data[1]) >> 7)
        datalen = (0x7F & data[1])

        #print("received data len %d" %(datalen,))

        str_data = ''
        if(datalen > 0):
            mask_key = data[2:6]
            masked_data = data[6:(6+datalen)]
            unmasked_data = [masked_data[i] ^ mask_key[i%4] for i in range(len(masked_data))]
            #str_data = str(bytearray(unmasked_data))
            ba = bytearray(unmasked_data)
            #str_data = bytes.join(b'', unmasked_data).decode('ascii')
            str_data = ba.decode()
        return str_data

    def broadcast_resp(self, data):
        # 1st byte: fin bit set. text frame bits set.
        # 2nd byte: no mask. length set in 1 byte. 
        resp = bytearray([0b10000001, len(data)])
        # append the data bytes
        for d in bytearray(data):
            resp.append(d)

        self.LOCK.acquire()
        for client in self.clients:
            try:
                client.send(resp)
            except:
                print("error sending to a client")
        self.LOCK.release()

    def parse_headers (self, data):
        headers = {}
        lines = data.splitlines()
        for l in lines:
            parts = l.split(": ", 1)
            if len(parts) == 2:
                headers[parts[0]] = parts[1]
        headers['code'] = lines[len(lines) - 1]
        return headers

    def handshake (self, client):
        # print('Handshaking...')
        data = client.recv(2048).decode('utf_8') #p3
        #data.decode('utf_8') #p3 
        headers = self.parse_headers(data)
        # print('Got headers:')
        # for k, v in headers.iteritems():
            # print(k, ':', v)

        key = headers['Sec-WebSocket-Key']
        key = key.encode('utf_8') #p3

        resp_data = self.HSHAKE_RESP % ((base64.b64encode(hashlib.sha1(key+self.MAGIC).digest()),))
        # print('Response: [%s]' % (resp_data,))
        return client.send(resp_data)

    def handle_client (self, client, addr):
        self.handshake(client)
        try:
            while 1:            
                data = self.recv_data(client)
                data_broadcast = data.encode('utf_8') #p3
                #data = data.encode('utf_8') #p3

                if data == "s":
                        print("motors stop")
                        stp() #motors go forward for 0.5s
                if data == "f":
                        print("motors forward")
                        fwd() #motors go forward for 0.5s
                if data == "b":
                        print("motors rev")
                        bck() #motors go rev for 0.5s
                if data == "l":
                        print("motors left")
                        left() #motors go left for 0.5s
                if data == "r":
                        print("motors right")
                        right() #motors go right for 0.5s
                if data == "fl":
                        print("motors forward-left")
                        fl() #motors go forward-left for 0.5s
                if data == "fr":
                        print("motors forward-right")
                        fr() #motors go forward-right for 0.5s
                if data == "bl":
                        print("motors rev-left")
                        bl() #motors go rev-left for 0.5s
                if data == "br":
                        print("motors rev-right")
                        br() #motors go rev-right for 0.5s
                self.broadcast_resp(data_broadcast)
        except Exception as e:
            print("Exception at handle_client %s" % (str(e)))
        print('Client closed: ' + str(addr))
        self.LOCK.acquire()
        self.clients.remove(client)
        self.LOCK.release()
        client.close()

    def start_server (self, port):
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', port))
        s.listen(5)
        while(1):
            print ('Waiting for connection...')
            conn, addr = s.accept()
            print ('Connection from: ' + str(addr))
            threading.Thread(target = self.handle_client, args = (conn, addr)).start()
            self.LOCK.acquire()
            self.clients.append(conn)
            self.LOCK.release()


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

ws = PyWSock()
ws.start_server(9876)

while True:
	pass

