#!/usr/bin/env python3
"""
Basic component tests for dashboard UI.
"""

import pytest
from playwright.sync_api import Page, expect

@pytest.mark.ui
def test_dashboard_title(page: Page):
    """Test dashboard title loads correctly."""
    page.goto("http://localhost:3000")

    # Check if title is present
    title = page.locator("h1").first
    expect(title).to_be_visible()

@pytest.mark.ui
def test_navigation_menu(page: Page):
    """Test navigation menu is present."""
    page.goto("http://localhost:3000")

    # Check for navigation elements
    nav = page.locator("nav").first
    expect(nav).to_be_visible()

@pytest.mark.ui
def test_system_status_display(page: Page):
    """Test system status section displays."""
    page.goto("http://localhost:3000")

    # Look for status indicators
    status_section = page.locator("[data-testid='system-status'], .status, #status").first
    expect(status_section).to_be_visible()

@pytest.mark.ui
def test_market_data_section(page: Page):
    """Test market data section loads."""
    page.goto("http://localhost:3000")

    # Check for market data elements
    market_data = page.locator("[data-testid='market-data'], .market-data, #market-data").first
    expect(market_data).to_be_visible()

@pytest.mark.ui
def test_signals_display(page: Page):
    """Test signals section displays."""
    page.goto("http://localhost:3000")

    # Check for signals/trading signals
    signals = page.locator("[data-testid='signals'], .signals, #signals").first
    expect(signals).to_be_visible()

@pytest.mark.ui
def test_analysis_section(page: Page):
    """Test analysis section displays."""
    page.goto("http://localhost:3000")

    # Check for analysis content
    analysis = page.locator("[data-testid='analysis'], .analysis, #analysis").first
    expect(analysis).to_be_visible()