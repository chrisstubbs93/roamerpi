# RoamerPi

- ✨low quality ✨setup instructions


## raspi-config

```sh
raspi-config
```

- enable CSI camera port
- enable ssh
- enable vnc
- disable serial shell
- join wifi

## for lite OS only, install missing stuff:
```sh
sudo apt-get install git
sudo apt install python3-pip
sudo apt-get install python3-numpy
python3 -m pip install pyserial
```

## get code
```sh
git clone https://creds@github.com/chrisstubbs93/roamerpi.git
cd roamerpi/
cp pull.sh.template pull.sh
nano pull.sh (insert creds)
```

## set permissions
```sh
chmod 755 permissions.sh
./permissions.sh
```


## install python libs
Needs python >3.7 probably
```sh
python3 -m pip install python-socketio
python3 -m pip install aiohttp
pip install git+https://github.com/inmcm/micropyGPS.git
pip install shapely
sudo apt-get install libgeos-dev
```

## dyndns

```sh
cd
mkdir dynudns
cd dynudns
nano dynu.sh
```
put this in dynu.sh:
```sh
echo url="https://api.dynu.com/nic/update?username=domlinson&password=creds" | curl -k -o ~/dynudns/dynu.log -K -
```

```sh
chmod 700 dynu.sh
```

## cron
```sh
crontab -e
```
bang this in:
```sh
@reboot /home/pi/roamerpi/startup.sh # JOB_ID_1
*/5 * * * * ~/dynudns/dynu.sh >/dev/null 2>&1
```



## ssl cert
```sh
sudo apt-get install certbot
```
forward ports 80 and 443
```sh
sudo certbot certonly --standalone -d bigclamps.loseyourip.com -d www.bigclamps.loseyourip.com
sudo chown pi -R /etc/letsencrypt/
```


## disable bt for serial
Edit the file /boot/config.txt and add the following line at the end of it.
```sh
dtoverlay=pi3-disable-bt
```
Disable HCIUart service and reboot
```sh
sudo systemctl disable hciuart.service
sudo reboot
```
I also disabled the bt service on the pi zero w but I don't think it was requred?
```sh
systemctl disable bluetooth.service
```

## Neopixel setup shiz
At this time, Blinka requires Python version 3.7 or later, which means you will need to at least be running Raspberry Pi OS Bullseye.
```
sudo apt-get update
sudo apt-get upgrade
sudo apt-get install python3-pip
sudo pip3 install --upgrade setuptools

sudo pip3 install --upgrade adafruit-python-shell
wget https://raw.githubusercontent.com/adafruit/Raspberry-Pi-Installer-Scripts/master/raspi-blinka.py
sudo python3 raspi-blinka.py

sudo pip3 install rpi_ws281x adafruit-circuitpython-neopixel
sudo python3 -m pip install --force-reinstall adafruit-blinka
```
To stop audio PWM clashing with neopixel create a file /etc/modprobe.d/snd-blacklist.conf with:
```
blacklist snd_bcm2835
```


## The list goes on...
Disable IPV6?
