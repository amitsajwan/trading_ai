Dashboard package

This directory contains the dashboard FastAPI application and related UI code.

UI Shell:
- The micro-library previously located at `ui_shell/src/ui_shell` was moved to `dashboard/ui/ui_shell` to consolidate UI components.
- A top-level `ui_shell` shim remains for backward compatibility and test imports.

If you are developing UI components, prefer importing from `dashboard.ui.ui_shell` or the top-level `ui_shell` shim.
