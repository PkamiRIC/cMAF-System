# Device 1 PLC Quick Guide (WARP1PLC)

SSH into the PLC:
```
ssh pi@warp1plc.local
# or
ssh pi@<DEVICE1_IP>
```

## Project Paths (on PLC)
```
/home/pi/projects/WARP-Devices/devices/device1
  src/
  config/
  .venv/
  requirements.txt
```

## Run Backend (manual)
```
cd ~/projects/WARP-Devices/devices/device1/src
source ../.venv/bin/activate
python -m main --config ../config/device1.yaml
```
Test: http://warp1plc.local:8001/status

## systemd (production)
Service: device1.service
```
sudo systemctl start|stop|restart device1.service
sudo systemctl enable device1.service
sudo systemctl status device1.service
journalctl -u device1.service -n 50 --no-pager
```

## Update code / deps
```
cd ~/projects/WARP-Devices && git pull
cd devices/device1 && source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart device1.service
```

## Config
Edit: ~/projects/WARP-Devices/devices/device1/config/device1.yaml

## Health check
```
curl http://localhost:8001/status
curl http://warp1plc.local:8001/status
```
