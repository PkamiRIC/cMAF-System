# GIT_WORKFLOW.md – WARP Devices Git Workflow Guide

This document defines the **official Git workflow** for the WARP-Devices monorepo.  
It ensures consistent commits, safe deployments, and clean collaboration — even when multiple devices and backends change at different times.

This workflow is optimized for:
- Rapid backend iteration  
- Frequent deployments to PLCs  
- Occasional dashboard updates  
- Single‑developer or small‑team environments  
- Preventing accidental breakage of deployed devices  

---

# 1. Branch Structure

We use a **simple, stable model**:

## 1.1 main (Protected)
- Always deployable  
- Devices abroad **must always pull from main**  
- No direct commits unless documentation‑only  

## 1.2 Feature branches
Naming convention:

```
feature/<area>-<what-you-are-changing>
```

Examples:

```
feature/device3-concentration-update
feature/dashboard-new-layout
feature/systemd-cleanup
feature/device2-sensor-fix
```

Create a new branch:

```
git checkout -b feature/device3-clean-fix
```

---

# 2. Commit Rules

## 2.1 Commit Format
Use:

```
<scope>: <summary>
```

Scopes:
- device1  
- device2  
- device3  
- dashboard  
- docs  
- infra  
- api  
- systemd  

Examples:

```
device3: improved clean_1 sequence timing
dashboard: added polling interval input
docs: updated DEV_SETUP for new instructions
api: added calibration endpoint
```

## 2.2 Commit Frequently
Small commits, not huge ones.

---

# 3. Merging Into main

Before merging:

1. Test backend locally on PC (if possible)  
2. Test backend manually on PLC  
3. Run:

```
sudo systemctl restart deviceX.service
sudo systemctl status deviceX.service
```

If everything works:

Merge feature branch:

```
git checkout main
git merge feature/device3-clean-fix
git push
```

---

# 4. Deployment Workflow (PLC)

When deploying to a PLC:

```
ssh pi@warp3plc.local
cd ~/projects/WARP-Devices
git pull
cd devices/device3
source .venv/bin/activate
pip install -r requirements.txt   # only if changed
sudo systemctl restart device3.service
sudo systemctl status device3.service
```

---

# 5. Dashboard Workflow

## 5.1 During development

```
cd dashboard
npm run dev
```

## 5.2 Building production version

```
npm run build
```

Upload to PLC if needed:

```
scp -r dist/* pi@warp3plc.local:~/dashboard/
```

---

# 6. Tagging Versions

Tagging is optional but **highly recommended** before shipping devices abroad.

Examples:

```
git tag backend-v1.3.0
git tag dashboard-d1.2.0
git push --tags
```

Use combined tag:

```
git tag release-2025-12-10
git push --tags
```

---

# 7. Updating Documentation When Code Changes

If you change:
- API → update API_REFERENCE.md  
- IO usage → update IO_MAP_DEVICEX.md  
- systemd → update SYSTEMD.md  
- folder structure → update README.md + DEV_SETUP.md  
- deployment workflow → update DEPLOYMENT.md  

Use the dependency map:

```
docs/DOC_DEPENDENCY_MAP.md
```

---

# 8. Hotfix Workflow

If a device abroad needs an emergency patch:

1. Create branch:
   ```
   git checkout -b hotfix/device3-sensor-bug
   ```
2. Patch code on PC.  
3. Push branch.  
4. Pull on PLC and test:
   ```
   git pull origin hotfix/device3-sensor-bug
   sudo systemctl restart device3.service
   ```
5. If stable → merge to main:
   ```
   git checkout main
   git merge hotfix/device3-sensor-bug
   git push
   ```

This ensures **main** always remains the stable reference.

---

# 9. Handling Conflicts

Conflicts happen when multiple branches modify the same files.

Resolve conflicts by:
- Keeping updated logic in backend sequences
- Ensuring API fields remain consistent
- Validating imports and file paths

Then:

```
git add .
git commit
git push
```

---

# 10. Workflow Summary (Copy-Paste Cheat Sheet)

```
# Create feature branch
git checkout -b feature/device3-next-feature

# Work normally
git add .
git commit -m "device3: improved flowmeter logic"

# Push
git push --set-upstream origin feature/device3-next-feature

# Merge into main
git checkout main
git pull
git merge feature/device3-next-feature
git push

# Deploy to PLC
ssh pi@warp3plc.local
cd ~/projects/WARP-Devices
git pull
sudo systemctl restart device3.service
```

---

# 11. When to Update This File

Update GIT_WORKFLOW.md when:
- Deployment steps change  
- Branching rules evolve  
- Versioning strategy changes  
- You adopt CI/CD later  
