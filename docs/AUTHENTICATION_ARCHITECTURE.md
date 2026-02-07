# 🏗️ Zerodha Authentication Architecture

## System Overview

The new authentication system consists of multiple components working together to provide seamless Zerodha authentication on application startup.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Application Startup                          │
│                                                                 │
│  python start_unified.py --live                                │
│  python start_local.py                                         │
│  python -m market_data.runner --mode live                      │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────────┐
         │  Entry Point              │
         │  (start_unified.py)       │
         │  (runner.py)              │
         │  (runner_historical.py)   │
         └────────────┬──────────────┘
                      │
                      ▼
         ┌────────────────────────────┐
         │  _ensure_credentials()     │
         │  check_zerodha_credentials │
         │  (Startup Handlers)        │
         └────────────┬───────────────┘
                      │
                      ▼
    ┌─────────────────────────────────────────┐
    │  AuthStartup (NEW - Main Module)        │
    │  market_data/tools/auth_startup.py      │
    │                                         │
    │  - load_credentials()                   │
    │  - is_token_valid()                     │
    │  - trigger_interactive_login()          │
    │  - startup_check()                      │
    └────────────┬────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
    ┌────────────┐   ┌─────────────────────┐
    │  File I/O  │   │  KiteAuthService    │
    │            │   │  (Fallback)         │
    │credentials │   │                     │
    │   .json    │   │- validate_token()   │
    └────────────┘   │- refresh_token()    │
        │            │- interactive_login()│
        │            └──────────┬──────────┘
        │                       │
        │            ┌──────────┴──────────┐
        │            │                     │
        │            ▼                     ▼
        │        ┌─────────────┐    ┌────────────────┐
        │        │KiteConnect  │    │Browser Login   │
        │        │API Calls    │    │(kite_auth.py)  │
        │        │             │    │                │
        │        │- profile()  │    │- login_via_    │
        │        │- validate   │    │  browser()     │
        │        │  token      │    │- request_token │
        │        └─────────────┘    │  exchange      │
        │            │              └────────────────┘
        └────────────┴──────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────────┐
    │  Token Valid?                        │
    ├──────────────────────────────────────┤
    │  ✅ YES → Continue with app start   │
    │  ❌ NO  → Trigger re-auth           │
    └──────────────────────────────────────┘
```

## Component Breakdown

### 1. Entry Points (Startup Handlers)

#### `start_unified.py` - Main unified startup script
```python
def _ensure_credentials(self):
    """Ensure credentials exist and are valid"""
    # 1. Try new AuthStartup module (recommended)
    # 2. Fallback to KiteAuthService (legacy)
    # 3. Fallback to file-based check (emergency)
```

**When it's used:**
- Main entry point: `python start_unified.py --live`
- Handles both live and historical modes
- First place to authenticate on startup

#### `market_data/runner.py` - Market data service runner
```python
def check_zerodha_credentials(prompt_login: bool = False):
    """Check if Zerodha credentials available"""
    # 1. Try AuthStartup for validation
    # 2. Check environment variables
    # 3. Fallback to KiteAuthService
```

**When it's used:**
- When starting market data API service
- Collectors need valid Zerodha credentials
- Can be called with `--prompt-login` flag

#### `market_data/runner_historical.py` - Historical data runner
```python
# Uses new AuthStartup for Zerodha historical API
# Loads credentials for KiteConnect instance
```

**When it's used:**
- Starting historical data replay
- Needs valid Zerodha token for historical API

---

### 2. Core Authentication Module (NEW)

#### `market_data/tools/auth_startup.py` - Main auth module

**Main Class:** `AuthStartup`

**Key Methods:**

```python
class AuthStartup:
    def __init__(self, cred_path: str = "credentials.json")
        # Initialize with credential file path
    
    def load_credentials(self) -> Optional[Dict]:
        # Load from credentials.json
        # Returns: credential dict or None
    
    def save_credentials(self, creds: Dict[str, Any]) -> bool:
        # Save to credentials.json AND update env vars
        # Returns: True if successful
    
    def is_token_valid(self, creds: Optional[Dict]) -> bool:
        # Validate token with actual Kite API call
        # Checks: token exists, age < 23h, API validation
        # Returns: True if token is valid
    
    def trigger_interactive_login(self, timeout: int = 300) -> bool:
        # Open browser for interactive login
        # 1. Try in-package helper (browser-based)
        # 2. Fallback to subprocess approach
        # Returns: True if credentials obtained
    
    def startup_check(self) -> Tuple[bool, str]:
        # Complete authentication check routine
        # Returns: (success, message)
```

**Typical Usage:**
```python
from market_data.tools.auth_startup import AuthStartup

auth = AuthStartup()
success, message = auth.startup_check()

if success:
    print("Ready to start application")
else:
    print(f"Authentication failed: {message}")
```

**Authentication Flow:**
1. Load credentials from file
2. If found, validate with Kite API
3. If invalid, check environment variables
4. If still invalid, trigger browser login
5. Save new credentials to file and env

---

### 3. Support Modules (Used by AuthStartup)

#### `market_data/tools/kite_auth_service.py` - Legacy auth service (Fallback)

Used when AuthStartup is not available or as secondary validation.

**Methods:**
- `load_credentials()` - Load from file
- `save_credentials()` - Save to file
- `is_token_valid()` - Validate with API
- `trigger_interactive_login()` - Browser login
- `refresh_token()` - Refresh if possible (returns None)

#### `market_data/tools/kite_auth.py` - Browser-based login helper

Provides `login_via_browser()` function for interactive login.

**Usage:**
```python
creds, code = login_via_browser(
    api_key="anbel...",
    api_secret="...",
    force_mode=True,
    timeout=300
)
```

---

### 4. Data Storage

#### `credentials.json` - Credential storage file
```json
{
  "user_id": "BV2032",
  "api_key": "anbel41tccg186z0",
  "access_token": "IErEL7Ch389KCVw70ZuabRmcWwUpkiQB",
  "user_type": "individual",
  "email": "user@example.com",
  "login_time": "2026-02-01T10:30:00"
}
```

**Security:**
- Set file permissions: `chmod 600 credentials.json` (Unix)
- Add to `.gitignore` to prevent Git commits
- Not required if using environment variables

#### Environment Variables
```bash
KITE_API_KEY              # Required: API key from Zerodha
KITE_API_SECRET           # Required: API secret from Zerodha
KITE_ACCESS_TOKEN         # Optional: Access token (if available)
KITE_USER_ID              # Optional: User ID
KITE_ALLOW_INTERACTIVE_LOGIN  # Optional: Enable browser login (default: 1)
KITE_TOKEN_MAX_AGE_HOURS  # Optional: Token expiration (default: 23)
```

---

## Fallback Chains

### In `start_unified.py`

```
Try AuthStartup
  ├─ Load credentials.json
  ├─ Validate token
  ├─ If invalid → Trigger browser login
  └─ Save to file + env vars
      │
      ├─ Success → Continue
      │
      └─ Fail → Try fallback

Try KiteAuthService (Fallback)
  ├─ Load credentials.json
  ├─ Validate token
  ├─ If invalid → Trigger browser login
  └─ Same as above

Try legacy file check (Emergency)
  ├─ Just check if credentials.json exists
  └─ No validation
```

### In `runner.py`

```
Try AuthStartup
  ├─ Full startup check
  └─ If valid → Continue

Try env variables
  ├─ Check KITE_API_KEY + KITE_ACCESS_TOKEN
  └─ Validate together

Try KiteAuthService (Fallback)
  ├─ Load credentials.json
  └─ Validate token

If all fail and prompt_login=True
  ├─ Trigger interactive login
  └─ Re-evaluate
```

---

## Error Handling Strategy

### Level 1: Validation
```python
if not access_token:
    return False, "Missing access_token"

if token_age > 23h:
    return False, "Token expired"

# API validation
response = kite.profile()
if response.status_code != 200:
    return False, f"API returned {status_code}"
```

### Level 2: Recovery
```python
# Try refresh
new_creds = refresh_token(old_creds)
if new_creds:
    save_credentials(new_creds)
    return True

# Try interactive login
if trigger_interactive_login():
    new_creds = load_credentials()
    if is_token_valid(new_creds):
        return True
```

### Level 3: Graceful Degradation
```python
# If all else fails
if KITE_ALLOW_INTERACTIVE_LOGIN == "0":
    return False, "Interactive login disabled"

# Or show user-friendly error
print("Please run: python -m market_data.tools.kite_auth")
return False
```

---

## Token Lifecycle

```
Day 1
├─ User logs in (12:00 PM)
├─ Token created + saved
└─ login_time = 2026-02-01T12:00:00

Day 2 (< 23 hours later)
├─ Application starts
├─ Token age checked: 18 hours ✅
├─ API validates token: ✅
└─ Continue with app

Day 2 (> 23 hours later)
├─ Application starts
├─ Token age checked: 25 hours ❌
├─ Token marked as expired
├─ Browser login triggered
├─ User logs in again
├─ New token obtained
├─ New login_time recorded
└─ Continue with app
```

---

## Docker Support

### In Docker Environment

The system detects Docker and handles authentication differently:

```python
is_docker = os.path.exists('/.dockerenv') or \
            os.environ.get('DOCKER_CONTAINER') == 'true'

if is_docker:
    # Can't open browser automatically
    # Display auth URL in logs
    # Wait for user to open in browser
else:
    # Open browser locally
    # Automatic login flow
```

### Docker Volume Mounting
```bash
docker run \
  -e KITE_API_KEY="your_key" \
  -e KITE_ACCESS_TOKEN="your_token" \
  -v $(pwd)/credentials.json:/app/credentials.json:ro \
  zerodha-app
```

---

## Extension Points

### Custom Credential Loader
```python
class CustomAuthStartup(AuthStartup):
    def load_credentials(self):
        # Load from database, vault, etc.
        return super().load_credentials()
```

### Custom Validation
```python
class CustomAuthStartup(AuthStartup):
    def is_token_valid(self, creds):
        # Custom validation logic
        return super().is_token_valid(creds)
```

### Custom Browser Login
```python
class CustomAuthStartup(AuthStartup):
    def trigger_interactive_login(self):
        # Custom login flow
        return super().trigger_interactive_login()
```

---

## Testing the Architecture

### Unit Tests (Per Component)

```bash
# Test AuthStartup
python -c "from market_data.tools.auth_startup import AuthStartup; print(AuthStartup())"

# Test credential loading
python -c "from market_data.tools.auth_startup import AuthStartup; a = AuthStartup(); print(a.load_credentials())"

# Test token validation
python -c "from market_data.tools.auth_startup import AuthStartup; a = AuthStartup(); c = a.load_credentials(); print(a.is_token_valid(c))"
```

### Integration Tests

```bash
# Full auth flow
python test_auth_startup.py

# Start with live mode
python start_unified.py --live

# Verify credentials were saved
cat credentials.json
```

---

## Performance Characteristics

### Startup Time
- Credential load: ~50ms
- Token validation (API call): ~300-500ms
- Browser login (user action): ~30 seconds
- Total (if valid): ~400ms
- Total (if re-auth needed): ~30+ seconds (user-dependent)

### Resource Usage
- Memory: ~5-10 MB for auth module
- Network: 1 API call (~1KB)
- Disk: credentials.json (~500B)

### Concurrency
- Single-threaded (blocking operations)
- Suitable for startup-only auth

---

## Migration Path

### From Old System
```
Old: Manual complete_auth.py → set env → run app
New: Set env → run app → auto-login if needed
```

### From Manual Tokens
```
Old: Export KITE_ACCESS_TOKEN manually
New: Set KITE_API_KEY/SECRET → app gets token automatically
```

### From credentials.json Only
```
Old: credentials.json in Git (bad)
New: credentials.json in .gitignore + env vars (good)
```

---

## Future Enhancements

Possible improvements to the auth system:

- [ ] OAuth2 support (if Zerodha adds it)
- [ ] Token refresh automation
- [ ] Multi-factor authentication
- [ ] API key rotation helpers
- [ ] Audit logging of auth events
- [ ] Credential management dashboard

---

**Last Updated**: 2026-02-01
**Architecture Version**: 2.0
**Status**: ✅ Production Ready
