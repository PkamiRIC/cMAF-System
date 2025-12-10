# TROUBLESHOOTING.md – WARP Devices

Common issues and fixes for PLC backends, systemd services, virtual environments, dashboard errors, networking, SSH, and build problems.

---

# 1. Systemd Service Fails to Start

### Symptom:
```
Active: failed (Result: exit-code)
```

### Causes & Fixes:

1. **ExecStart path is wrong or truncated**  
   - Ensure full line:
     ```
     ExecStart=/home/pi/projects/WARP-Devices/devices/deviceX/.venv/bin/python -m src.main --config config/deviceX.yaml
     ```

2. **Virtual environment missing**  
   Recreate:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Syntax error in Python code**  
   Check logs:
   ```
   journalctl -u deviceX.service -n 50 --no-pager
   ```

---

# 2. “Invalid HTTP request received” in logs

Occurs when a browser auto-probes ports.  
Safe to ignore unless crashing.

---

# 3. Dashboard shows:  
**“NetworkError when attempting to fetch resource.”**

### Fixes:
- Backend service not running → check systemd
- Wrong dashboard URL → check `.env` file
- Wrong port number → check `deviceX.yaml`
- CORS issues (rare) → adjust fetch URL

Test manually:
```
http://warp3plc.local:8003/status
```

---

# 4. Cannot Activate Virtual Environment

```
externally-managed-environment
```

### Fix:
Install full Python:
```
sudo apt install python3-full python3-venv python3-pip
```

If disk full:
```
sudo apt clean
sudo apt autoremove
```

---

# 5. SSH Fails / VSCode Server Looping

Fixes:
1. Remove server:
   ```
   rm -rf ~/.vscode-server
   ```
2. Retry SSH  
3. Ensure PLC has space:
   ```
   df -h
   ```

---

# 6. Tailwind / PostCSS Errors in Dashboard

Fix:
```
npm install -D @tailwindcss/postcss
```

Update `postcss.config.js` accordingly.

---

# 7. `ImportError: attempted relative import beyond top-level package`

Fix:
- Use **absolute imports only**
- Update `src/main.py` imports to:
  ```
  from domain.controller import DeviceController
  ```

---

# 8. Port Not Accessible

Check if backend running:
```
sudo systemctl status deviceX.service
```

Check if port open:
```
ss -tulpn | grep 8003
```

Restart service:
```
sudo systemctl restart deviceX.service
```

---

# 9. Disk Full Errors (“No space left on device”)

Clean apt cache:
```
sudo apt clean
```

Remove old vscode servers:
```
rm -rf ~/.vscode-server
```

Check big folders:
```
du -sh *
```

---

# 10. Update This File When:

- New recurring error appears  
- New troubleshooting category needed  
- API or dashboard changes introduce new failure modes  
