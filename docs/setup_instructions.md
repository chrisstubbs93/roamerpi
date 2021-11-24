# RoamerPi

- ✨low qualtiy ✨setup instructions


## raspi-config

```sh
raspi-config
```

- enable CSI camera port
- enable ssh
- enable vnc
- disable serial shell
- join wifi

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



## The list goes on...
Disable IPV6?
