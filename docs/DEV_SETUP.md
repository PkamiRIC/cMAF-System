# Developer Setup Guide (DEV_SETUP.md)

This document explains how to set up a development environment for the WARP Devices monorepo on a **Windows PC**. It is intended for developers working on:

- The FastAPI backend for each PLC  
- The React + Vite + Tailwind dashboard  
- Any future service or tool within the repo  

Commands are marked as:
- **[PC]** → Windows PowerShell  
- **[PLC]** → Raspberry PLC terminal (via SSH)

---

# 1. Clone the Repository (PC)

```
[PC]
git clone https://github.com/PkamiRIC/WARP-Devices.git
cd WARP-Devices
```

Recommended folder structure on your PC:

```
C:/Users/<you>/OneDrive/.../WARP/warp-devices
```

Always use quotes because OneDrive paths contain spaces:

```
[PC]
cd "C:/Users/.../warp-devices"
```

---

# 2. Install Required Tools (PC)

## 2.1 Node.js (for dashboard)
Download LTS from:

https://nodejs.org

Verify:

```
[PC]
node -v
npm -v
```

If npm fails due to execution policy:

```
[PC]
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
```

---

# 3. Dashboard Setup (Vite + React + Tailwind)

The dashboard lives in:

```
warp-devices/dashboard/
```

## 3.1 Install dependencies

```
[PC]
cd dashboard
npm install
```

## 3.2 Start development server

```
[PC]
npm run dev
```

Dashboard opens at:

```
http://localhost:5173
```

## 3.3 Environment variables

Create:

```
warp-devices/dashboard/.env
```

Example:

```
VITE_DEVICE1_URL=http://warp1plc.local:8001
VITE_DEVICE2_URL=http://warp2plc.local:8002
VITE_DEVICE3_URL=http://warp3plc.local:8003
```

Restart Vite after changing `.env`.

---

# 4. Backend Setup (FastAPI)

Each device backend is located under:

```
warp-devices/devices/deviceX/
```

Example:

```
devices/device3/
```

## 4.1 Virtual environment for backend

On the PLC:

```
[PLC]
cd ~/projects/WARP-Devices/devices/device3
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4.2 Running backend manually (dev mode)

```
[PLC]
cd devices/device3/src
python -m main --config ../config/device3.yaml
```

API is available at:

```
http://warp3plc.local:8003/status
```

---

# 5. Systemd Deployment (Production)

Once backend works manually, deploy via systemd.

Service file:

```
/etc/systemd/system/device3.service
```

Reload + enable:

```
[PLC]
sudo systemctl daemon-reload
sudo systemctl enable device3.service
sudo systemctl restart device3.service
```

Check status:

```
sudo systemctl status device3.service
```

---

# 6. Common Development Workflow

## 6.1 Modify backend code

```
[PC]
# Edit Python files
git add .
git commit -m "Update backend logic"
git push
```

Update PLC:

```
[PLC]
cd ~/projects/WARP-Devices
git pull
sudo systemctl restart device3.service
```

---

## 6.2 Modify dashboard UI

```
[PC]
cd dashboard
npm run dev
```

Code updates appear instantly in browser.

---

# 7. Folder Conventions & Rules

- All devices follow folder:  
  `devices/deviceX/src`, `config`, `.venv`
- Every device gets its own port (8001, 8002, 8003)
- Every device gets a systemd service named `deviceX.service`
- Dashboard uses `.env` to know each device URL
- Avoid creating global venvs—each device has its own

---

# 8. When You Add a New Device

1. Copy `devices/device3` → `devices/device4`
2. Change:
   - Folder name  
   - Config YAML  
   - API port  
   - systemd service  
3. Add new env variable in dashboard
4. Add new device card in React UI
5. Push to GitHub and pull on PLC

---

# 9. When to Update This File

Update DEV_SETUP.md whenever:

- Installation steps change  
- Folder structure changes  
- Backend or dashboard setup changes  
- New devices or services are added  
- System requirements change  

This file is meant to be **kept in sync** with the architecture.

