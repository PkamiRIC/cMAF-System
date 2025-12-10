# VERSIONING.md – WARP Devices Versioning Strategy

This file defines how to version the software for all WARP devices and the dashboard.
Software will change frequently; hardware rarely. This strategy keeps everything consistent.

---

# 1. Version Types

We maintain **three parallel version numbers:**

| Component | Example | Meaning |
|----------|----------|---------|
| Backend version | v1.3.0 | FastAPI backend + sequences |
| Dashboard version | d1.2.0 | React UI / frontend |
| API version | api-1 | Schema compatibility |

---

# 2. Backend Versioning (FastAPI)

Increment when:
- New sequence added
- Sequence behavior changes
- API endpoints added
- IO mapping logic changes
- Systemd service behavior changes

Rules:
- PATCH (v1.0.x): bugfixes only  
- MINOR (v1.x.0): sequence changes, new API fields  
- MAJOR (vX.0.0): breaking API changes  

Store backend version in:
```
devices/deviceX/src/version.py
```

Example:
```python
BACKEND_VERSION = "1.3.0"
```

Expose it in `/status` later if desired.

---

# 3. Dashboard Versioning

Increment when UI changes:
- New device card
- New sensor field displayed
- New fetch endpoints
- UI redesign
- `.env` changes

Rules:
- Follow semantic versioning: dMAJOR.MINOR.PATCH

Store version in:
```
dashboard/package.json
```

---

# 4. API Versioning

Important because dashboard and backend must stay compatible.

Rules:
- Start at `api-1`
- If adding non-breaking fields (e.g., new JSON keys): stay in same API version
- If removing or renaming fields: bump → `api-2`
- If endpoints change behavior significantly: bump

Expose API version in `/status` later if needed.

---

# 5. Device Software Version

Each PLC should store a text file with version:

```
/home/pi/device_version.txt
```

Format:
```
device3
backend v1.3.0
api api-1
dashboard d1.2.0
```

This helps immensely when debugging remote deployments.

---

# 6. Tagging Releases in Git

When stable:

```
git tag backend-v1.3.0
git tag dashboard-d1.2.0
git push --tags
```

For combined releases:

```
git tag release-2025-12-10
```

---

# 7. When to Update This File

Update VERSIONING.md when:
- A new versioning rule is introduced
- API strategy evolves
- You begin embedding versions in endpoints or config
