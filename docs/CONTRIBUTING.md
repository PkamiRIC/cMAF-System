# CONTRIBUTING.md – WARP Devices Monorepo

This document defines how contributions should be made to the **WARP-Devices** monorepo.  
It ensures consistent code quality, folder structure, commit standards, and workflow across the backend services and dashboard UI.

This applies to all developers working on:

- FastAPI device backends (device1, device2, device3, ...)
- React + Vite + Tailwind dashboard
- Systemd service definitions
- Documentation files under `docs/`

---

# 1. Repository Structure Rules

All devices live under:

```
devices/deviceX/
```

Each device **must** contain:

```
deviceX/
  ├── src/
  ├── config/
  ├── requirements.txt
  ├── .venv/                # created on PLC only, never committed
  ├── README_DEVICEX.md
```

Backend ports follow this pattern:

| Device | API Port |
|--------|----------|
| device1 | 8001 |
| device2 | 8002 |
| device3 | 8003 |

Dashboard lives in:

```
dashboard/
```

Documentation lives in:

```
docs/
```

Any structural changes **must update**:

- Root `README.md`
- `docs/DEV_SETUP.md`
- `docs/SYSTEMD.md`
- All `README_DEVICEX.md` affected

---

# 2. Branching Strategy

Monorepo uses a simple model:

### `main`  
Stable, deployable branch.  
All production devices run code pulled from `main`.

### Feature branches
Create for each change:

```
feature/<device>-<feature-name>
```

Examples:

```
feature/device3-clean-sequence
feature/dashboard-layout-fix
feature/device2-pressure-sensor
```

---

# 3. Commit Message Guidelines

Use clear, actionable messages.

Format:

```
<scope>: <what changed>
```

Examples:

```
device3: added clean_1 sequence logic
dashboard: added device2 card component
docs: updated systemd instructions
infra: improved config loader
```

Avoid:

- "fix"
- "misc updates"
- "changes"
- empty messages

---

# 4. Python Code Standards (Backend)

### 4.1 Required practices

- Absolute imports only  
  ✔ Good: `from domain.controller import DeviceController`  
  ✖ Bad: `from ..domain.controller import DeviceController`

- No GUI/Qt code inside backend  
- All hardware interactions routed through `hardware/plc_io.py`
- All sequences routed through `domain/controller.py`
- Configuration loaded only from `config/*.yaml`
- No secrets in repo

### 4.2 Formatting

- Use Black formatting if possible
- Max line length: 120
- Use type hints everywhere:

```
def start_sequence(self, name: str) -> None:
```

---

# 5. JavaScript/React Standards (Dashboard)

### 5.1 File structure

```
dashboard/src/
  components/
  pages/
  hooks/
  utils/
```

### 5.2 Coding rules

- Use functional components
- Use hooks (`useState`, `useEffect`)
- No class components
- Use Tailwind for styling
- No inline CSS except tiny tweaks
- Use environment variables via `import.meta.env`

---

# 6. Adding a New Device

Whenever a new device is added:

1. Copy an existing device folder (device3 recommended)
2. Rename folder to `deviceX`
3. Update:
   - `config/deviceX.yaml`
   - Ports in code
   - Systemd file (`deviceX.service`)
   - Dashboard `.env`
   - Dashboard UI card
4. Update documentation:
   - `README.md`
   - `DEV_SETUP.md`
   - `SYSTEMD.md`
   - New `README_DEVICEX.md`
5. Push changes to GitHub

---

# 7. Testing Changes

### Backend

```
python -m main --config ../config/deviceX.yaml
curl http://localhost:<port>/status
```

### Dashboard

```
npm run dev
```

Open `http://localhost:5173`

---

# 8. Deployment Procedure

For backend:

```
git pull
pip install -r requirements.txt
sudo systemctl restart deviceX.service
```

For dashboard:

- Update `.env`
- Rebuild if needed:

```
npm run build
```

---

# 9. When to Update CONTRIBUTING.md

This document must be updated whenever:

- Repo structure changes  
- New coding rules are introduced  
- New devices are added  
- Build or deployment workflow changes  
- Backend/frontend conventions evolve  

This file defines **how development is done**, and must ALWAYS be kept up to date.
