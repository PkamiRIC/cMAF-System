# Device 2 PLC Quick Guide (WARP2PLC)

SSH into the PLC:
```
ssh pi@warp2plc.local
# or
ssh pi@<DEVICE2_IP>
```

## Project Paths (on PLC)
```
/home/pi/projects/WARP-Devices/devices/device2
  src/
  config/
  .venv/
  requirements.txt
```

## Run Backend (manual)
```
cd ~/projects/WARP-Devices/devices/device2/src
source ../.venv/bin/activate
python -m main --config ../config/device2.yaml
```
Test: http://warp2plc.local:8002/status

## systemd (production)
Service: device2.service
```
sudo systemctl start|stop|restart device2.service
sudo systemctl enable device2.service
sudo systemctl status device2.service
journalctl -u device2.service -n 50 --no-pager
```

## Update code / deps
```
cd ~/projects/WARP-Devices && git pull
cd devices/device2 && source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart device2.service
```

## Config
Edit: ~/projects/WARP-Devices/devices/device2/config/device2.yaml

## Health check
```
curl http://localhost:8002/status
curl http://warp2plc.local:8002/status
```
