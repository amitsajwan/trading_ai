"""Enhanced GenAI Trading Dashboard Pro with improved UI and features."""

import logging
import json
from fastapi import FastAPI, HTTPException, Request, Query, Query
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from io import StringIO
import csv

# Mock imports - replace with your actual modules
try:
    from mongodb_schema import get_mongo_client, get_collection
    from config.settings import settings
    from data.market_memory import MarketMemory
    from monitoring.system_health import SystemHealthChecker
    from agents.llm_provider_manager import get_llm_manager
except ImportError:
    settings = None
    MarketMemory = None
    SystemHealthChecker = None
    get_llm_manager = None

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="GenAI Trading Dashboard",
    description="Advanced trading system with real-time monitoring, analytics, and multi-agent AI",
    version="2.0"
)

# Cache control middleware
class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

app.add_middleware(CacheControlMiddleware)

# Global instances
marketmemory = MarketMemory() if MarketMemory else None
healthchecker = SystemHealthChecker() if SystemHealthChecker else None
if healthchecker and marketmemory:
    healthchecker.market_memory = marketmemory

# Helper: add camel/no-underscore aliases to API response dicts (recursive)
def add_camel_aliases(obj):
    """Return a copy of obj with additional alias keys for snake_case fields.

    Adds two aliases for keys containing underscores:
    - no_underscore (e.g., entry_price -> entryprice)
    - camelCase (e.g., entry_price -> entryPrice)

    Recurses into nested dicts and lists.
    """
    if isinstance(obj, dict):
        new = {}
        for k, v in obj.items():
            # Recurse into nested structures first
            if isinstance(v, (dict, list)):
                v = add_camel_aliases(v)
            new[k] = v
            if "_" in k:
                # no underscore alias (all lowercase)
                no_us = k.replace("_", "")
                if no_us not in new:
                    new[no_us] = v
                # camelCase alias
                parts = k.split("_")
                camel = parts[0] + "".join(p.title() for p in parts[1:])
                if camel not in new:
                    new[camel] = v
        return new
    elif isinstance(obj, list):
        return [add_camel_aliases(i) if isinstance(i, (dict, list)) else i for i in obj]
    else:
        return obj

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GenAI Trading Dashboard Pro</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --primary: #667eea;
            --primary-dark: #5568d3;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
            --dark-bg: #0f172a;
            --light-bg: #f8fafc;
            --border: #e5e7eb;
            --card-shadow: 0 1px 3px rgba(0,0,0,0.1);
            --card-hover: 0 4px 12px rgba(0,0,0,0.15);
        }

        html {
            scroll-behavior: smooth;
            font-size: 16px;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #1f2937;
            padding: 0;
            min-height: 100vh;
            transition: background 0.3s ease;
        }

        body.dark-mode {
            background: #0a0e27;
            color: #e5e7eb;
        }

        .wrapper {
            display: flex;
            min-height: 100vh;
        }

        /* SIDEBAR */
        .sidebar {
            width: 280px;
            background: white;
            border-right: 1px solid var(--border);
            padding: 20px;
            position: sticky;
            top: 0;
            height: 100vh;
            overflow-y: auto;
            box-shadow: var(--card-shadow);
        }

        body.dark-mode .sidebar {
            background: #1e293b;
            border-right-color: #334155;
        }

        .sidebar-header {
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }

        body.dark-mode .sidebar-header {
            border-bottom-color: #334155;
        }

        .sidebar-logo {
            font-size: 18px;
            font-weight: bold;
            color: var(--primary);
            margin-bottom: 5px;
        }

        .sidebar-subtitle {
            font-size: 12px;
            color: #6b7280;
        }

        body.dark-mode .sidebar-subtitle {
            color: #9ca3af;
        }

        .nav-section {
            margin-bottom: 25px;
        }

        .nav-section-title {
            font-size: 11px;
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.5px;
            color: #9ca3af;
            margin-bottom: 12px;
        }

        .nav-item {
            padding: 10px 12px;
            margin-bottom: 6px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s ease;
            color: #4b5563;
            border-left: 3px solid transparent;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        body.dark-mode .nav-item {
            color: #cbd5e1;
        }

        .nav-item:hover {
            background: #f3f4f6;
            color: var(--primary);
        }

        body.dark-mode .nav-item:hover {
            background: #334155;
            color: #60a5fa;
        }

        .nav-item.active {
            background: #f0f4ff;
            color: var(--primary);
            border-left-color: var(--primary);
            font-weight: 500;
        }

        body.dark-mode .nav-item.active {
            background: #1e40af20;
            color: #60a5fa;
            border-left-color: #60a5fa;
        }

        .sidebar-footer {
            position: sticky;
            bottom: 0;
            padding-top: 20px;
            border-top: 1px solid var(--border);
            margin-top: 30px;
        }

        body.dark-mode .sidebar-footer {
            border-top-color: #334155;
        }

        .status-indicator {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px 12px;
            background: #f0fdf4;
            border-radius: 6px;
            margin-bottom: 10px;
            font-size: 13px;
        }

        body.dark-mode .status-indicator {
            background: #064e3b20;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--success);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        /* MAIN CONTENT */
        .main {
            flex: 1;
            overflow-y: auto;
            padding: 30px;
        }

        .page-header {
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 20px;
        }

        .page-title {
            font-size: 28px;
            font-weight: 700;
            color: white;
            text-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        body.dark-mode .page-title {
            text-shadow: none;
        }

        .header-controls {
            display: flex;
            gap: 12px;
            align-items: center;
            flex-wrap: wrap;
        }

        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 6px;
            white-space: nowrap;
        }

        .btn-primary {
            background: white;
            color: var(--primary);
        }

        .btn-primary:hover {
            background: #f0f4ff;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
        }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.15);
            color: white;
            border: 1px solid rgba(255, 255, 255, 0.3);
        }

        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.25);
        }

        .badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }

        .badge-success {
            background: var(--success);
            color: white;
        }

        .badge-warning {
            background: var(--warning);
            color: white;
        }

        /* SIGNAL BANNER */
        .signal-banner {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 24px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 8px 24px rgba(102, 126, 234, 0.2);
        }

        .signal-banner.buy {
            background: linear-gradient(135deg, var(--success) 0%, #059669 100%);
        }

        .signal-banner.sell {
            background: linear-gradient(135deg, var(--danger) 0%, #dc2626 100%);
        }

        .signal-banner-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 20px;
            gap: 20px;
        }

        .signal-info {
            flex: 1;
        }

        .signal-icon {
            font-size: 32px;
            margin-right: 12px;
        }

        .signal-title {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 5px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .signal-subtitle {
            font-size: 14px;
            opacity: 0.9;
        }

        .signal-timestamp {
            font-size: 12px;
            opacity: 0.75;
        }

        .signal-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
        }

        .signal-metric {
            background: rgba(255, 255, 255, 0.15);
            padding: 12px;
            border-radius: 8px;
            backdrop-filter: blur(10px);
        }

        .signal-metric-label {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            opacity: 0.85;
            margin-bottom: 5px;
        }

        .signal-metric-value {
            font-size: 18px;
            font-weight: bold;
        }

        /* DASHBOARD GRID */
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        @media (max-width: 1400px) {
            .dashboard-grid {
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            }
        }

        .card {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: var(--card-shadow);
            transition: all 0.2s ease;
            border: 1px solid var(--border);
        }

        body.dark-mode .card {
            background: #1e293b;
            border-color: #334155;
        }

        .card:hover {
            box-shadow: var(--card-hover);
            transform: translateY(-2px);
        }

        .card-header {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 16px;
            padding-bottom: 16px;
            border-bottom: 2px solid var(--primary);
        }

        body.dark-mode .card-header {
            border-bottom-color: #60a5fa;
        }

        .card-title {
            font-size: 16px;
            font-weight: 600;
            color: var(--primary);
            margin: 0;
        }

        body.dark-mode .card-title {
            color: #60a5fa;
        }

        .card-content {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .metric-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid var(--border);
        }

        body.dark-mode .metric-row {
            border-bottom-color: #334155;
        }

        .metric-row:last-child {
            border-bottom: none;
        }

        .metric-label {
            font-size: 13px;
            color: #6b7280;
            font-weight: 500;
        }

        body.dark-mode .metric-label {
            color: #9ca3af;
        }

        .metric-value {
            font-size: 14px;
            font-weight: 600;
            color: #1f2937;
        }

        body.dark-mode .metric-value {
            color: #f1f5f9;
        }

        .metric-positive {
            color: var(--success);
        }

        .metric-negative {
            color: var(--danger);
        }

        .metric-neutral {
            color: #6b7280;
        }

        /* FULL WIDTH SECTIONS */
        .section-full {
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: var(--card-shadow);
            margin-bottom: 20px;
            border: 1px solid var(--border);
        }

        body.dark-mode .section-full {
            background: #1e293b;
            border-color: #334155;
        }

        .section-title {
            font-size: 18px;
            font-weight: 600;
            color: var(--primary);
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        body.dark-mode .section-title {
            color: #60a5fa;
        }

        /* TABLES */
        .data-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }

        .data-table thead {
            background: #f9fafb;
            border-bottom: 2px solid var(--primary);
        }

        body.dark-mode .data-table thead {
            background: #0f172a;
            border-bottom-color: #60a5fa;
        }

        .data-table th {
            padding: 12px;
            text-align: left;
            font-weight: 600;
            color: var(--primary);
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.5px;
        }

        body.dark-mode .data-table th {
            color: #60a5fa;
        }

        .data-table td {
            padding: 12px;
            border-bottom: 1px solid var(--border);
        }

        body.dark-mode .data-table td {
            border-bottom-color: #334155;
        }

        .data-table tbody tr:hover {
            background: #f9fafb;
        }

        body.dark-mode .data-table tbody tr:hover {
            background: #0f172a;
        }

        .badge-small {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }

        .badge-buy {
            background: #dcfce7;
            color: #166534;
        }

        .badge-sell {
            background: #fee2e2;
            color: #991b1b;
        }

        .badge-hold {
            background: #f3f4f6;
            color: #374151;
        }

        .badge-open {
            background: #dbeafe;
            color: #1e40af;
        }

        .badge-closed {
            background: #d1fae5;
            color: #065f46;
        }

        /* AGENT CARDS */
        .agent-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
        }

        .agent-card {
            background: #f9fafb;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 15px;
            transition: all 0.2s ease;
        }

        body.dark-mode .agent-card {
            background: #0f172a;
            border-color: #334155;
        }

        .agent-card:hover {
            box-shadow: var(--card-hover);
            border-color: var(--primary);
        }

        .agent-name {
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--primary);
            margin-bottom: 10px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border);
        }

        body.dark-mode .agent-name {
            color: #60a5fa;
            border-bottom-color: #334155;
        }

        .agent-metric {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 10px;
            margin-bottom: 8px;
            font-size: 12px;
        }

        .agent-metric:last-child {
            margin-bottom: 0;
        }

        .agent-label {
            color: #6b7280;
            font-weight: 500;
        }

        body.dark-mode .agent-label {
            color: #9ca3af;
        }

        .agent-value {
            font-weight: 600;
            color: #1f2937;
        }

        body.dark-mode .agent-value {
            color: #f1f5f9;
        }

        /* TABS */
        .tab-navigation {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 2px solid var(--border);
        }

        body.dark-mode .tab-navigation {
            border-bottom-color: #334155;
        }

        .tab-button {
            background: none;
            border: none;
            padding: 12px 16px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            color: #6b7280;
            border-bottom: 3px solid transparent;
            margin-bottom: -2px;
            transition: all 0.2s ease;
        }

        body.dark-mode .tab-button {
            color: #9ca3af;
        }

        .tab-button.active {
            color: var(--primary);
            border-bottom-color: var(--primary);
        }

        body.dark-mode .tab-button.active {
            color: #60a5fa;
            border-bottom-color: #60a5fa;
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }

        /* RESPONSIVE */
        @media (max-width: 768px) {
            .wrapper {
                flex-direction: column;
            }

            .sidebar {
                width: 100%;
                height: auto;
                position: relative;
                border-right: none;
                border-bottom: 1px solid var(--border);
                max-height: 200px;
                overflow-x: auto;
            }

            .main {
                padding: 20px;
            }

            .page-header {
                flex-direction: column;
            }

            .page-title {
                font-size: 22px;
            }

            .dashboard-grid {
                grid-template-columns: 1fr;
            }

            .signal-banner-top {
                flex-direction: column;
            }

            .signal-grid {
                grid-template-columns: repeat(2, 1fr);
            }

            .agent-grid {
                grid-template-columns: 1fr;
            }
        }

        /* UTILITIES */
        .loading {
            text-align: center;
            padding: 40px 20px;
            color: #6b7280;
            font-style: italic;
        }

        body.dark-mode .loading {
            color: #9ca3af;
        }

        .text-small {
            font-size: 12px;
            color: #6b7280;
        }

        body.dark-mode .text-small {
            color: #9ca3af;
        }

        .mt-20 {
            margin-top: 20px;
        }

        .mb-20 {
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="wrapper">
        <!-- SIDEBAR -->
        <aside class="sidebar">
            <div class="sidebar-header">
                <div class="sidebar-logo">📊 Trading Pro</div>
                <div class="sidebar-subtitle">GenAI Dashboard v3</div>
            </div>

            <nav class="nav-section">
                <div class="nav-section-title">Main</div>
                <div class="nav-item active" onclick="scrollToSection('overview')">📈 Overview</div>
                <div class="nav-item" onclick="scrollToSection('trades')">📋 Trades</div>
                <div class="nav-item" onclick="scrollToSection('analysis')">🤖 Analysis</div>
                <div class="nav-item" onclick="scrollToSection('portfolio')">🎯 Portfolio</div>
            </nav>

            <nav class="nav-section">
                <div class="nav-section-title">Tools</div>
                <div class="nav-item" onclick="loadData()">🔄 Refresh</div>
                <div class="nav-item" onclick="exportTrades()">📥 Export</div>
            </nav>

            <div class="sidebar-footer">
                <div class="status-indicator">
                    <div class="status-dot"></div>
                    <span>System Active</span>
                </div>
                <button class="btn btn-primary" onclick="toggleTheme()" style="width: 100%;">
                    🌙 Dark Mode
                </button>
            </div>
        </aside>

        <!-- MAIN CONTENT -->
        <main class="main">
            <!-- PAGE HEADER -->
            <div class="page-header" id="overview">
                <h1 class="page-title">Trading Dashboard</h1>
                <div class="header-controls">
                    <span class="badge badge-success">🟢 Running</span>
                    <span class="badge badge-warning">📄 Paper Mode</span>
                    <span class="text-small" id="last-update">Last updated: just now</span>
                </div>
            </div>

            <!-- SIGNAL BANNER -->
            <div class="signal-banner" id="signal-card">
                <div class="signal-banner-top">
                    <div class="signal-info">
                        <div class="signal-title">
                            <span id="signal-icon">📊</span>
                            <span id="signal-text">HOLD</span>
                        </div>
                        <div class="signal-subtitle" id="signal-reasoning">Waiting for analysis...</div>
                        <div class="signal-timestamp" id="signal-timestamp">—</div>
                    </div>
                </div>
                <div class="signal-grid" id="signal-metrics">
                    <div class="signal-metric">
                        <div class="signal-metric-label">Confidence</div>
                        <div class="signal-metric-value" id="signal-conf">-</div>
                    </div>
                    <div class="signal-metric">
                        <div class="signal-metric-label">Entry Price</div>
                        <div class="signal-metric-value" id="signal-entry">-</div>
                    </div>
                    <div class="signal-metric">
                        <div class="signal-metric-label">Stop Loss</div>
                        <div class="signal-metric-value" id="signal-sl">-</div>
                    </div>
                    <div class="signal-metric">
                        <div class="signal-metric-label">Take Profit</div>
                        <div class="signal-metric-value" id="signal-tp">-</div>
                    </div>
                </div>
            </div>

            <!-- METRICS GRID -->
            <div class="dashboard-grid">
                <div class="card">
                    <div class="card-header">
                        <span style="font-size: 18px;">📊</span>
                        <h3 class="card-title">Market Data</h3>
                    </div>
                    <div class="card-content">
                        <div class="metric-row">
                            <span class="metric-label">Current Price</span>
                            <span class="metric-value" id="current-price">-</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-label">24h High</span>
                            <span class="metric-value" id="high-24h">-</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-label">24h Low</span>
                            <span class="metric-value" id="low-24h">-</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-label">24h Change</span>
                            <span class="metric-value" id="change-24h">-</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-label">Status</span>
                            <span class="metric-value" id="market-status">-</span>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <span style="font-size: 18px;">💰</span>
                        <h3 class="card-title">Performance</h3>
                    </div>
                    <div class="card-content">
                        <div class="metric-row">
                            <span class="metric-label">Total P&L</span>
                            <span class="metric-value" id="total-pnl">-</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-label">Win Rate</span>
                            <span class="metric-value" id="win-rate">-</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-label">Total Trades</span>
                            <span class="metric-value" id="total-trades">-</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-label">Profitable</span>
                            <span class="metric-value metric-positive" id="profitable">-</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-label">Open Positions</span>
                            <span class="metric-value" id="open-pos">-</span>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <span style="font-size: 18px;">⚠️</span>
                        <h3 class="card-title">Risk Metrics</h3>
                    </div>
                    <div class="card-content">
                        <div class="metric-row">
                            <span class="metric-label">Sharpe Ratio</span>
                            <span class="metric-value" id="sharpe">-</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-label">Max Drawdown</span>
                            <span class="metric-value metric-negative" id="drawdown">-</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-label">Win/Loss Ratio</span>
                            <span class="metric-value" id="wl-ratio">-</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-label">Avg Win Size</span>
                            <span class="metric-value metric-positive" id="avg-win">-</span>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <span style="font-size: 18px;">🏥</span>
                        <h3 class="card-title">System Health</h3>
                    </div>
                    <div class="card-content" id="health-content">
                        <div class="loading">Checking...</div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <span style="font-size: 18px;">🤖</span>
                        <h3 class="card-title">LLM Providers</h3>
                    </div>
                    <div class="card-content" id="llm-providers-content">
                        <div class="loading">Loading provider metrics...</div>
                    </div>
                </div>
            </div>

            <!-- TRADES SECTION -->
            <div class="section-full" id="trades">
                <div class="section-title">📋 Recent Trades</div>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Signal</th>
                            <th>Entry</th>
                            <th>Exit</th>
                            <th>Qty</th>
                            <th>P&L</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody id="trades-body">
                        <tr>
                            <td colspan="7" class="loading">Loading trades...</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <!-- AGENT ANALYSIS SECTION -->
            <div class="section-full" id="analysis">
                <div class="section-title">🤖 Agent Analysis</div>
                <div id="agents-container" class="agent-grid">
                    <div class="loading" style="grid-column: 1/-1;">Loading agents...</div>
                </div>
            </div>

            <!-- PORTFOLIO SECTION -->
            <div class="section-full" id="portfolio">
                <div class="section-title">🎯 Portfolio Positions</div>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th>Size</th>
                            <th>Entry</th>
                            <th>Current</th>
                            <th>P&L</th>
                        </tr>
                    </thead>
                    <tbody id="portfolio-body">
                        <tr>
                            <td colspan="5" class="loading">No positions</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </main>
    </div>

    <script>
        let allTrades = [];

        function formatCurrency(val) {
            return '₹' + parseFloat(val || 0).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
        }

        function formatPercent(val) {
            return parseFloat(val || 0).toFixed(2) + '%';
        }

        function toggleTheme() {
            document.body.classList.toggle('dark-mode');
            localStorage.setItem('darkMode', document.body.classList.contains('dark-mode'));
        }

        function scrollToSection(id) {
            const element = document.getElementById(id);
            if (element) element.scrollIntoView({behavior: 'smooth'});
        }

        if (localStorage.getItem('darkMode') === 'true') {
            document.body.classList.add('dark-mode');
        }

        async function loadData() {
            try {
                // Parallel loading
                const [signal, market, metrics, risk, trades, agents, portfolio, health] = await Promise.all([
                    fetch('/api/latest-signal').then(r => r.json()).catch(() => ({})),
                    fetch('/api/market-data').then(r => r.json()).catch(() => ({})),
                    fetch('/metrics/trading').then(r => r.json()).catch(() => ({})),
                    fetch('/metrics/risk').then(r => r.json()).catch(() => ({})),
                    fetch('/api/recent-trades?limit=20').then(r => r.json()).catch(() => []),
                    fetch('/api/agent-status').then(r => r.json()).catch(() => ({})),
                    fetch('/api/portfolio').then(r => r.json()).catch(() => ({positions: []})),
                    fetch('/api/system-health').then(r => r.json()).catch(() => ({}))
                ]);

                updateSignal(signal);
                updateMarketData(market);
                updateMetrics(metrics);
                updateRisk(risk);
                displayTrades(trades);
                displayAgents(agents);
                displayPortfolio(portfolio);
                displayHealth(health);

                document.getElementById('last-update').textContent = 'Last updated: ' + new Date().toLocaleTimeString();
            } catch (error) {
                console.error('Load error:', error);
            }
        }

        function updateSignal(signal) {
            const card = document.getElementById('signal-card');
            const icon = {'BUY': '🚀', 'SELL': '📉', 'HOLD': '📊'}[signal.signal] || '📊';
            document.getElementById('signal-icon').textContent = icon;
            document.getElementById('signal-text').textContent = signal.signal || 'HOLD';
            document.getElementById('signal-reasoning').textContent = signal.reasoning || 'Analysis in progress';
            document.getElementById('signal-conf').textContent = signal.confidence ? formatPercent(signal.confidence) : '-';
            document.getElementById('signal-entry').textContent = signal.entryprice ? formatCurrency(signal.entryprice) : '-';
            document.getElementById('signal-sl').textContent = signal.stoploss ? formatCurrency(signal.stoploss) : '-';
            document.getElementById('signal-tp').textContent = signal.takeprofit ? formatCurrency(signal.takeprofit) : '-';
            card.className = 'signal-banner ' + (signal.signal || 'HOLD').toLowerCase();
        }

        function updateMarketData(market) {
            document.getElementById('current-price').textContent = market.currentprice ? formatCurrency(market.currentprice) : '-';
            document.getElementById('high-24h').textContent = market.high24h ? formatCurrency(market.high24h) : '-';
            document.getElementById('low-24h').textContent = market.low24h ? formatCurrency(market.low24h) : '-';
            const change = market.change24h || 0;
            const changeEl = document.getElementById('change-24h');
            changeEl.textContent = formatPercent(change);
            changeEl.className = 'metric-value ' + (change >= 0 ? 'metric-positive' : 'metric-negative');
            document.getElementById('market-status').textContent = market.marketopen ? '🟢 Open' : '🔴 Closed';
        }

        function updateMetrics(m) {
            document.getElementById('total-pnl').textContent = m.totalpnl ? formatCurrency(m.totalpnl) : '-';
            document.getElementById('win-rate').textContent = m.winrate ? formatPercent(m.winrate) : '-';
            document.getElementById('total-trades').textContent = m.totaltrades || 0;
            document.getElementById('profitable').textContent = m.profitabletrades || 0;
            document.getElementById('open-pos').textContent = m.openpositions || 0;
        }

        function updateRisk(r) {
            document.getElementById('sharpe').textContent = (r.sharperatio || 0).toFixed(2);
            document.getElementById('drawdown').textContent = formatPercent(r.maxdrawdown || 0);
            document.getElementById('wl-ratio').textContent = (r.winlossratio || 0).toFixed(2);
            document.getElementById('avg-win').textContent = r.avgwinsize ? formatCurrency(r.avgwinsize) : '-';
        }

        function displayTrades(trades) {
            const tbody = document.getElementById('trades-body');
            if (!trades || trades.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="loading">No trades yet</td></tr>';
                return;
            }
            let html = '';
            trades.forEach(t => {
                const pnl = t.pnl || 0;
                html += '<tr>' +
                    '<td>' + new Date(t.entrytimestamp).toLocaleTimeString() + '</td>' +
                    '<td><span class="badge-small badge-' + (t.signal || 'hold').toLowerCase() + '">' + (t.signal || 'HOLD') + '</span></td>' +
                    '<td>' + formatCurrency(t.entryprice || 0) + '</td>' +
                    '<td>' + (t.exitprice ? formatCurrency(t.exitprice) : '-') + '</td>' +
                    '<td>' + (t.quantity || 0) + '</td>' +
                    '<td style="color: ' + (pnl >= 0 ? '#10b981' : '#ef4444') + '">' + formatCurrency(pnl) + '</td>' +
                    '<td><span class="badge-small badge-' + (t.status || 'open').toLowerCase() + '">' + (t.status || 'OPEN') + '</span></td>' +
                    '</tr>';
            });
            tbody.innerHTML = html;
        }

        function displayAgents(agents) {
            const container = document.getElementById('agents-container');
            if (!agents.agents || Object.keys(agents.agents).length === 0) {
                container.innerHTML = '<div class="loading" style="grid-column: 1/-1;">No agents active</div>';
                return;
            }
            let html = '';
            Object.entries(agents.agents).forEach(([name, agent]) => {
                html += '<div class="agent-card">' +
                    '<div class="agent-name">' + name.replace(/_/g, ' ').toUpperCase() + '</div>' +
                    '<div class="agent-metric">' +
                    '<span class="agent-label">Status</span>' +
                    '<span class="agent-value">🟢 Active</span>' +
                    '</div>' +
                    '</div>';
            });
            container.innerHTML = html;
        }

        function displayPortfolio(portfolio) {
            const tbody = document.getElementById('portfolio-body');
            if (!portfolio.positions || portfolio.positions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="loading">No positions</td></tr>';
                return;
            }
            let html = '';
            portfolio.positions.forEach(p => {
                const pnl = p.pnl || 0;
                html += '<tr>' +
                    '<td>' + p.symbol + '</td>' +
                    '<td>' + p.size + '</td>' +
                    '<td>' + formatCurrency(p.entry) + '</td>' +
                    '<td>' + formatCurrency(p.current) + '</td>' +
                    '<td style="color: ' + (pnl >= 0 ? '#10b981' : '#ef4444') + ';">' + formatCurrency(pnl) + '</td>' +
                    '</tr>';
            });
            tbody.innerHTML = html;
        }

        function displayHealth(health) {
            const container = document.getElementById('health-content');
            if (!health.components) {
                container.innerHTML = '<div class="loading">Unavailable</div>';
                return;
            }
            let html = '';
            Object.entries(health.components).forEach(([name, comp]) => {
                const color = comp.status === 'healthy' ? '#10b981' : '#f59e0b';
                html += '<div class="metric-row"><span class="metric-label">' + name + '</span><span class="metric-value" style="color: ' + color + ';">' + (comp.status || 'unknown').toUpperCase() + '</span></div>';
            });
            container.innerHTML = html;
        }

        function exportTrades() {
            if (allTrades.length === 0) {alert('No trades'); return;}
            const csv = 'Time,Signal,Entry,Exit,Qty,PnL,Status\\n' + allTrades.map(t => `"${new Date(t.entrytimestamp).toLocaleString()}",${t.signal},${t.entryprice},${t.exitprice || '-'},${t.quantity},${t.pnl || 0},${t.status}`).join('\\n');
            const blob = new Blob([csv], {type: 'text/csv'});
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = 'trades_' + new Date().toISOString().split('T')[0] + '.csv'; a.click();
        }

        // Resilient loader: preserve last-known data and apply per-endpoint backoff
        const LAST_GOOD_KEY = 'dashboard:lastGood';
        let lastGood = JSON.parse(localStorage.getItem(LAST_GOOD_KEY) || '{}');
        const endpointState = {
            signal: {failures: 0, skipUntil: 0},
            market: {failures: 0, skipUntil: 0},
            metrics: {failures: 0, skipUntil: 0},
            risk: {failures: 0, skipUntil: 0},
            trades: {failures: 0, skipUntil: 0},
            agents: {failures: 0, skipUntil: 0},
            portfolio: {failures: 0, skipUntil: 0},
            health: {failures: 0, skipUntil: 0}
        };
        let globalFailureCount = 0;
        let currentInterval = 5000;
        let loadTimeout = null;

        function showDegradedBanner(show, message) {
            let banner = document.getElementById('degraded-banner');
            if (!banner) return;
            if (show) {
                banner.style.display = 'block';
                banner.textContent = message || 'System degraded — displaying last-known data where applicable.';
            } else {
                banner.style.display = 'none';
                banner.textContent = '';
            }
        }

        async function fetchWithBackoff(url, key, fallback) {
            const state = endpointState[key];
            if (state && state.skipUntil > Date.now()) {
                // return stale data or fallback
                return lastGood[key] || fallback || {};
            }
            try {
                const res = await fetch(url);
                if (!res.ok) throw new Error('HTTP ' + res.status);
                const json = await res.json();
                state.failures = 0;
                state.skipUntil = 0;
                return json;
            } catch (err) {
                state.failures = (state.failures || 0) + 1;
                const backoffMs = Math.min(60000, 5000 * Math.pow(2, state.failures - 1));
                state.skipUntil = Date.now() + backoffMs;
                return Object.assign({}, fallback || {}, {__error: true, __errorMessage: err.message});
            }
        }

        async function loadDataOnce() {
            try {
                const results = await Promise.all([
                    fetchWithBackoff('/api/latest-signal', 'signal', {}),
                    fetchWithBackoff('/api/market-data', 'market', {}),
                    fetchWithBackoff('/metrics/trading', 'metrics', {}),
                    fetchWithBackoff('/metrics/risk', 'risk', {}),
                    fetchWithBackoff('/api/recent-trades?limit=20', 'trades', []),
                    fetchWithBackoff('/api/agent-status', 'agents', {}),
                    fetchWithBackoff('/api/portfolio', 'portfolio', {positions: []}),
                    fetchWithBackoff('/api/system-health', 'health', {})
                ]);

                const [signal, market, metrics, risk, trades, agents, portfolio, health] = results;
                const hadError = results.some(r => r && r.__error);

                const finalSignal = (signal && !signal.__error) ? signal : (lastGood.signal || {});
                const finalMarket = (market && !market.__error) ? market : (lastGood.market || {});
                const finalMetrics = (metrics && !metrics.__error) ? metrics : (lastGood.metrics || {});
                const finalRisk = (risk && !risk.__error) ? risk : (lastGood.risk || {});
                const finalTrades = (trades && !trades.__error && Array.isArray(trades)) ? trades : (lastGood.trades || []);
                const finalAgents = (agents && !agents.__error) ? agents : (lastGood.agents || {});
                const finalPortfolio = (portfolio && !portfolio.__error) ? portfolio : (lastGood.portfolio || {positions: []});
                const finalHealth = (health && !health.__error) ? health : (lastGood.health || {});

                updateSignal(finalSignal);
                updateMarketData(finalMarket);
                updateMetrics(finalMetrics);
                updateRisk(finalRisk);
                displayTrades(finalTrades);
                displayAgents(finalAgents);
                displayPortfolio(finalPortfolio);
                displayHealth(finalHealth);

                // update lastGood selectively
                if (!signal.__error) lastGood.signal = signal;
                if (!market.__error) lastGood.market = market;
                if (!metrics.__error) lastGood.metrics = metrics;
                if (!risk.__error) lastGood.risk = risk;
                if (!(trades && trades.__error)) lastGood.trades = trades;
                if (!agents.__error) lastGood.agents = agents;
                if (!portfolio.__error) lastGood.portfolio = portfolio;
                if (!health.__error) lastGood.health = health;
                localStorage.setItem(LAST_GOOD_KEY, JSON.stringify(lastGood));

                document.getElementById('last-update').textContent = 'Last updated: ' + new Date().toLocaleTimeString();

                if (hadError) {
                    globalFailureCount = Math.min(10, globalFailureCount + 1);
                    showDegradedBanner(true, 'Some services are unavailable. Displaying last-known data.');
                } else {
                    globalFailureCount = 0;
                    showDegradedBanner(false);
                }

            } catch (error) {
                console.error('Unexpected loader error:', error);
                // treat as failure
                globalFailureCount = Math.min(10, globalFailureCount + 1);
                showDegradedBanner(true, 'Unexpected error. Displaying last-known data.');
            } finally {
                // adjust interval
                if (globalFailureCount === 0) currentInterval = 5000;
                else if (globalFailureCount <= 2) currentInterval = 15000;
                else currentInterval = 60000;

                if (loadTimeout) clearTimeout(loadTimeout);
                loadTimeout = setTimeout(loadDataOnce, currentInterval);
            }
        }

        // Create a small, visible banner (initially hidden)
        if (!document.getElementById('degraded-banner')) {
            const header = document.querySelector('.page-header .header-controls');
            if (header) {
                const banner = document.createElement('div');
                banner.id = 'degraded-banner';
                banner.style.display = 'none';
                banner.style.background = '#fffbeb';
                banner.style.color = '#92400e';
                banner.style.padding = '8px';
                banner.style.borderRadius = '6px';
                banner.style.marginTop = '10px';
                banner.style.fontWeight = '600';
                header.parentNode.insertBefore(banner, header.nextSibling);
            }
        }

        // Kick off the improved loader
        loadDataOnce();
        // Old interval removed in favor of adaptive scheduler

        // LLM metrics polling - separate, updates every 30s
        async function loadLLMMetrics() {
            try {
                const res = await fetch('/api/metrics/llm');
                if (!res.ok) throw new Error('HTTP ' + res.status);
                const data = await res.json();
                updateLLMProviders(data);
            } catch (e) {
                console.error('Failed to load LLM metrics:', e);
                const container = document.getElementById('llm-providers-content');
                if (container) container.innerHTML = '<div class="loading">Unable to load provider metrics</div>';
            }
        }

        function updateLLMProviders(metrics) {
            const container = document.getElementById('llm-providers-content');
            if (!container) return;
            try {
                if (!metrics || !metrics.providers) {
                    container.innerHTML = '<div class="loading">No provider metrics available</div>';
                    return;
                }
                let html = '<div style="display:flex;flex-direction:column;gap:8px;">';
                metrics.providers.forEach(p => {
                    const color = (p.status === 'healthy') ? '#10b981' : (p.status === 'rate_limited' ? '#f59e0b' : '#ef4444');
                    html += `<div style="display:flex;justify-content:space-between;align-items:center;padding:6px;border-radius:6px;background:#fff;">` +
                        `<div style="font-weight:600">${p.name}</div>` +
                        `<div style="text-align:right">` +
                        `<div style="font-size:12px;color:${color}">${(p.status||'unknown').toUpperCase()}</div>` +
                        `<div style="font-size:12px;color:#6b7280">Tokens: ${p.tokens_today || 0}${p.daily_limit ? ' / ' + p.daily_limit : ''} (${p.usage_percent || 0}%)</div>` +
                        `</div>` +
                        `</div>`;
                });
                html += '</div>';
                container.innerHTML = html;

                // summary badge
                if (metrics.summary) {
                    const headerBadge = document.querySelector('.page-header .header-controls .badge');
                    // Add or update a small indicator if health below threshold
                    const healthPercent = metrics.summary.health_percentage || 0;
                    let existing = document.getElementById('llm-health-badge');
                    if (!existing) {
                        const b = document.createElement('span');
                        b.id = 'llm-health-badge';
                        b.className = 'badge badge-info';
                        b.style.marginLeft = '8px';
                        b.textContent = `LLM Health: ${healthPercent}%`;
                        const header = document.querySelector('.page-header .header-controls');
                        if (header) header.appendChild(b);
                    } else {
                        existing.textContent = `LLM Health: ${healthPercent}%`;
                    }
                }
            } catch (err) {
                console.error('Error rendering LLM metrics', err);
                container.innerHTML = '<div class="loading">Error rendering metrics</div>';
            }
        }

        // Start polling LLM metrics every 30s
        loadLLMMetrics();
        setInterval(loadLLMMetrics, 30000);
    </script>
</body>
</html>
"""

# ============ API ENDPOINTS ============

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTML_TEMPLATE


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/metrics/llm")
async def get_llm_metrics():
    """Get LLM provider usage metrics and health status"""
    try:
        from agents.llm_provider_manager import get_llm_manager
        
        manager = get_llm_manager()
        if not manager:
            return {
                "error": "LLM manager not initialized",
                "providers": []
            }
        
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "providers": []
        }
        
        # Get metrics for each provider (handle dicts and objects)
        for provider_name, provider_info in manager.providers.items():
            def _g(key, default=None):
                if hasattr(provider_info, 'get'):
                    return provider_info.get(key, default)
                return getattr(provider_info, key, default)

            last_check = _g('last_check', None)
            if hasattr(last_check, 'isoformat'):
                last_check = last_check.isoformat()

            provider_metrics = {
                "name": provider_name,
                "priority": _g('priority', 99),
                "status": _g('status', 'unknown'),
                "tokens_today": _g('tokens_today', 0),
                "daily_limit": _g('daily_limit', 0),
                "usage_percent": 0,
                "last_check": last_check,
                "consecutive_failures": _g('consecutive_failures', 0),
                "total_calls": _g('total_calls', 0)
            }
            
            # Calculate usage percentage
            if provider_metrics['daily_limit'] > 0:
                provider_metrics['usage_percent'] = round(
                    (provider_metrics['tokens_today'] / provider_metrics['daily_limit']) * 100, 
                    2
                )
            
            metrics['providers'].append(provider_metrics)
        
        # Sort by priority
        metrics['providers'].sort(key=lambda p: p['priority'])
        
        # Add summary
        total_providers = len(metrics['providers'])
        healthy_providers = sum(1 for p in metrics['providers'] if p['status'] == 'healthy')
        total_tokens = sum(p['tokens_today'] for p in metrics['providers'])
        
        metrics['summary'] = {
            "total_providers": total_providers,
            "healthy_providers": healthy_providers,
            "unhealthy_providers": total_providers - healthy_providers,
            "total_tokens_today": total_tokens,
            "health_percentage": round((healthy_providers / total_providers * 100) if total_providers > 0 else 0, 2)
        }
        
        return add_camel_aliases(metrics)
        
    except Exception as e:
        logger.error(f"Error getting LLM metrics: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@app.get("/api/latest-signal")
async def get_latest_signal() -> Dict[str, Any]:
    """Get the latest trading signal."""
    try:
        mongo_client = get_mongo_client()
        db = mongo_client[settings.mongodb_db_name]
        trades_collection = get_collection(db, "trades_executed")
        
        # Get the most recent trade decision (even if not executed)
        latest_trade = trades_collection.find_one(
            sort=[("entry_timestamp", -1)]
        )
        
        if latest_trade:
            resp = {
                "signal": latest_trade.get("signal", "HOLD"),
                "position_size": latest_trade.get("quantity", 0),
                "entry_price": latest_trade.get("entry_price", 0),
                "stop_loss": latest_trade.get("stop_loss", 0),
                "take_profit": latest_trade.get("take_profit", 0),
                "confidence": 0.65,  # Default confidence
                "reasoning": "Based on multi-agent analysis"
            }
            return add_camel_aliases(resp)
        
        # If no trades, return HOLD signal
        resp = {
            "signal": "HOLD",
            "position_size": 0,
            "entry_price": 0,
            "stop_loss": 0,
            "take_profit": 0,
            "confidence": 0.0,
            "reasoning": "Waiting for market analysis"
        }
        return add_camel_aliases(resp)
    except Exception as e:
        logger.error(f"Error getting latest signal: {e}")
        resp = {
            "signal": "HOLD",
            "reasoning": f"Error: {str(e)}"
        }
        return add_camel_aliases(resp)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# ============ API ENDPOINTS ============

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTML_TEMPLATE

@app.get("/api/market-data")
async def get_market_data() -> Dict[str, Any]:
    """Get current market data."""
    try:
        current_price = None
        
        # Try to get price from Redis first
        if marketmemory and marketmemory._redis_available:
            try:
                instrument_key = settings.instrument_symbol.replace("-", "").replace(" ", "").upper()
                current_price = marketmemory.get_current_price(instrument_key)
            except Exception as e:
                logger.debug(f"Redis price fetch failed: {e}")
        
        # If Redis not available, try to get from MongoDB OHLC collection
        if not current_price:
            try:
                mongo_client = get_mongo_client()
                db = mongo_client[settings.mongodb_db_name]
                ohlc_collection = get_collection(db, "ohlc_history")
                last_ohlc = ohlc_collection.find_one(
                    {"instrument": settings.instrument_symbol},
                    sort=[("timestamp", -1)]
                )
                if last_ohlc and last_ohlc.get("close"):
                    current_price = last_ohlc["close"]
            except Exception as e:
                logger.debug(f"Could not get price from MongoDB: {e}")
        
        # If still no price, try to get from latest agent decision
        if not current_price:
            try:
                mongo_client = get_mongo_client()
                db = mongo_client[settings.mongodb_db_name]
                analysis_collection = get_collection(db, "agent_decisions")
                latest = analysis_collection.find_one(
                    {"instrument": settings.instrument_symbol},
                    sort=[("timestamp", -1)]
                )
                if latest and latest.get("current_price"):
                    current_price = latest["current_price"]
            except Exception as e:
                logger.debug(f"Could not get price from agent decisions: {e}")
        
        # Check if market is open
        now = datetime.now()
        try:
            open_time = datetime.strptime(settings.market_open_time, "%H:%M:%S").time()
            close_time = datetime.strptime(settings.market_close_time, "%H:%M:%S").time()
        except (ValueError, AttributeError):
            open_time = datetime.strptime("09:15:00", "%H:%M:%S").time()
            close_time = datetime.strptime("15:30:00", "%H:%M:%S").time()
        
        # Check market hours - for 24/7 markets (crypto), always open
        if hasattr(settings, 'market_24_7') and settings.market_24_7:
            market_open = True
        else:
            market_open = (now.weekday() < 5 and open_time <= now.time() <= close_time)
        
        # Determine data source from settings
        data_source_map = {
            "CRYPTO": "Binance WebSocket",
            "ZERODHA": "Zerodha Kite",
            "FINNHUB": "Finnhub"
        }
        data_source = data_source_map.get(getattr(settings, 'data_source', ''), "MongoDB/Redis")
        
        # Get additional market data for crypto/futures (if available)
        futures_price = None
        funding_rate = None
        open_interest = None
        volume_24h = None
        high_24h = None
        low_24h = None
        change_24h = None
        
        # Get futures data from Redis if available
        if marketmemory:
            instrument_key = settings.instrument_symbol.replace('-', '').replace(' ', '').upper()
            futures_data = marketmemory.get_futures_data(instrument_key)
            if futures_data:
                futures_price = futures_data.get("futures_price")
                funding_rate = futures_data.get("funding_rate")
                open_interest = futures_data.get("open_interest")
                volume_24h = futures_data.get("volume")
                high_24h = futures_data.get("high_24h")
                low_24h = futures_data.get("low_24h")
                change_24h = futures_data.get("price_change_24h")
        
        # Note: Return data in camelCase to match frontend expectations
        return {
            "currentprice": current_price,
            "futuresprice": futures_price,
            "fundingrate": funding_rate,
            "openinterest": open_interest,
            "volume24h": volume_24h,
            "high24h": high_24h,
            "low24h": low_24h,
            "change24h": change_24h,
            "datasource": data_source,
            "instrumentname": getattr(settings, 'instrument_name', 'Unknown'),
            "instrumentsymbol": settings.instrument_symbol,
            "marketopen": market_open,
            "redisavailable": marketmemory._redis_available if marketmemory else False,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting market data: {e}", exc_info=True)
        return {
            "currentprice": None,
            "datasource": "Error",
            "marketopen": False,
            "redisavailable": False
        }


@app.get("/api/recent-trades")
async def get_recent_trades(limit: int = Query(10, ge=1, le=100)) -> List[Dict[str, Any]]:
    """Get recent trades."""
    try:
        mongo_client = get_mongo_client()
        db = mongo_client[settings.mongodb_db_name]
        trades_collection = get_collection(db, "trades_executed")
        
        trades = list(trades_collection.find(
            {},
            sort=[("entry_timestamp", -1)]
        ).limit(limit))
        
        # Convert ObjectId to string for JSON serialization and add aliases
        for i, trade in enumerate(trades):
            if "_id" in trade:
                trade["_id"] = str(trade["_id"])
            trades[i] = add_camel_aliases(trade)
        
        return trades
    except Exception as e:
        logger.error(f"Error getting recent trades: {e}")
        return []


@app.get("/metrics/trading")
async def get_trading_metrics() -> Dict[str, Any]:
    """Get trading performance metrics."""
    try:
        mongo_client = get_mongo_client()
        db = mongo_client[settings.mongodb_db_name]
        trades_collection = get_collection(db, "trades_executed")
        
        # Get all trades
        all_trades = list(trades_collection.find({}))
        closed_trades = [t for t in all_trades if t.get("status") == "CLOSED"]
        open_trades = [t for t in all_trades if t.get("status") == "OPEN"]
        
        if not closed_trades:
            return add_camel_aliases({
                "total_trades": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "average_pnl": 0,
                "open_positions": len(open_trades)
            })
        
        profitable_trades = sum(1 for t in closed_trades if t.get("pnl", 0) > 0)
        total_pnl = sum(t.get("pnl", 0) for t in closed_trades)
        
        return add_camel_aliases({
            "total_trades": len(closed_trades),
            "profitable_trades": profitable_trades,
            "win_rate": (profitable_trades / len(closed_trades) * 100) if closed_trades else 0,
            "total_pnl": total_pnl,
            "average_pnl": total_pnl / len(closed_trades) if closed_trades else 0,
            "open_positions": len(open_trades)
        })
    except Exception as e:
        logger.error(f"Error getting trading metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics/risk")
async def get_risk_metrics() -> Dict[str, Any]:
    """Get risk metrics."""
    try:
        mongo_client = get_mongo_client()
        db = mongo_client[settings.mongodb_db_name]
        trades_collection = get_collection(db, "trades_executed")

        # Get all closed trades for risk calculation
        closed_trades = list(trades_collection.find({"status": "CLOSED"}))

        if not closed_trades:
            return {
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "win_loss_ratio": 0.0,
                "avg_win_size": 0.0
            }

        # Calculate basic risk metrics
        profitable_trades = [t for t in closed_trades if t.get("pnl", 0) > 0]
        losing_trades = [t for t in closed_trades if t.get("pnl", 0) < 0]

        win_loss_ratio = len(profitable_trades) / len(losing_trades) if losing_trades else 0
        avg_win_size = sum(t.get("pnl", 0) for t in profitable_trades) / len(profitable_trades) if profitable_trades else 0

        # Calculate drawdown (simplified)
        cumulative_pnl = 0
        peak = 0
        max_drawdown = 0

        for trade in closed_trades:
            cumulative_pnl += trade.get("pnl", 0)
            peak = max(peak, cumulative_pnl)
            drawdown = peak - cumulative_pnl
            max_drawdown = max(max_drawdown, drawdown)

        # Sharpe ratio (simplified - would need daily returns for proper calculation)
        total_pnl = sum(t.get("pnl", 0) for t in closed_trades)
        pnl_std = sum((t.get("pnl", 0) - (total_pnl / len(closed_trades)))**2 for t in closed_trades) / len(closed_trades)
        pnl_std = pnl_std**0.5 if pnl_std > 0 else 0
        sharpe_ratio = (total_pnl / len(closed_trades)) / pnl_std if pnl_std > 0 else 0

        return {
            "sharpe_ratio": round(sharpe_ratio, 2),
            "max_drawdown": round(max_drawdown, 2),
            "win_loss_ratio": round(win_loss_ratio, 2),
            "avg_win_size": round(avg_win_size, 2)
        }
    except Exception as e:
        logger.error(f"Error getting risk metrics: {e}")
        return {
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "win_loss_ratio": 0.0,
            "avg_win_size": 0.0
        }


@app.get("/api/latest-analysis")
async def get_latest_analysis() -> Dict[str, Any]:
    """Get latest agent analysis for the current instrument."""
    try:
        mongo_client = get_mongo_client()
        db = mongo_client[settings.mongodb_db_name]
        analysis_collection = get_collection(db, "agent_decisions")
        trades_collection = get_collection(db, "trades_executed")
        
        # Filter by current instrument to avoid showing old data from other instruments
        instrument_filter = {"instrument": settings.instrument_symbol}
        
        # First, try to get from agent_decisions collection (has all analysis runs)
        latest_analysis = analysis_collection.find_one(
            instrument_filter,
            sort=[("timestamp", -1)]
        )
        
        if latest_analysis and latest_analysis.get("agent_decisions"):
            # CRITICAL FIX: Parse agent_decisions if it's stored as a string
            agent_decisions = latest_analysis.get("agent_decisions")
            if isinstance(agent_decisions, str):
                try:
                    # Parse the stringified dict
                    import ast
                    agent_decisions = ast.literal_eval(agent_decisions)
                except (ValueError, SyntaxError) as e:
                    logger.error(f"Failed to parse agent_decisions string: {e}")
                    agent_decisions = {}
            
            # Get portfolio manager output for scores
            portfolio_output = agent_decisions.get("portfolio_manager", {}) if isinstance(agent_decisions, dict) else {}
            
            # Extract scores, handling None/empty cases
            bullish_score = portfolio_output.get("bullish_score")
            bearish_score = portfolio_output.get("bearish_score")
            
            # Try to parse as float if they're strings or None
            try:
                if bullish_score is not None:
                    bullish_score = float(bullish_score)
                else:
                    bullish_score = 0.5
            except (ValueError, TypeError):
                bullish_score = 0.5
            
            try:
                if bearish_score is not None:
                    bearish_score = float(bearish_score)
                else:
                    bearish_score = 0.6
            except (ValueError, TypeError):
                bearish_score = 0.6
            
            # Parse agent_explanations if it's a string
            agent_explanations = latest_analysis.get("agent_explanations", [])
            if isinstance(agent_explanations, str):
                try:
                    import ast
                    agent_explanations = ast.literal_eval(agent_explanations)
                except:
                    agent_explanations = []
            
            resp = {
                "agents": agent_decisions,
                "timestamp": latest_analysis.get("timestamp"),
                "final_signal": latest_analysis.get("final_signal", "HOLD"),
                "trend_signal": latest_analysis.get("trend_signal", "NEUTRAL"),
                "current_price": latest_analysis.get("current_price"),
                "bullish_score": bullish_score,
                "bearish_score": bearish_score,
                "agent_explanations": agent_explanations,
                "executive_summary": latest_analysis.get("executive_summary", "")
            }
            return add_camel_aliases(resp)
        
        # Fallback: Get most recent trade with agent decisions
        latest_trade = trades_collection.find_one(
            {"agent_decisions": {"$exists": True}},
            sort=[("entry_timestamp", -1)]
        )
        
        if latest_trade and latest_trade.get("agent_decisions"):
            agent_decisions = latest_trade.get("agent_decisions")
            if isinstance(agent_decisions, str):
                try:
                    import ast
                    agent_decisions = ast.literal_eval(agent_decisions)
                except:
                    agent_decisions = {}
            
            resp = {
                "agents": agent_decisions,
                "timestamp": latest_trade.get("entry_timestamp"),
                "final_signal": latest_trade.get("signal", "HOLD"),
                "trend_signal": latest_trade.get("trend_signal", "NEUTRAL")
            }
            return add_camel_aliases(resp)
        
        return add_camel_aliases({"agents": {}, "message": "No analysis available yet. Agents are running every 60 seconds."})
    except Exception as e:
        logger.error(f"Error getting latest analysis: {e}", exc_info=True)
        return add_camel_aliases({"agents": {}, "error": str(e)})


@app.get("/api/portfolio")
async def get_portfolio() -> Dict[str, Any]:
    """Get current portfolio positions."""
    try:
        mongo_client = get_mongo_client()
        db = mongo_client[settings.mongodb_db_name]
        trades_collection = get_collection(db, "trades_executed")

        # Get all open positions
        open_trades = list(trades_collection.find({"status": "OPEN"}))

        positions = []
        total_value = 0

        for trade in open_trades:
            symbol = trade.get("instrument", settings.instrument_symbol)
            size = trade.get("quantity", 0)
            entry_price = trade.get("entry_price", 0)

            # Get current price
            current_price = marketmemory.get_current_price(symbol.replace("-", "").replace(" ", "").upper())
            if not current_price:
                # Fallback to entry price if no current price available
                current_price = entry_price

            pnl = (current_price - entry_price) * size
            total_value += (current_price * abs(size))

            positions.append({
                "symbol": symbol,
                "size": size,
                "entry": entry_price,
                "current": current_price,
                "pnl": pnl
            })

        resp = {
            "total_value": total_value,
            "positions": [add_camel_aliases(p) for p in positions]
        }
        return resp
    except Exception as e:
        logger.error(f"Error getting portfolio: {e}")
        return {
            "total_value": 0,
            "positions": []
        }


@app.get("/api/alerts")
async def get_alerts(limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent trade alerts."""
    try:
        mongo_client = get_mongo_client()
        db = mongo_client[settings.mongodb_db_name]
        alerts_collection = get_collection(db, "alerts")

        # Get recent alerts
        alerts = list(alerts_collection.find(
            {},
            sort=[("timestamp", -1)]
        ).limit(limit))

        # Convert ObjectId to string for JSON serialization
        for alert in alerts:
            if "_id" in alert:
                alert["_id"] = str(alert["_id"])

        # If no alerts in collection, generate some based on recent trades
        if not alerts:
            trades_collection = get_collection(db, "trades_executed")
            recent_trades = list(trades_collection.find(
                {},
                sort=[("entry_timestamp", -1)]
            ).limit(5))

            alerts = []
            for trade in recent_trades:
                pnl = trade.get("pnl", 0)
                if pnl > 1000:
                    alerts.append({
                        "type": "success",
                        "message": f"Large profit on {trade.get('instrument', 'Unknown')}: ₹{pnl:.2f}",
                        "timestamp": trade.get("entry_timestamp", datetime.now().isoformat())
                    })
                elif pnl < -1000:
                    alerts.append({
                        "type": "warning",
                        "message": f"Large loss on {trade.get('instrument', 'Unknown')}: ₹{pnl:.2f}",
                        "timestamp": trade.get("entry_timestamp", datetime.now().isoformat())
                    })

        return alerts
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        return []


@app.get("/api/system-health")
async def get_system_health() -> Dict[str, Any]:
    """Get comprehensive system health check."""
    try:
        return healthchecker.check_all()
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.get("/api/agent-status")
async def get_agent_status() -> Dict[str, Any]:
    """Get current agent status and activity with staleness awareness."""
    try:
        mongo_client = get_mongo_client()
        db = mongo_client[settings.mongodb_db_name]
        analysis_collection = get_collection(db, "agent_decisions")

        latest_analysis = analysis_collection.find_one(
            sort=[("timestamp", -1)]
        )

        # State flags
        agents_info: Dict[str, Any] = {}
        status_label = "initializing"
        status_message = "Waiting for first analysis"
        last_analysis_ts: Optional[datetime] = None

        if latest_analysis:
            analysis_time = latest_analysis.get("timestamp")
            if isinstance(analysis_time, str):
                try:
                    analysis_time = datetime.fromisoformat(analysis_time.replace('Z', '+00:00'))
                except ValueError:
                    analysis_time = None
            if isinstance(analysis_time, datetime):
                last_analysis_ts = analysis_time

        # Determine staleness windows
        now = datetime.now()
        active_window_seconds = 900  # 15 minutes window for "active"
        initializing_window_seconds = 120  # 2 minutes grace after startup if no data yet

        if last_analysis_ts:
            seconds_since = (now - last_analysis_ts.replace(tzinfo=None)).total_seconds()
            if seconds_since <= active_window_seconds:
                status_label = "active"
                status_message = "Agents are running analysis"
            else:
                status_label = "stale"
                status_message = "Analysis is stale; waiting for next cycle"
        else:
            # No analysis yet; treat as initializing for a brief window
            status_label = "initializing"
            status_message = "Agents are starting; waiting for first analysis"

        # Build per-agent info from latest analysis if present
        agent_decisions = latest_analysis.get("agent_decisions", {}) if latest_analysis else {}
        if isinstance(agent_decisions, dict) and agent_decisions:
            for agent_name, agent_data in agent_decisions.items():
                agents_info[agent_name] = {
                    "name": agent_name.replace("_", " ").title(),
                    "status": status_label if status_label != "initializing" else "active",
                    "last_update": last_analysis_ts.isoformat() if last_analysis_ts else None,
                    "data": agent_data
                }

        # Fallback default agents when none available
        if not agents_info:
            default_agents = [
                "technical_agent", "fundamental_agent", "sentiment_agent",
                "macro_agent", "portfolio_manager", "risk_agent",
                "execution_agent", "learning_agent"
            ]
            for agent_name in default_agents:
                agents_info[agent_name] = {
                    "name": agent_name.replace("_", " ").title(),
                    "status": status_label,
                    "last_update": last_analysis_ts.isoformat() if last_analysis_ts else None,
                    "data": {"message": status_message}
                }

        return {
            "status": status_label,
            "agents": agents_info,
            "last_analysis": last_analysis_ts.isoformat() if last_analysis_ts else None,
            "message": status_message
        }
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        return {
            "status": "error",
            "agents": {},
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)