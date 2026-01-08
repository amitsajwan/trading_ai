#!/bin/bash
# Bash script to run all API tests
# Usage: bash scripts/test_all_apis.sh

echo "Running All API Tests..."
echo ""

# Run all API test files
pytest \
    tests/e2e/test_dashboard_api.py \
    tests/e2e/test_trading_api.py \
    tests/e2e/test_control_api.py \
    -v \
    --tb=short

echo ""
echo "API Tests Complete!"



