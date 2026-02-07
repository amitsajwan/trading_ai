#!/bin/bash
# Docker Compose Validation Script
# Tests all compose file combinations to ensure they work correctly

set -e

echo "🔍 Docker Compose Validation Script"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to test compose configuration
test_compose() {
    local desc="$1"
    local cmd="$2"

    echo -n "Testing $desc... "
    if eval "$cmd" &>/dev/null; then
        echo -e "${GREEN}✅ PASS${NC}"
        return 0
    else
        echo -e "${RED}❌ FAIL${NC}"
        return 1
    fi
}

# Test individual files
echo -e "\n📄 Testing Individual Files:"
echo "----------------------------"

test_compose "Main compose file" "docker-compose -f docker-compose.yml config --quiet"
test_compose "Data services only" "docker-compose -f docker-compose.data.yml config --quiet"

# Test override combinations
echo -e "\n🔧 Testing Override Combinations:"
echo "----------------------------------"

test_compose "Main + Development overrides" "docker-compose -f docker-compose.yml -f docker-compose.override.yml config --quiet"
test_compose "Main + Mock overrides" "docker-compose -f docker-compose.yml -f docker-compose.mock.yml config --quiet"

# Test service counts
echo -e "\n📊 Service Count Validation:"
echo "-----------------------------"

main_services=$(docker-compose -f docker-compose.yml config --services | wc -l)
data_services=$(docker-compose -f docker-compose.data.yml config --services | wc -l)
dev_services=$(docker-compose -f docker-compose.yml -f docker-compose.override.yml config --services | wc -l)
mock_services=$(docker-compose -f docker-compose.yml -f docker-compose.mock.yml config --services | wc -l)

echo "Main compose: $main_services services"
echo "Data only: $data_services services"
echo "Dev overrides: $dev_services services"
echo "Mock overrides: $mock_services services"

# Validate service counts make sense
if [ "$main_services" -gt "$data_services" ] && [ "$dev_services" -eq "$main_services" ] && [ "$mock_services" -eq "$main_services" ]; then
    echo -e "${GREEN}✅ Service counts are consistent${NC}"
else
    echo -e "${RED}❌ Service count mismatch detected${NC}"
    exit 1
fi

# Test environment variable overrides in mock file
echo -e "\n🌍 Testing Environment Overrides:"
echo "----------------------------------"

# Check if mock environment variables are properly set
mock_config=$(docker-compose -f docker-compose.yml -f docker-compose.mock.yml config)
if echo "$mock_config" | grep -q "TRADING_PROVIDER=mock"; then
    echo -e "${GREEN}✅ Mock environment variables applied${NC}"
else
    echo -e "${RED}❌ Mock environment variables missing${NC}"
    exit 1
fi

echo -e "\n${GREEN}🎉 All validations passed!${NC}"
echo "Docker Compose configuration is ready for use."