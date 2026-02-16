# DNA Extraction System

Backend + UI for the DNA Extraction System PLC device.

Structure:
- `device`: FastAPI backend (live)
- `ui/warp-console`: Next.js frontend (recommended UI)

## Base Image Used
```
2024-07-04-raspios-bookworm-arm64-desktop-raspberry-plc-v6-20240916163624.img
```

## Package/Dependency Versions (reference)
From the working SD card:

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

## SD Card Setup (Device 2)
### Step 1 - Set hostname to WARP2PLC
Run on the Pi:
```
sudo hostnamectl set-hostname WARP2PLC
sudo sed -i 's/127.0.1.1.*/127.0.1.1	WARP2PLC/' /etc/hosts
sudo reboot
```
Verify after reboot:
```
hostname
```

### Step 2 - Install base packages
Run on the Pi:
```
sudo apt-get update
sudo apt-get install -y git python3-venv python3-pip
```

### Step 3 - Install Industrial Shields librpiplc (pinned method)
Run on the Pi (**do not** run `apt-get update` here):
```
sudo apt-get install -y ca-certificates curl gnupg
sudo mkdir -p /etc/apt/keyrings
sudo curl -fsSL https://apps.industrialshields.com/main/DebRepo/PublicKey.gpg -o /etc/apt/keyrings/industrialshields.gpg
echo "deb [signed-by=/etc/apt/keyrings/industrialshields.gpg] https://apps.industrialshields.com/main/DebRepo/ ./" | sudo tee /etc/apt/sources.list.d/industrialshields.list
sudo apt-get install -y librpiplc python3-librpiplc
sudo ldconfig
```
Verify:
```
python3 - <<'PY'
import librpiplc
from librpiplc import rpiplc as plc
print("librpiplc OK:", librpiplc.__file__)
print("rpiplc ok")
PY
```

### Step 4 - Install GUI dependencies
```
sudo apt-get install -y python3-pyqt5 python3-rpi.gpio
```

### Step 5 - Install simple-pid (system python)
```
sudo /usr/bin/python3 -m pip install simple-pid --break-system-packages
```

### Step 6 - Install Node.js 20.x
Run on the Pi:
```
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
node -v
npm -v
```

### Step 7 - Clone the repo
Run on the Pi:
```
cd ~
git clone https://github.com/PkamiRIC/cMAF-System.git
```

### Step 8 - Fix SSH host key warning after reflash
If SSH says the host key changed (new SD card), run on your PC:
```
ssh-keygen -R 10.0.46.111
ssh-keygen -R WARP2PLC
```
Then reconnect:
```
ssh pi@10.0.46.111
ssh pi@WARP2PLC
```

### Step 9 - Ensure Wi-Fi auto-connect (NetworkManager)
Run on the Pi:
```
nmcli connection show
sudo nmcli connection modify "CyRIC-INT" connection.autoconnect yes
sudo nmcli connection modify "CyRIC-INT" connection.autoconnect-priority 10
```
(Optional) remove duplicate old connections if needed:
```
nmcli connection delete "<UUID_OR_NAME_OF_OLD_DUPLICATE>"
```

### Step 9.1 - Confirm Debian/Raspberry Pi OS version
Run on the Pi:
```
cat /etc/os-release
uname -a
```

### Step 9.2 - Ensure Ethernet auto-connect too
Run on the Pi (adjust name if yours differs):
```
nmcli connection show
sudo nmcli connection modify "Wired connection 1" connection.autoconnect yes
sudo nmcli connection modify "Wired connection 1" connection.autoconnect-priority 20
```
Notes:
- Ethernet typically uses DHCP by default (same as Wi-Fi).
- If you use a different wired profile name, replace it accordingly.

### Step 9.3 - Install + enable Tailscale (remote access)
Run on the Pi:
```
curl -fsSL https://tailscale.com/install.sh | sudo sh
sudo systemctl enable --now tailscaled
sudo tailscale up
```
If you want SSH over Tailscale:
```
sudo tailscale up --ssh
```
Check status:
```
tailscale status
tailscale ip -4
```
(Might need to authorize via the owner Tailscale account)

Notes:
- Share the device using a link or email.
- User must be logged in using Tailscale on PC or phone.
- After sharing, SSH and RealVNC are accessible using the Tailscale IP.
### Step 10 - Create venv and install backend dependencies
Run on the Pi:
```
cd ~/cMAF-System/device
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
Important (PLC I/O requires librpiplc): if `/home/pi/cMAF-System/device/.venv/bin/python` cannot import `librpiplc`,
recreate the venv with system packages:
```
cd ~/cMAF-System/device
mv .venv .venv.bak.$(date +%Y%m%d-%H%M%S)
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -r requirements.txt
pip install simple-pid
```
Revert if needed:
```
cd ~/cMAF-System/device
rm -rf .venv
mv .venv.bak.<TIMESTAMP> .venv
```
If the backend fails with `ModuleNotFoundError: simple_pid`, install it in the venv:
```
pip install simple-pid
```

### Step 11 - Create device2 config
Run on the Pi:
```
cd ~/cMAF-System/device/config
cp device3.yaml device2.yaml
```
### Step 11.1 - Create stable flow meter device name (prevents ttyUSB0/ttyUSB1 flips)
Run on the Pi:
```
# Find USB ID for the SCC1 cable (run with current ttyUSB0/ttyUSB1)
udevadm info -a -n /dev/ttyUSB0 | grep -m1 -E 'idVendor|idProduct|serial'

# Create udev rule for a stable name
sudo tee /etc/udev/rules.d/99-scc1.rules >/dev/null <<'EOF'
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", SYMLINK+="ttySCC1"
EOF

# Reload rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```
Verify:
```
ls -l /dev/ttySCC1
```
Edit `device2.yaml` and set:
- `device_id: "device2"`
- `network.api_port: 8002`
- `auth.advanced_controls_password: "<choose-a-strong-password>"`
- `relay.address: 1`
- `vertical_axis` min/max to 0..25
- `flow_sensor.port: /dev/ttySCC1`
- `temperature` pins (Q0.6/I0.11/8)

### Step 12 - Create backend systemd service
Run on the Pi:
```
sudo tee /etc/systemd/system/device2.service > /dev/null <<'EOF'
[Unit]
Description=cMAF Device 2 Backend (FastAPI)
After=network-online.target
Wants=network-online.target

[Service]
User=pi
WorkingDirectory=/home/pi/cMAF-System/device
ExecStart=/home/pi/cMAF-System/device/.venv/bin/python -m src.main --config config/device2.yaml
Restart=on-failure
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now device2.service
sudo systemctl status device2.service --no-pager
```
Note: Ensure the service uses `config/device2.yaml` (not `device3.yaml`).

### Step 13 - Build Next.js UI on the Pi
Run on the Pi:
```
cd /home/pi/cMAF-System/ui/warp-console
npm install
npm run build
```

### Step 14 - Optional: build on PC and copy to the Pi (if Pi build fails)
Run on your PC:
```
cd C:/Users/p.kamintzis/OneDrive - Cy.R.I.C. Cyprus Research and Innovation Center Ltd/Work/WARP/cMAF-System/ui/warp-console
npm install
npm run build
```
Copy the build to the Pi:
```
scp -r "C:/Users/p.kamintzis/OneDrive - Cy.R.I.C. Cyprus Research and Innovation Center Ltd/Work/WARP/cMAF-System/ui/warp-console/.next" pi@10.0.46.111:/home/pi/cMAF-System/ui/warp-console/
```
Verify on the Pi (must exist before starting the UI service):
```
ls -ld /home/pi/cMAF-System/ui/warp-console/.next
```
Then install UI runtime deps on the Pi:
```
cd /home/pi/cMAF-System/ui/warp-console
npm install --omit=dev
```
Tip (if install is slow): add `--no-audit --no-fund`.

### Step 15 - Create UI systemd service (port 3002)
Run on the Pi:
```
sudo tee /etc/systemd/system/warp-ui.service > /dev/null <<'EOF'
[Unit]
Description=cMAF UI (Next.js)
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/pi/cMAF-System/ui/warp-console
Restart=on-failure
Environment=NODE_ENV=production
Environment=PATH=/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/bin/npm run start -- --hostname 0.0.0.0 --port 3002
User=pi
Group=pi

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now warp-ui.service
sudo systemctl status warp-ui.service --no-pager
```
Note: If the service fails with status=127, make sure `npm` is in PATH or use the absolute path from `which npm`.

## Notes
- UI API base defaults to the same host on port 8002.
- Use `NEXT_PUBLIC_API_BASE` in `ui/warp-console/.env.local` only if you must override.

## Additional Field Notes (USB + TEC + LAM Driver)

These are practical notes specific to the current working Device 2 setup.

### Stable USB Assignment for Flow + TEC
Do not use `/dev/ttyUSB0`/`/dev/ttyUSB1` directly because order can swap after reboot/replug.

Check IDs:
```bash
ls -l /dev/serial/by-id/
```

Expected devices:
- Flow meter: `/dev/serial/by-id/usb-Sensirion_AG_Sensirion_RS485-USB_Cable_FT7TV0U4-if00-port0`
- TEC: `/dev/serial/by-id/usb-FTDI_FT230X_Basic_UART_DP05MXL4-if00-port0`

Set in `device/config/device2.yaml`:
```yaml
flow_sensor:
  port: "/dev/serial/by-id/usb-Sensirion_AG_Sensirion_RS485-USB_Cable_FT7TV0U4-if00-port0"

temperature:
  tec_port: "/dev/serial/by-id/usb-FTDI_FT230X_Basic_UART_DP05MXL4-if00-port0"
  tec_address: 2
  tec_channel: 1
  tec_baudrate: 57600
```

Optional custom aliases via udev:
```bash
sudo tee /etc/udev/rules.d/99-cmaf-serial.rules > /dev/null <<'EOF'
SUBSYSTEM=="tty", ENV{ID_SERIAL_SHORT}=="FT7TV0U4", SYMLINK+="ttyFLOW"
SUBSYSTEM=="tty", ENV{ID_SERIAL_SHORT}=="DP05MXL4", SYMLINK+="ttyTEC"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger
ls -l /dev/ttyFLOW /dev/ttyTEC
```

### TEC Behavior Notes
- Applying target while Peltier is OFF stores the target in software state.
- Hardware write occurs when Peltier is turned ON.
- Sequence temperature steps are non-blocking (timeouts log warnings and sequence continues).

### LAM Driver Digital Pin + RS485 Direction Command
Peristaltic direction uses both PLC pin and RS485 external driver.

Current mapping:
- PLC direction pin: `Q0.2`
- RS485 command register: `0xA4F7` (Modbus function `0x06`)
- Forward/CW value: `0x0081`
- Reverse/CCW value: `0x0001`

Backend API examples:
```bash
# Forward/CW
curl -X POST http://127.0.0.1:8002/peristaltic/direction \
  -H "Content-Type: application/json" -d '{"forward": true}'

# Reverse/CCW
curl -X POST http://127.0.0.1:8002/peristaltic/direction \
  -H "Content-Type: application/json" -d '{"forward": false}'
```
