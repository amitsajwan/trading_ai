#!/usr/bin/env python3
"""
Basic smoke tests for dashboard API endpoints.
"""

import pytest
import requests
import time
import sys

@pytest.mark.smoke
@pytest.mark.api
def test_dashboard_health():
    """Test dashboard health endpoint."""
    print("🩺 Testing dashboard health...")

    try:
        response = requests.get("http://localhost:8888/api/system-health", timeout=10)
        assert response.status_code == 200, f"Health check failed: {response.status_code}"

        data = response.json()
        assert "status" in data, "Health response missing status"
        assert data["status"] in ["ok", "degraded"], f"Unexpected status: {data['status']}"

        print("✅ Dashboard health check passed")
    except Exception as e:
        pytest.fail(f"Dashboard health check failed: {e}")

@pytest.mark.smoke
@pytest.mark.api
def test_latest_analysis():
    """Test latest analysis endpoint."""
    print("📊 Testing latest analysis...")

    try:
        response = requests.get("http://localhost:8888/api/latest-analysis", timeout=10)
        assert response.status_code == 200, f"Latest analysis failed: {response.status_code}"

        data = response.json()
        assert "decision" in data, "Analysis response missing decision"

        print("✅ Latest analysis check passed")
    except Exception as e:
        pytest.fail(f"Latest analysis check failed: {e}")

@pytest.mark.smoke
@pytest.mark.api
def test_latest_signal():
    """Test latest signal endpoint."""
    print("📈 Testing latest signal...")

    try:
        response = requests.get("http://localhost:8888/api/latest-signal", timeout=10)
        assert response.status_code == 200, f"Latest signal failed: {response.status_code}"

        data = response.json()
        assert "signal" in data or "decision" in data, "Signal response missing signal/decision"

        print("✅ Latest signal check passed")
    except Exception as e:
        pytest.fail(f"Latest signal check failed: {e}")