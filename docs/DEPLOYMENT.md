# DEPLOYMENT.md – Deployment Guide for WARP Devices

This document describes how to deploy backend updates (FastAPI) and dashboard updates (React) to all WARP Devices.  
Deployment includes:  
- Updating code on PLCs  
- Restarting systemd services  
- Managing environment variables  
- Dashboard production build and hosting options  

Commands are tagged as:  
- **[PC]** → Windows PowerShell  
- **[PLC]** → Raspberry PLC terminal (via SSH)

---

# 1. Backend Deployment (FastAPI on PLC)

Each device backend runs as a systemd service:

- device1 → `device1.service`
- device2 → `device2.service`
- device3 → `device3.service`

Backend code is stored on the PLC under:

```
/home/pi/projects/WARP-Devices/devices/deviceX
```

---

## 1.1 Pull latest code from GitHub (ON PLC)

```
[PLC]
cd ~/projects/WARP-Devices
git pull
```

If any Python dependencies changed:

```
cd devices/deviceX
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 1.2 Restart backend service (ON PLC)

```
sudo systemctl restart deviceX.service
sudo systemctl status deviceX.service
```

You want:

```
Active: active (running)
```

---

## 1.3 Verify API status

```
curl http://localhost:<PORT>/status
```

From PC:

```
http://<hostname>.local:<PORT>/status
```

Example:

```
http://warp3plc.local:8003/status
```

---

# 2. Dashboard Deployment (React + Vite)

The dashboard is normally run in **development mode**:

```
[PC]
npm run dev
```

For production deployment, you may need to:

- Host it on a PLC (static server)
- Host it on a central computer
- Host it on a remote server (using Tailscale)

---

## 2.1 Production build (ON PC)

```
[PC]
cd dashboard
npm install
npm run build
```

Output is stored in:

```
dashboard/dist/
```

This folder contains static HTML/CSS/JS files.

---

## 2.2 Serving Dashboard Locally (simple method)

Run:

```
npm run dev
```

Access:

```
http://localhost:5173
```

NOT suitable for real deployment—only for loading UI from the developer machine.

---

# 3. Deploying Dashboard to PLC (Optional)

One PLC can host the dashboard for all devices.

Copies build files to PLC:

```
[PC]
scp -r dashboard/dist/* pi@warp3plc.local:~/dashboard/
```

Install a simple web server (example: Nginx):

```
[PLC]
sudo apt install -y nginx
sudo mkdir -p /var/www/warp-dashboard
sudo cp -r ~/dashboard/* /var/www/warp-dashboard
```

Configure Nginx:

```
sudo nano /etc/nginx/sites-available/warp-dashboard
```

Add:

```
server {
    listen 80;
    server_name warp3plc.local;

    root /var/www/warp-dashboard;
    index index.html;
}
```

Enable:

```
sudo ln -s /etc/nginx/sites-available/warp-dashboard /etc/nginx/sites-enabled/
sudo systemctl restart nginx
```

Dashboard is now available at:

```
http://warp3plc.local
```

---

# 4. Updating Dashboard After Code Changes

On PC:

```
cd dashboard
npm run build
```

Upload again:

```
scp -r dashboard/dist/* pi@warp3plc.local:~/dashboard/
sudo cp -r ~/dashboard/* /var/www/warp-dashboard
sudo systemctl restart nginx
```

---

# 5. Tailscale Deployment (Remote Access)

Install on PLC:

```
[PLC]
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Once connected:

- PLC receives a **Tailscale IP** (100.x.x.x)
- Dashboard and APIs become accessible from anywhere:
  - `http://100.x.x.x:8003/status`
  - `http://100.x.x.x` (dashboard hosted on PLC)

Make sure firewall rules allow these ports.

---

# 6. Remote Backend Deployment (through Tailscale)

Once PLC is on Tailscale, you can deploy from anywhere:

```
ssh pi@100.x.x.x
cd ~/projects/WARP-Devices
git pull
sudo systemctl restart device3.service
```

This enables remote maintenance and updates for international installations.

---

# 7. Multi-Device Dashboard Deployment

To support devices 1–3 simultaneously:

Update dashboard `.env`:

```
VITE_DEVICE1_URL=http://warp1plc.local:8001
VITE_DEVICE2_URL=http://warp2plc.local:8002
VITE_DEVICE3_URL=http://warp3plc.local:8003
```

Run:

```
npm run build
```

Deploy as usual.

---

# 8. Deployment Checklist

### Backend
- [ ] Code updated with `git pull`
- [ ] Dependencies installed
- [ ] systemd service restarted
- [ ] API reachable

### Dashboard
- [ ] `.env` updated
- [ ] Build completed
- [ ] Static files deployed
- [ ] Browser cache cleared

### Remote Access
- [ ] Tailscale connected
- [ ] Firewall open for ports 80 + 8001–8003
- [ ] Remote fetch test OK

---

# 9. When to Update This File

Update `DEPLOYMENT.md` whenever:

- Deployment instructions change  
- Hosting location changes (PC → PLC → server)  
- Ports change  
- Tailscale setup changes  
- Static file paths change  
- Dashboard build process changes  
- Systemd service names or logic changes  

This file ensures deployments are **repeatable and consistent** across all environments.
