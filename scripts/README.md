Scripts consolidation

Overview

This directory was consolidated on 2026-01-03 to reduce noise and centralize developer/ops scripts.

Layout:
- scripts/setup/      : setup and env tooling
- scripts/manage/     : start/stop/restart and system control scripts
- scripts/monitor/    : check, monitor, and verify scripts
- scripts/diagnostics/ : diagnostics and debug helpers
- scripts/utils/      : small utilities and helpers
- scripts/tests/      : maintained test helpers (minimal)

Removed files
- A number of ad-hoc test/debug scripts and historical check scripts were permanently deleted on 2026-01-03 as they were outdated or had compressed backups already deleted. See REMOVED_FILES_2026-01-03.md for details.

Restore / ownership
- If you need a removed script restored, contact repository maintainers. Where possible we recommend adding a small, tested helper under `scripts/` or converting it into a CI job.

Policy
- Keep scripts small, documented, and idempotent.
- Prefer centralizing operational checks into `scripts/monitor` and add tests where feasible.

Contact: repo maintainers
