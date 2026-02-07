@REM Zerodha Authentication Quick Reference Card
@echo off
echo.
echo ============================================================================
echo  ZERODHA LOGIN SYSTEM - QUICK REFERENCE
echo ============================================================================
echo.

echo SETUP (First Time)
echo ---------------------------------------------------------------------------
echo 1. Get credentials from https://kite.zerodha.com/api
echo 2. Set environment variables:
echo    set KITE_API_KEY=your_api_key
echo    set KITE_API_SECRET=your_api_secret
echo 3. Start application:
echo    python start_unified.py --live
echo    - Browser opens - Log in - Credentials saved ^✓
echo.

echo NORMAL STARTUP
echo ---------------------------------------------------------------------------
echo python start_unified.py --live
echo.
echo The system will:
echo   1. Check for saved credentials
echo   2. Validate token with Zerodha API
echo   3. If invalid - Open browser for re-login
echo   4. Start live trading once authenticated
echo.

echo TOKEN EXPIRED (After 24 Hours)
echo ---------------------------------------------------------------------------
echo python start_unified.py --live
echo - Browser opens - Log in (30 seconds) - New token obtained ^✓
echo.

echo TEST AUTHENTICATION SYSTEM
echo ---------------------------------------------------------------------------
echo python test_auth_startup.py
echo.

echo MANUAL LOGIN (If Needed)
echo ---------------------------------------------------------------------------
echo python -m market_data.tools.kite_auth
echo - Opens browser - Complete login flow - Token saved
echo.

echo ENVIRONMENT VARIABLES
echo ---------------------------------------------------------------------------
echo REQUIRED:
echo   KITE_API_KEY              API key from Zerodha dashboard
echo   KITE_API_SECRET           API secret from Zerodha dashboard
echo.
echo OPTIONAL:
echo   KITE_ACCESS_TOKEN         Access token (if available)
echo   KITE_USER_ID              Your Zerodha user ID
echo   KITE_ALLOW_INTERACTIVE_LOGIN  Enable browser login (default: 1)
echo   KITE_TOKEN_MAX_AGE_HOURS  Token expiration hours (default: 23)
echo.

echo TROUBLESHOOTING
echo ---------------------------------------------------------------------------
echo Problem: Token validation failed
echo   Fix: del credentials.json ^& python start_unified.py --live
echo.
echo Problem: No credentials found
echo   Fix: set KITE_API_KEY=... ^& python start_unified.py --live
echo.
echo Problem: Running in Docker
echo   Fix: Check logs for authentication URL, open in browser
echo.

echo FULL DOCUMENTATION
echo ---------------------------------------------------------------------------
echo Setup guide:           docs\AUTHENTICATION_SETUP.md
echo Implementation summary: IMPLEMENTATION_SUMMARY.md
echo Auth system details:    AUTH_SYSTEM_FIXED.md
echo.

echo ============================================================================
echo  ZERODHA AUTHENTICATION READY FOR USE
echo ============================================================================
echo.

REM Show how to set environment variables
echo To set environment variables:
echo.
echo PowerShell:
echo   $env:KITE_API_KEY="your_api_key"
echo   $env:KITE_API_SECRET="your_api_secret"
echo.
echo Command Prompt:
echo   set KITE_API_KEY=your_api_key
echo   set KITE_API_SECRET=your_api_secret
echo.
