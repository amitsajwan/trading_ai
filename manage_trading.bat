@echo off
REM Simple Multi-Symbol Trading System Manager for Windows

set COMPOSE_FILE=docker-compose.yml

echo Multi-Symbol Trading System Manager
echo ===================================
echo.

if "%1"=="start" goto start_cmd
if "%1"=="stop" goto stop_cmd
if "%1"=="restart" goto restart_cmd
if "%1"=="logs" goto logs_cmd
if "%1"=="status" goto status_cmd
goto usage

:start_cmd
if "%2"=="btc" (
    echo Starting BTC trading system...
    docker-compose -f %COMPOSE_FILE% up -d trading-bot-btc backend-btc
    echo ✓ BTC system started
    echo Dashboard: http://localhost:8001
    goto end
)
if "%2"=="banknifty" (
    echo Starting Bank Nifty trading system...
    docker-compose -f %COMPOSE_FILE% up -d trading-bot-banknifty backend-banknifty
    echo ✓ Bank Nifty system started
    echo Dashboard: http://localhost:8002
    goto end
)
if "%2"=="nifty" (
    echo Starting Nifty 50 trading system...
    docker-compose -f %COMPOSE_FILE% up -d trading-bot-nifty backend-nifty
    echo ✓ Nifty 50 system started
    echo Dashboard: http://localhost:8003
    goto end
)
if "%2"=="all" (
    echo Starting ALL trading systems...
    docker-compose -f %COMPOSE_FILE% up -d
    echo ✓ All systems started
    echo Dashboards:
    echo   BTC: http://localhost:8001
    echo   Bank Nifty: http://localhost:8002
    echo   Nifty 50: http://localhost:8003
    goto end
)
echo ERROR: Unknown symbol '%2'
goto usage

:stop_cmd
if "%2"=="btc" (
    echo Stopping BTC trading system...
    docker-compose -f %COMPOSE_FILE% stop trading-bot-btc backend-btc
    echo ✓ BTC system stopped
    goto end
)
if "%2"=="banknifty" (
    echo Stopping Bank Nifty trading system...
    docker-compose -f %COMPOSE_FILE% stop trading-bot-banknifty backend-banknifty
    echo ✓ Bank Nifty system stopped
    goto end
)
if "%2"=="nifty" (
    echo Stopping Nifty 50 trading system...
    docker-compose -f %COMPOSE_FILE% stop trading-bot-nifty backend-nifty
    echo ✓ Nifty 50 system stopped
    goto end
)
if "%2"=="all" (
    echo Stopping ALL trading systems...
    docker-compose -f %COMPOSE_FILE% down
    echo ✓ All systems stopped
    goto end
)
echo ERROR: Unknown symbol '%2'
goto usage

:restart_cmd
if "%2"=="btc" (
    echo Restarting BTC trading system...
    docker-compose -f %COMPOSE_FILE% restart trading-bot-btc backend-btc
    echo ✓ BTC system restarted
    goto end
)
if "%2"=="banknifty" (
    echo Restarting Bank Nifty trading system...
    docker-compose -f %COMPOSE_FILE% restart trading-bot-banknifty backend-banknifty
    echo ✓ Bank Nifty system restarted
    goto end
)
if "%2"=="nifty" (
    echo Restarting Nifty 50 trading system...
    docker-compose -f %COMPOSE_FILE% restart trading-bot-nifty backend-nifty
    echo ✓ Nifty 50 system restarted
    goto end
)
if "%2"=="all" (
    echo Restarting ALL trading systems...
    docker-compose -f %COMPOSE_FILE% restart
    echo ✓ All systems restarted
    goto end
)
echo ERROR: Unknown symbol '%2'
goto usage

:logs_cmd
if "%2"=="btc" (
    echo Showing BTC logs (Ctrl+C to exit)...
    docker-compose -f %COMPOSE_FILE% logs -f trading-bot-btc backend-btc
    goto end
)
if "%2"=="banknifty" (
    echo Showing Bank Nifty logs (Ctrl+C to exit)...
    docker-compose -f %COMPOSE_FILE% logs -f trading-bot-banknifty backend-banknifty
    goto end
)
if "%2"=="nifty" (
    echo Showing Nifty 50 logs (Ctrl+C to exit)...
    docker-compose -f %COMPOSE_FILE% logs -f trading-bot-nifty backend-nifty
    goto end
)
if "%2"=="all" (
    echo Showing ALL logs (Ctrl+C to exit)...
    docker-compose -f %COMPOSE_FILE% logs -f
    goto end
)
echo ERROR: Unknown symbol '%2'
goto usage

:status_cmd
echo Trading System Status:
docker-compose -f %COMPOSE_FILE% ps
goto end

:usage
echo.
echo Usage: manage_trading.bat {start^|stop^|restart^|logs^|status} {btc^|banknifty^|nifty^|all}
echo.
echo Examples:
echo   manage_trading.bat start btc        - Start BTC system
echo   manage_trading.bat start all        - Start all systems
echo   manage_trading.bat logs banknifty   - Show Bank Nifty logs
echo   manage_trading.bat stop nifty       - Stop Nifty system
echo   manage_trading.bat status           - Show all statuses
goto end

:end