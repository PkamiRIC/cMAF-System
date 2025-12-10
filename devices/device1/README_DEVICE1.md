# Device 1 – PLC Quick Guide (WARP1PLC)

This file contains the essential commands to operate Device 1 **on its PLC**.

SSH into the PLC:

```
ssh pi@warp1plc.local
# or
ssh pi@<DEVICE1_IP>
```

---

## 1. Project Paths (ON PLC)

```
/home/pi/projects/WARP-Devices/devices/device1
  ├── src/
  ├── config/
  ├── .venv/
  └── requirements.txt
```

---

## 2. Run Backend (Manual Mode)

```
cd ~/projects/WARP-Devices/devices/device1/src
source ../.venv/bin/activate
python -m main --config ../config/device1.yaml
```

Test:

```
http://warp1plc.local:8001/status
```

---

## 3. Run Backend (Production via systemd)

Service name: **device1.service**

```
sudo systemctl start device1.service
sudo systemctl stop device1.service
sudo systemctl restart device1.service
sudo systemctl enable device1.service
sudo systemctl status device1.service
journalctl -u device1.service -n 50 --no-pager
```

---

## 4. Update Code

```
cd ~/projects/WARP-Devices
git pull
```

If dependencies change:

```
cd devices/device1
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart device1.service
```

---

## 5. Edit Config

```
~/projects/WARP-Devices/devices/device1/config/device1.yaml
```

---

## 6. Health Check

```
curl http://localhost:8001/status
http://warp1plc.local:8001/status
```
