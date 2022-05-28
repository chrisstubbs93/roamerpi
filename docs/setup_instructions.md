# RoamerPi

- ✨low quality ✨setup instructions

## raspi-config

```sh
sudo raspi-config
```

- enable legacy camera support
- enable ssh
- enable vnc
- enable i2c
- disable serial shell
- join wifi
- enable composite output
- set vnc res to 720x480
- in Display Options - disable Screen Blanking

- Reboot YES

## for lite OS only, install missing stuff:
```sh
sudo apt-get install git
sudo apt install python3-pip
sudo apt-get install python3-numpy
python3 -m pip install pyserial
```

## get code
```sh
git clone https://[INSERT CREDS]@github.com/chrisstubbs93/roamerpi.git
cd roamerpi/
cp pull.sh.template pull.sh
sudo nano pull.sh (insert creds)
```

## set permissions
```sh
chmod 755 permissions.sh
./permissions.sh
```

## Neopixel setup shiz
At this time, Blinka requires Python version 3.7 or later, which means you will need to at least be running Raspberry Pi OS Bullseye.
```
sudo apt-get update
sudo apt-get upgrade

sudo pip3 install --upgrade setuptools
sudo pip3 install --upgrade adafruit-python-shell

cd leds
sudo python3 raspi-blinka.py
Reboot: Y

sudo pip3 install rpi_ws281x adafruit-circuitpython-neopixel

```
To stop audio PWM clashing with neopixel create a file /etc/modprobe.d/snd-blacklist.conf with:
```
sudo nano /etc/modprobe.d/snd-blacklist.conf
```
add the following:
```
blacklist snd_bcm2835
```

```
sudo reboot
```

## install python libs
Needs python >3.7 probably
```sh
sudo python3 -m pip install --upgrade --force-reinstall python-socketio
sudo python3 -m pip install --upgrade --force-reinstall aiohttp
sudo python3 -m pip install --upgrade --force-reinstall git+https://github.com/inmcm/micropyGPS.git
sudo python3 -m pip install --upgrade --force-reinstall shapely
sudo apt-get install libgeos-dev
```

## dyndns

```sh
cd
mkdir dynudns
cd dynudns
sudo nano dynu.sh
```
put this in dynu.sh:
```sh
echo url="https://api.dynu.com/nic/update?username=domlinson&password=creds" | curl -k -o ~/dynudns/dynu.log -K -
```

```sh
sudo chmod 700 dynu.sh
```

## cron
```sh
crontab -e
choose 1 - nano
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
Edit the file /boot/config.txt.
```sh
sudo nano /boot/config.txt
```
Add this to the end:
```sh
dtoverlay=disable-bt
```
Disable Services and reboot
```sh
sudo systemctl disable hciuart.service
sudo systemctl disable bluetooth.service
sudo reboot
```

## Wifi (TP Link Archer T4U plus v3)
From https://github.com/morrownr/88x2bu-20210702
```
#this takes an absolute age:
sudo apt install -y raspberrypi-kernel-headers bc build-essential dkms git

mkdir -p ~/wifisrc
cd ~/wifisrc
git clone https://github.com/morrownr/88x2bu-20210702.git
cd ~/wifisrc/88x2bu-20210702
./ARM_RPI.sh
sudo ./install-driver.sh

#reboot the pi
#configure ssid/pass
sudo raspi-config
#reboot again
```

## disable built in wifi
Edit the file /boot/config.txt.
```sh
sudo nano /boot/config.txt
```
Add this to the end below dtoverlay=disable-bt:
```sh
dtoverlay=disable-wifi
```

## video things

https://github.com/richprze/picam_livestream/blob/master/README.md
https://stackoverflow.com/questions/50492044/how-to-install-heroku-cli-on-raspberry-pi-3

u: admin@roamer.fun
p: secret! 

Do it all in the home directory, the paths are hardcoded. I initially did it in a folder called vid (and the install script worked), then moved it out to the home directory.
Delete the old cronjob if re-running setup.
```sh
cd /home/pi
wget https://cli-assets.heroku.com/branches/stable/heroku-linux-arm.tar.gz
mkdir -p /usr/local/lib /usr/local/bin
sudo tar -xvzf heroku-linux-arm.tar.gz -C /usr/local/lib
sudo ln -s /usr/local/lib/heroku/bin/heroku /usr/local/bin/heroku
heroku version
sudo heroku update (might need to run more than once)

sudo apt-get install -y python3-pip git ffmpeg libffi-dev nodejs
sudo pip3 install bcrypt
git clone https://github.com/richprze/picam_livestream.git
sudo bash picam_livestream/setup.sh (this may/may not fail and youll need to copy out the commands to run as sudo manually)
```
If required: Edit the file /boot/config.txt.

Set the provided URL on the server in settings.php - $videoUrl.



## The list goes on...
Disable IPV6?
