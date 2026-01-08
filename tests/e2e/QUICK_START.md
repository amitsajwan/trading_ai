# Quick Start - Testing All APIs

## PowerShell (Windows)

### Option 1: Use the script
```powershell
.\scripts\test_all_apis.ps1
```

### Option 2: Explicit file list
```powershell
pytest tests/e2e/test_dashboard_api.py tests/e2e/test_trading_api.py tests/e2e/test_control_api.py -v
```

### Option 3: Use pytest's pattern matching
```powershell
pytest tests/e2e/ -k "api" -v
```

## Bash/Linux/Mac

### Option 1: Use the script
```bash
bash scripts/test_all_apis.sh
```

### Option 2: Glob pattern (works in bash)
```bash
pytest tests/e2e/test_*_api.py -v
```

## Individual Test Suites

```powershell
# Dashboard APIs only
pytest tests/e2e/test_dashboard_api.py -v

# Trading APIs only  
pytest tests/e2e/test_trading_api.py -v

# Control APIs only
pytest tests/e2e/test_control_api.py -v
```

## All E2E Tests (APIs + Workflows)

```powershell
pytest tests/e2e/ -v
```

## With Coverage

```powershell
pytest tests/e2e/test_dashboard_api.py tests/e2e/test_trading_api.py tests/e2e/test_control_api.py --cov=dashboard --cov-report=html
```




