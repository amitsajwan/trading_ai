#!/bin/bash

# Multi-Symbol Trading System Manager
# Run separate containers for BTC, Bank Nifty, and Nifty 50

set -e

COMPOSE_FILE="docker-compose.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to show usage
usage() {
    echo "Usage: $0 {start|stop|restart|logs|status} {btc|banknifty|nifty|all}"
    echo ""
    echo "Commands:"
    echo "  start    - Start containers for specified symbol(s)"
    echo "  stop     - Stop containers for specified symbol(s)"
    echo "  restart  - Restart containers for specified symbol(s)"
    echo "  logs     - Show logs for specified symbol(s)"
    echo "  status   - Show status of all containers"
    echo ""
    echo "Symbols:"
    echo "  btc      - Bitcoin trading system"
    echo "  banknifty- Bank Nifty trading system"
    echo "  nifty    - Nifty 50 trading system"
    echo "  all      - All trading systems"
    echo ""
    echo "Examples:"
    echo "  $0 start btc          # Start BTC system"
    echo "  $0 start all          # Start all systems"
    echo "  $0 logs banknifty     # Show Bank Nifty logs"
    echo "  $0 restart nifty      # Restart Nifty system"
    exit 1
}

# Function to get service names for a symbol
get_services() {
    local symbol=$1
    case $symbol in
        btc)
            echo "trading-bot-btc backend-btc"
            ;;
        banknifty)
            echo "trading-bot-banknifty backend-banknifty"
            ;;
        nifty)
            echo "trading-bot-nifty backend-nifty"
            ;;
        all)
            echo "mongodb redis trading-bot-btc backend-btc trading-bot-banknifty backend-banknifty trading-bot-nifty backend-nifty"
            ;;
        *)
            echo "ERROR: Unknown symbol '$symbol'"
            exit 1
            ;;
    esac
}

# Function to start services
start_services() {
    local symbol=$1
    local services=$(get_services $symbol)

    echo -e "${GREEN}Starting $symbol trading system...${NC}"
    echo "Services: $services"

    if [ "$symbol" = "all" ]; then
        docker-compose -f $COMPOSE_FILE up -d
    else
        docker-compose -f $COMPOSE_FILE up -d $services
    fi

    echo -e "${GREEN}✓ $symbol system started${NC}"
    echo ""
    echo "Dashboard URLs:"
    case $symbol in
        btc)
            echo "  BTC Dashboard: http://localhost:8001"
            ;;
        banknifty)
            echo "  Bank Nifty Dashboard: http://localhost:8002"
            ;;
        nifty)
            echo "  Nifty 50 Dashboard: http://localhost:8003"
            ;;
        all)
            echo "  BTC Dashboard: http://localhost:8001"
            echo "  Bank Nifty Dashboard: http://localhost:8002"
            echo "  Nifty 50 Dashboard: http://localhost:8003"
            ;;
    esac
}

# Function to stop services
stop_services() {
    local symbol=$1
    local services=$(get_services $symbol)

    echo -e "${YELLOW}Stopping $symbol trading system...${NC}"
    echo "Services: $services"

    if [ "$symbol" = "all" ]; then
        docker-compose -f $COMPOSE_FILE down
    else
        docker-compose -f $COMPOSE_FILE stop $services
    fi

    echo -e "${GREEN}✓ $symbol system stopped${NC}"
}

# Function to restart services
restart_services() {
    local symbol=$1
    local services=$(get_services $symbol)

    echo -e "${BLUE}Restarting $symbol trading system...${NC}"
    echo "Services: $services"

    if [ "$symbol" = "all" ]; then
        docker-compose -f $COMPOSE_FILE restart
    else
        docker-compose -f $COMPOSE_FILE restart $services
    fi

    echo -e "${GREEN}✓ $symbol system restarted${NC}"
}

# Function to show logs
show_logs() {
    local symbol=$1
    local services=$(get_services $symbol)

    echo -e "${BLUE}Showing logs for $symbol trading system...${NC}"
    echo "Services: $services"
    echo "Press Ctrl+C to exit logs"
    echo ""

    if [ "$symbol" = "all" ]; then
        docker-compose -f $COMPOSE_FILE logs -f
    else
        docker-compose -f $COMPOSE_FILE logs -f $services
    fi
}

# Function to show status
show_status() {
    echo -e "${BLUE}Trading System Status${NC}"
    echo "===================="
    docker-compose -f $COMPOSE_FILE ps
}

# Main script logic
if [ $# -ne 2 ]; then
    usage
fi

COMMAND=$1
SYMBOL=$2

case $COMMAND in
    start)
        start_services $SYMBOL
        ;;
    stop)
        stop_services $SYMBOL
        ;;
    restart)
        restart_services $SYMBOL
        ;;
    logs)
        show_logs $SYMBOL
        ;;
    status)
        show_status
        ;;
    *)
        echo -e "${RED}ERROR: Unknown command '$COMMAND'${NC}"
        usage
        ;;
esac