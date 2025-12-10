# DOC_DEPENDENCY_MAP.md  
Documentation Dependency Map for WARP Devices

This file tells you **which documentation files must be updated when any major component changes**.

It is the master reference that keeps all documentation in sync across:
- multiple devices
- backend code
- dashboard code
- configs
- IO mappings
- systemd services
- repo folder structure

---

# 1. If FOLDER STRUCTURE changes

Examples:
- Renaming `device3` to `deviceC`
- Moving `src/` or adding new directories
- Restructuring `docs/`

**Update the following files:**

| MUST UPDATE | Reason |
|-------------|--------|
| `README.md` | Folder diagram lives here |
| `docs/DEV_SETUP.md` | Folder paths referenced |
| `docs/SYSTEMD.md` | WorkingDirectory path uses folder structure |
| `devices/deviceX/README_DEVICEX.md` | Points to paths on PLC |
| `docs/CONTRIBUTING.md` | Coding and structure rules |
| `docs/DEPLOYMENT.md` | Deployment paths reference real directory layout |

---

# 2. If NEW DEVICE is added (device4, device5…)

You do **NOT** modify existing files inside each device.  
You **DO** update the global documentation.

**Files to update:**

| MUST UPDATE | Reason |
|-------------|--------|
| `README.md` | Top-level diagram must include device4 |
| `docs/DEV_SETUP.md` | Add device creation steps |
| `docs/SYSTEMD.md` | New systemd service instructions |
| `docs/API_REFERENCE.md` | Add new base URL (host, port) |
| Dashboard `.env` | Add VITE_DEVICE4_URL |
| Dashboard UI | Add new DeviceCard |
| `docs/DEPLOYMENT.md` | Multi-device deployment section |

**Also generate:**

- `devices/device4/README_DEVICE4.md`  
- `devices/device4/IO_MAP_DEVICE4.md` (copied from template)

---

# 3. If IO MAPPING changes (new valves, pumps, pins, sensors)

Examples:
- New valve added on Q0.7  
- Pressure sensor model changed  
- Pump step pin moved  

**Files to update:**

| MUST UPDATE | Reason |
|-------------|--------|
| `devices/deviceX/IO_MAP_DEVICEX.md` | Master pin mapping |
| `hardware/plc_io.py` | Actual I/O control logic |
| `domain/controller.py` | Sequences depend on IO |
| `docs/IO_MAP_TEMPLATE.md` | If template evolves |
| `README_DEVICEX.md` | If operator commands depend on IO |
| `docs/API_REFERENCE.md` | If status JSON changes (e.g., new sensors) |

---

# 4. If API ENDPOINTS change

Examples:
- New endpoint `/sensors`
- New sequence added
- Status JSON gets new fields

**Files to update:**

| MUST UPDATE | Reason |
|-------------|--------|
| `interfaces/api.py` | Real API implementation |
| `domain/models.py` | Pydantic models must match |
| `API_REFERENCE.md` | API documentation lives here |
| Dashboard components | They rely on the API fields |
| `README_DEVICEX.md` | If operator behavior changes |

Optional:
- `DEPLOYMENT.md` (if ports/routes change)
- `DEV_SETUP.md` (if new dev tools required)

---

# 5. If SYSTEMD service changes

Examples:
- Name changed  
- Service path changed  
- ExecStart updated (new command, flags, config changes)  

**Files to update:**

| MUST UPDATE | Reason |
|-------------|--------|
| `/etc/systemd/system/deviceX.service` | The actual service |
| `docs/SYSTEMD.md` | Defines service structure |
| `README_DEVICEX.md` | Contains operator commands |
| `DEPLOYMENT.md` | Deployment instructions reference service names |

Also update:
- `README.md` (if mentioning services)

---

# 6. If CONFIGURATION CHANGES (deviceX.yaml)

Examples:
- New keys added  
- Port changed  
- Device ID changed  

**Files to update:**

| MUST UPDATE | Reason |
|-------------|--------|
| `config/deviceX.yaml` | The config itself |
| `README_DEVICEX.md` | Operators need updated port/ID |
| `docs/API_REFERENCE.md` | Base URLs change |
| Dashboard `.env` | Uses the port and hostname |
| `docs/DEPLOYMENT.md` | Deployment instructions reference ports |

---

# 7. If BACKEND LOGIC changes (controller, sequences)

Examples:
- New sequence added  
- Sequence logic modified  
- Emergency stop updated  

**Files to update:**

| MUST UPDATE | Reason |
|-------------|--------|
| `domain/controller.py` | Real logic lives here |
| `API_REFERENCE.md` | Must document new sequence |
| Dashboard UI | Must add new button / call |
| `README_DEVICEX.md` | Operator instructions update |
| `DEPLOYMENT.md` | Redeployment instructions |
| `docs/CONTRIBUTING.md` | Possibly update standards |

---

# 8. If HARDWARE COMPONENTS change

Examples:
- New pump driver  
- New flow meter with different pulses/liter  
- New valve wiring scheme  

**Files to update:**

| MUST UPDATE | Reason |
|-------------|--------|
| `IO_MAP_DEVICEX.md` | Reflect actual new wiring |
| `plc_io.py` | Update logic controlling new hardware |
| `controller.py` | Sequences depend on IO behavior |
| `README_DEVICEX.md` | Operator guide changes |
| `API_REFERENCE.md` | If JSON changes (e.g., new sensor readings) |

---

# 9. If DASHBOARD changes (UI rewrite, new framework, new data fields)

Examples:
- New card layout  
- More sensors displayed  
- Device cards rearranged  

**Files to update:**

| MUST UPDATE | Reason |
|-------------|--------|
| Dashboard components | Actual code |
| `.env` | Additional URLs or settings |
| `README.md` | Architecture overview |
| `DEV_SETUP.md` | Dev instructions |
| `API_REFERENCE.md` | UI depends on API |

---

# 10. If REPO POLICIES change (coding rules, branching rules)

Update:

- `CONTRIBUTING.md`  
- `README.md` (if needed)

---

# 11. Master Summary Table

| Change Type | Files To Update |
|-------------|------------------|
| Folder structure | README.md, DEV_SETUP.md, SYSTEMD.md, DEPLOYMENT.md, CONTRIBUTING.md |
| New device | README.md, DEV_SETUP.md, SYSTEMD.md, API_REFERENCE.md, DEPLOYMENT.md |
| IO mapping | IO_MAP_DEVICEX.md, plc_io.py, controller.py, API_REFERENCE.md |
| API changes | interfaces/api.py, models.py, API_REFERENCE.md, Dashboard UI |
| Systemd changes | SYSTEMD.md, README_DEVICEX.md, DEPLOYMENT.md |
| Config changes | config/deviceX.yaml, README_DEVICEX.md, API_REFERENCE.md, Dashboard .env |
| Sequence logic | controller.py, API_REFERENCE.md, Dashboard UI, README_DEVICEX.md |
| Hardware changes | IO_MAP_DEVICEX.md, plc_io.py, controller.py, API_REFERENCE.md |
| Dashboard changes | Components, .env, README.md, DEV_SETUP.md |

---

# 12. Purpose of This Document

This file prevents:

- outdated documents  
- missing updates when hardware/software changes  
- inconsistent device setups  
- confusion when scaling beyond 3 devices  

Keep this file accurate — it is the **documentation brain** of the entire project.
