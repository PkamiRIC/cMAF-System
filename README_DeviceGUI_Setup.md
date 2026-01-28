# DeviceGUI_v17 Setup (DeviceGUI folder)

These steps mirror the exact process used on the Pi.  
Note: **Do NOT run `sudo apt-get update`** (omitted by request).

## Base Image Used
```
2024-07-04-raspios-bookworm-arm64-desktop-raspberry-plc-v6-20240916163624.img
```

## Package/Dependency Versions Used
From the working SD card (reference):

**OS / Python**
- Python: 3.11.2

**APT packages**
- librpiplc: 4.1.1
- python3-librpiplc: 4.0.2
- python3-pyqt5: 5.15.9+dfsg-1
- python3-pyqt5.sip: 12.11.1-1
- python3-rpi.gpio: 0.7.1~a4-1+b4
- rpi.gpio-common: 0.7.1~a4-1+b4
- python3-venv: 3.11.2-1+b1

**Pip packages**
- simple-pid: 2.0.1

## 1) Install required packages
```
sudo apt-get install -y ca-certificates curl gnupg
sudo mkdir -p /etc/apt/keyrings
sudo curl -fsSL https://apps.industrialshields.com/main/DebRepo/PublicKey.gpg -o /etc/apt/keyrings/industrialshields.gpg
echo "deb [signed-by=/etc/apt/keyrings/industrialshields.gpg] https://apps.industrialshields.com/main/DebRepo/ ./" | sudo tee /etc/apt/sources.list.d/industrialshields.list
sudo apt-get install -y librpiplc python3-librpiplc
sudo ldconfig
```

## 2) Verify librpiplc is visible
```
ldconfig -p | grep -i rpiplc
```

## 3) Install GUI dependencies
```
sudo apt-get install -y python3-pyqt5 python3-rpi.gpio
```

## 4) Install simple-pid (system python)
```
sudo /usr/bin/python3 -m pip install simple-pid --break-system-packages
```

## 5) Run the GUI
```
cd /home/pi/DeviceGUI/Old_Codes
/usr/bin/python3 DeviceGUI_v17.py
```
