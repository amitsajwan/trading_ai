# Zerodha Authentication Setup Guide

This guide walks you through properly authenticating with Zerodha for live and historical market data.

## Overview

The authentication system has been redesigned to:
- ✅ Never store hardcoded credentials
- ✅ Support interactive browser-based login
- ✅ Automatically validate tokens at startup
- ✅ Handle token expiration gracefully
- ✅ Work in both Docker and local environments

## Quick Start

### Step 1: Get Your Zerodha API Credentials

1. Visit https://kite.zerodha.com/api
2. Note your:
   - **API Key** (starts with `anbel...`)
   - **API Secret** (longer string)

### Step 2: Set Environment Variables

```bash
# On Linux/Mac
export KITE_API_KEY="your_api_key_here"
export KITE_API_SECRET="your_api_secret_here"

# On Windows (PowerShell)
$env:KITE_API_KEY="your_api_key_here"
$env:KITE_API_SECRET="your_api_secret_here"

# Or create a .env file in the project root
cat > .env << EOF
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here
EOF
```

### Step 3: Start the Application

```bash
python start_unified.py --live
```

The system will:
1. Check for saved credentials in `credentials.json`
2. Validate the token with Zerodha
3. If invalid/missing, open a browser for interactive login
4. Automatically save the new token

## Detailed Auth Flow

### First Time Setup (No Credentials)

```
python start_unified.py --live
  │
  ├─ Check credentials.json → NOT FOUND
  ├─ Check environment vars → NOT FOUND
  │
  ├─ 🌐 Open browser → Zerodha login page
  ├─ User logs in with username/password
  ├─ User approves app access
  │
  ├─ 💾 Save token to credentials.json
  ├─ 💾 Update environment variables
  │
  └─ ✅ Start live trading
```

### Token Expiration (24 Hours)

```
python start_unified.py --live
  │
  ├─ Load credentials.json
  ├─ Validate token → EXPIRED
  │
  ├─ 🌐 Open browser → Re-authentication
  ├─ User logs in again
  │
  ├─ 💾 Save new token
  │
  └─ ✅ Continue with new token
```

### Using Environment Variables Only

If you prefer not to save credentials to disk (e.g., in containerized environments):

```bash
export KITE_API_KEY="your_api_key"
export KITE_API_SECRET="your_api_secret"
export KITE_ACCESS_TOKEN="your_access_token"

python start_unified.py --live
```

The application will use these without saving to file.

## Manual Authentication

If automatic login doesn't work (e.g., in Docker headless environments):

### Option 1: Interactive Browser Auth
```bash
python -m market_data.tools.kite_auth
```

This opens a browser where you can:
1. Log in with your Zerodha credentials
2. Approve app access
3. Get redirected with an access token
4. Token is automatically saved to credentials.json

### Option 2: Using Request Token
If you have a request token from the Kite login page:

```bash
export KITE_API_KEY="your_api_key"
export KITE_API_SECRET="your_api_secret"
export KITE_REQUEST_TOKEN="your_request_token"

python complete_auth.py
```

⚠️ **Note**: Request tokens are valid for ~5 minutes only.

## Security Best Practices

### ✅ DO:
- Store API credentials in environment variables
- Use `credentials.json` with appropriate file permissions (600)
- Rotate access tokens periodically (Zerodha tokens last 24 hours)
- Use different API keys for development vs. production
- Never commit credentials to version control

### ❌ DON'T:
- Hardcode API keys in source files
- Share `credentials.json` in shared environments
- Commit `.env` or credentials files to Git
- Use the same token across multiple machines

### .gitignore

Ensure your `.gitignore` includes:
```
credentials.json
credentials.json.backup
.env
.env.local
.env.*.local
*.key
*.secret
```

## Troubleshooting

### "No valid credentials found"

**Cause**: credentials.json missing or invalid token

**Fix**:
```bash
# Option 1: Delete old credentials and re-authenticate
rm credentials.json
python start_unified.py --live

# Option 2: Use manual browser auth
python -m market_data.tools.kite_auth
```

### "Token validation failed (401/403)"

**Cause**: Token expired or invalid

**Fix**:
```bash
# Delete credentials and re-authenticate
rm credentials.json
python start_unified.py --live

# Or manually refresh
python -m market_data.tools.kite_auth
```

### "Running in Docker - authentication URL will be displayed"

**Cause**: Docker container can't open browser

**Fix**: You'll see a URL in logs like `http://localhost:3000/auth?request_token=...`
1. Copy the URL
2. Open it in your browser on the host machine
3. Complete login
4. Token will be saved automatically

### "Interactive login disabled"

**Cause**: `KITE_ALLOW_INTERACTIVE_LOGIN=0` environment variable

**Fix**: Either:
- Remove the environment variable, or
- Ensure valid credentials exist, or
- Use manual auth: `python -m market_data.tools.kite_auth`

## Credential Storage Locations

The system checks credentials in this order:

1. **Environment Variables** (highest priority)
   - `KITE_API_KEY`
   - `KITE_ACCESS_TOKEN`
   - `KITE_USER_ID`

2. **credentials.json** (recommended for local development)
   ```json
   {
     "api_key": "your_api_key",
     "access_token": "your_access_token",
     "user_id": "your_user_id",
     "login_time": "2026-02-01T10:30:00"
   }
   ```

3. **Request Token Exchange** (for one-time setup)
   - Environment: `KITE_REQUEST_TOKEN`
   - Tool: `python complete_auth.py`

## Docker Environment

For Docker deployments:

```dockerfile
# In your Dockerfile
ENV KITE_API_KEY=""
ENV KITE_API_SECRET=""
ENV KITE_ALLOW_INTERACTIVE_LOGIN=0  # Usually disabled in Docker

# Mount credentials.json or pass via environment
```

```bash
# When running Docker
docker run \
  -e KITE_API_KEY="your_key" \
  -e KITE_ACCESS_TOKEN="your_token" \
  -v $(pwd)/credentials.json:/app/credentials.json:ro \
  zerodha-app
```

## API Reference

### AuthStartup Class

```python
from market_data.tools.auth_startup import AuthStartup

auth = AuthStartup(cred_path="credentials.json")

# Check and validate credentials
success, message = auth.startup_check()
if success:
    print("✅ Authenticated")
else:
    print(f"❌ {message}")

# Trigger interactive login
if auth.trigger_interactive_login(timeout=300):
    print("✅ Login successful")
```

### KiteAuthService Class

```python
from market_data.tools.kite_auth_service import KiteAuthService

svc = KiteAuthService()

# Load and validate
creds = svc.load_credentials()
if svc.is_token_valid(creds):
    print("✅ Token valid")

# Trigger login if needed
if not svc.is_token_valid(creds):
    svc.trigger_interactive_login()
```

## FAQ

**Q: How long is the access token valid?**
A: Zerodha access tokens are valid for 24 hours. After that, you'll need to re-authenticate.

**Q: Can I use the same token on multiple machines?**
A: Yes, but it's not recommended. Each machine should authenticate once to get its own token.

**Q: What if I lose my credentials.json?**
A: Just re-run `python start_unified.py --live` and authenticate again.

**Q: Can I use OAuth2 or other auth methods?**
A: Currently only Kite's access token method is supported. Zerodha doesn't expose OAuth2 for retail traders.

**Q: How do I rotate credentials?**
A: Log in to https://kite.zerodha.com/api and generate a new API key. Update your environment variables and delete credentials.json.

---

**Last Updated**: 2026-02-01
**Status**: Active ✅
