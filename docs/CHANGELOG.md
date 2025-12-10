# CHANGELOG.md – WARP Devices

All notable software changes for the WARP-Devices monorepo are recorded here.

Format:
- Group entries by date
- Use clear bullet points
- Reference devices, backend, dashboard, services, configs

---

## [Unreleased]
- Pending changes not yet deployed to PLCs.

---

## 2025-12-10
### Added
- Initial fastAPI backends for device1, device2, device3.
- Dashboard created using React + Vite + Tailwind.
- Systemd services added for all devices.
- Documentation suite created (README, DEV_SETUP, SYSTEMD, API_REFERENCE, IO_MAP_TEMPLATE, DEPLOYMENT, DOC_DEPENDENCY_MAP).

### Fixed
- Web API pathing issue with relative imports (`ImportError: attempted relative import beyond top-level package`).
- Tailwind PostCSS plugin error in dashboard.

### Changed
- Updated backend to use absolute imports.
- Refined dashboard fetch logic to use `localhost` during dev.

---
