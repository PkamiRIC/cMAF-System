# Device 2 – PLC Quick Guide (WARP2PLC)

This file contains the essential commands to operate Device 2 **on its PLC**.

SSH into the PLC:

```
ssh pi@warp2plc.local
# or
ssh pi@<DEVICE2_IP>
```

---

## 1. Project Paths (ON PLC)

```
/home/pi/projects/WARP-Devices/devices/device2
  ├── src/
  ├── config/
  ├── .venv/
  └── requirements.txt
```

---

## 2. Run Backend (Manual Mode)

```
cd ~/projects/WARP-Devices/devices/device2/src
source ../.venv/bin/activate
python -m main --config ../config/device2.yaml
```

Test:

```
http://warp2plc.local:8002/status
```

---

## 3. Run Backend (Production via systemd)

Service name: **device2.service**

```
sudo systemctl start device2.service
sudo systemctl stop device2.service
sudo systemctl restart device2.service
sudo systemctl enable device2.service
sudo systemctl status device2.service
journalctl -u device2.service -n 50 --no-pager
```

---

## 4. Update Code

```
cd ~/projects/WARP-Devices
git pull
```

If dependencies change:

```
cd devices/device2
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart device2.service
```

---

## 5. Edit Config

```
~/projects/WARP-Devices/devices/device2/config/device2.yaml
```

---

## 6. Health Check

```
curl http://localhost:8002/status
http://warp2plc.local:8002/status
```
