# Credentials Troubleshooting Guide

## Issue: "No module named 'market_data.providers'"

### Root Cause
The error occurs when `start_local.py` tries to import `ZerodhaProvider` in the fallback credentials check path, but the Python path isn't set correctly.

### Fix Applied
✅ Added proper path setup before import in `start_local.py` (line 252)
✅ Improved error handling for import failures
✅ Better error messages with actionable suggestions

### Verification
The fix ensures:
1. `market_data/src` is added to `sys.path` before import
2. Import errors are caught and handled gracefully
3. Clear error messages guide users to solutions

---

## Issue: "Zerodha credentials incomplete"

### Common Scenarios

#### Scenario 1: Missing Access Token
**Error**:
```
⚠️  You have KITE_API_KEY and KITE_API_SECRET, but need KITE_ACCESS_TOKEN
```

**Solution**:
```bash
# Option 1: Set in environment
export KITE_ACCESS_TOKEN=your_access_token

# Option 2: Add to credentials.json
# {
#   "api_key": "your_api_key",
#   "access_token": "your_access_token"
# }
```

#### Scenario 2: Using Historical Mode Without Credentials
**Error**:
```
❌ Missing Zerodha credentials are required for your current configuration
```

**Solutions**:

**Option A: Use CSV file (no credentials needed)**
```bash
python start_local.py \
  --provider historical \
  --historical-source ./data/historical_data.csv \
  --historical-from 2026-01-08 \
  --allow-missing-credentials
```

**Option B: Provide Zerodha credentials**
```bash
export KITE_API_KEY=your_api_key
export KITE_API_SECRET=your_api_secret
export KITE_ACCESS_TOKEN=your_access_token

python start_local.py --provider historical --historical-from 2026-01-08
```

**Option C: Override (uses synthetic data)**
```bash
python start_local.py \
  --provider historical \
  --historical-from 2026-01-08 \
  --allow-missing-credentials
```

---

## Quick Fixes

### Fix 1: Install Market Data Module
If `market_data.providers` import fails:

```bash
pip install -e ./market_data
```

Or ensure `market_data/src` is in Python path:
```python
import sys
sys.path.insert(0, './market_data/src')
```

### Fix 2: Check credentials.json Format
Ensure `credentials.json` has correct structure:

```json
{
  "api_key": "your_api_key",
  "access_token": "your_access_token"
}
```

Or Zerodha-specific format:
```json
{
  "zerodha": {
    "api_key": "your_api_key",
    "access_token": "your_access_token"
  }
}
```

### Fix 3: Use Environment Variables
Instead of `credentials.json`, use environment variables:

```bash
export KITE_API_KEY=your_api_key
export KITE_API_SECRET=your_api_secret  
export KITE_ACCESS_TOKEN=your_access_token
```

---

## For Historical Mode (Market Down)

### Without Credentials (CSV File)
```bash
python start_local.py \
  --provider historical \
  --historical-source ./data/historical.csv \
  --historical-from 2026-01-08 \
  --allow-missing-credentials
```

### Without Credentials (Synthetic)
```bash
python start_local.py \
  --provider historical \
  --historical-from 2026-01-08 \
  --allow-missing-credentials
```

### With Credentials (Zerodha API)
```bash
export KITE_API_KEY=your_key
export KITE_API_SECRET=your_secret
export KITE_ACCESS_TOKEN=your_token

python start_local.py \
  --provider historical \
  --historical-source zerodha \
  --historical-from 2026-01-08
```

---

## Stepwise Script Issues

`scripts/stepwise_start.py` uses the same `verify_zerodha_credentials()` function, so:

- ✅ Same fixes apply
- ✅ Same error handling improvements
- ✅ Uses `--allow-missing-credentials` logic

**Note**: `stepwise_start.py` doesn't start Engine API automatically, so for signal lifecycle, you still need to start Engine API separately:

```bash
# Terminal 1
python scripts/stepwise_start.py --allow-missing-credentials

# Terminal 2 (for signal lifecycle)
python -m engine_module.api_service
```

---

## Verification After Fix

After applying fixes, verify:

1. **Import Works**:
   ```bash
   python -c "import sys; sys.path.insert(0, './market_data/src'); from market_data.providers.zerodha import ZerodhaProvider; print('✅ Import works')"
   ```

2. **Credentials Check**:
   ```bash
   python -c "from start_local import verify_zerodha_credentials; ok, _ = verify_zerodha_credentials(); print('✅' if ok else '⚠️ Credentials missing (OK for historical with CSV)')"
   ```

3. **Start Script**:
   ```bash
   python start_local.py --provider historical --historical-from 2026-01-08 --allow-missing-credentials
   ```

---

## Summary

✅ **Fixed**: Import path issue in credentials validation  
✅ **Improved**: Error messages with actionable solutions  
✅ **Enhanced**: CSV file support detection  
✅ **Better**: Handling of `--allow-missing-credentials` flag  

**The credentials check now works correctly!** 🚀
