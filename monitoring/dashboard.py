"""Monitoring dashboard for real-time metrics with web UI."""

import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Any, List
from datetime import datetime, timedelta
from mongodb_schema import get_mongo_client, get_collection
from config.settings import settings
from data.market_memory import MarketMemory
from monitoring.system_health import SystemHealthChecker
from agents.llm_provider_manager import get_llm_manager

logger = logging.getLogger(__name__)

app = FastAPI(title="Trading System Dashboard")

# Add cache control middleware
class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

app.add_middleware(CacheControlMiddleware)

# Initialize market memory for real-time data
# Reinitialize to pick up Redis connection if it becomes available
market_memory = MarketMemory()
health_checker = SystemHealthChecker()

# Force reinitialize MarketMemory in health checker to ensure fresh connection
health_checker.market_memory = MarketMemory()


@app.get("/", response_class=HTMLResponse)
async def dashboard_home():
    """Main dashboard HTML page."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>GenAI Trading System Dashboard</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #333;
                padding: 20px;
                min-height: 100vh;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
            }
            .header {
                background: white;
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 20px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            .header h1 {
                color: #667eea;
                margin-bottom: 10px;
            }
            .status-badge {
                display: inline-block;
                padding: 5px 15px;
                border-radius: 20px;
                font-size: 14px;
                font-weight: bold;
                margin-left: 10px;
            }
            .status-running { background: #10b981; color: white; }
            .status-stopped { background: #ef4444; color: white; }
            .status-paper { background: #f59e0b; color: white; }
            .grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-bottom: 20px;
            }
            .card {
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            .card h2 {
                color: #667eea;
                margin-bottom: 15px;
                font-size: 18px;
                border-bottom: 2px solid #667eea;
                padding-bottom: 10px;
            }
            .metric {
                display: flex;
                justify-content: space-between;
                padding: 10px 0;
                border-bottom: 1px solid #e5e7eb;
            }
            .metric:last-child { border-bottom: none; }
            .metric-label { color: #6b7280; }
            .metric-value {
                font-weight: bold;
                font-size: 18px;
            }
            .positive { color: #10b981; }
            .negative { color: #ef4444; }
            .neutral { color: #6b7280; }
            .signal-card {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 25px;
                border-radius: 10px;
                margin-bottom: 20px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.2);
            }
            .signal-buy {
                background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            }
            .signal-sell {
                background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            }
            .signal-hold {
                background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%);
            }
            .signal-title {
                font-size: 24px;
                margin-bottom: 15px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .signal-details {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 15px;
                margin-top: 15px;
            }
            .signal-detail {
                background: rgba(255,255,255,0.2);
                padding: 10px;
                border-radius: 5px;
            }
            .signal-detail-label {
                font-size: 12px;
                opacity: 0.9;
                margin-bottom: 5px;
            }
            .signal-detail-value {
                font-size: 20px;
                font-weight: bold;
            }
            .trades-table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }
            .trades-table th {
                background: #667eea;
                color: white;
                padding: 12px;
                text-align: left;
                font-weight: 600;
            }
            .trades-table td {
                padding: 12px;
                border-bottom: 1px solid #e5e7eb;
            }
            .trades-table tr:hover {
                background: #f9fafb;
            }
            .badge {
                display: inline-block;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            .badge-open { background: #dbeafe; color: #1e40af; }
            .badge-closed { background: #d1fae5; color: #065f46; }
            .badge-buy { background: #10b981; color: white; }
            .badge-sell { background: #ef4444; color: white; }
            .refresh-btn {
                background: #667eea;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 14px;
                margin-top: 10px;
            }
            .refresh-btn:hover {
                background: #5568d3;
            }
            .loading {
                text-align: center;
                padding: 20px;
                color: #6b7280;
            }
            .agent-output {
                background: #f9fafb;
                padding: 10px;
                border-radius: 5px;
                margin: 5px 0;
                font-size: 13px;
            }
            .agent-name {
                font-weight: bold;
                color: #667eea;
                margin-bottom: 5px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 GenAI Trading System Dashboard - <span id="header-instrument">Loading...</span>
                    <span id="status-badge" class="status-badge status-running">RUNNING</span>
                    <span id="paper-badge" class="status-badge status-paper">PAPER MODE</span>
                </h1>
                <p>Real-time trading system monitoring and trade suggestions</p>
                <p style="margin-top: 10px; color: #6b7280; font-size: 14px;">
                    Last updated: <span id="last-update">Loading...</span>
                </p>
            </div>

            <div id="latest-signal" class="signal-card signal-hold">
                <div class="signal-title">
                    <span id="signal-icon">⏸</span>
                    <span id="signal-text">HOLD - Waiting for analysis...</span>
                </div>
                <div class="signal-details" id="signal-details">
                    <div class="signal-detail">
                        <div class="signal-detail-label">Confidence</div>
                        <div class="signal-detail-value" id="signal-confidence">-</div>
                    </div>
                    <div class="signal-detail">
                        <div class="signal-detail-label">Position Size</div>
                        <div class="signal-detail-value" id="signal-size">-</div>
                    </div>
                    <div class="signal-detail">
                        <div class="signal-detail-label">Entry Price</div>
                        <div class="signal-detail-value" id="signal-entry">-</div>
                    </div>
                    <div class="signal-detail">
                        <div class="signal-detail-label">Stop Loss</div>
                        <div class="signal-detail-value" id="signal-sl">-</div>
                    </div>
                    <div class="signal-detail">
                        <div class="signal-detail-label">Take Profit</div>
                        <div class="signal-detail-value" id="signal-target">-</div>
                    </div>
                </div>
            </div>

            <div class="grid">
                <div class="card">
                    <h2>📊 Market Data</h2>
                    <div class="metric" id="price-metric">
                        <span class="metric-label">Current Price</span>
                        <span class="metric-value" id="current-price">Loading...</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Data Source</span>
                        <span class="metric-value" id="data-source">Loading...</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Instrument</span>
                        <span class="metric-value" id="instrument-name">Loading...</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Market Status</span>
                        <span class="metric-value" id="market-status">Checking...</span>
                    </div>
                    <button class="refresh-btn" onclick="loadData()">🔄 Refresh</button>
                </div>

                <div class="card">
                    <h2>💰 Performance</h2>
                    <div class="metric">
                        <span class="metric-label">Total P&L</span>
                        <span class="metric-value" id="total-pnl">₹0</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Win Rate</span>
                        <span class="metric-value" id="win-rate">0%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Total Trades</span>
                        <span class="metric-value" id="total-trades">0</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Open Positions</span>
                        <span class="metric-value" id="open-positions">0</span>
                    </div>
                </div>

                <div class="card">
                    <h2>🤖 Agent Status</h2>
                    <div id="agent-status">
                        <div class="loading">Loading agent status...</div>
                    </div>
                </div>

                <div class="card">
                    <h2>⚙️ System Health</h2>
                    <div id="system-health">
                        <div class="loading">Checking system health...</div>
                    </div>
                </div>
            </div>

            <div class="card">
                <h2>📈 Recent Trades</h2>
                <div id="trades-container">
                    <div class="loading">Loading trades...</div>
                </div>
            </div>

            <div class="card">
                <h2>💡 Latest Agent Analysis</h2>
                <div id="agent-analysis">
                    <div class="loading">Waiting for agent analysis...</div>
                </div>
            </div>
        </div>

        <script>
            let updateInterval;

            function formatCurrency(value) {
                return '₹' + parseFloat(value).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
            }

            function formatPercent(value) {
                return parseFloat(value).toFixed(2) + '%';
            }

            function updateSignal(signal) {
                const signalCard = document.getElementById('latest-signal');
                const signalText = document.getElementById('signal-text');
                const signalIcon = document.getElementById('signal-icon');
                
                signalCard.className = 'signal-card signal-' + signal.signal.toLowerCase();
                
                const icons = {
                    'BUY': '🟢',
                    'SELL': '🔴',
                    'HOLD': '⏸'
                };
                
                signalIcon.textContent = icons[signal.signal] || '⏸';
                signalText.textContent = signal.signal + ' - ' + (signal.reasoning || 'Analysis complete');
                
                document.getElementById('signal-confidence').textContent = 
                    signal.confidence ? formatPercent(signal.confidence * 100) : '-';
                document.getElementById('signal-size').textContent = signal.position_size || '-';
                document.getElementById('signal-entry').textContent = 
                    signal.entry_price ? formatCurrency(signal.entry_price) : '-';
                document.getElementById('signal-sl').textContent = 
                    signal.stop_loss ? formatCurrency(signal.stop_loss) : '-';
                document.getElementById('signal-target').textContent = 
                    signal.take_profit ? formatCurrency(signal.take_profit) : '-';
            }

            async function loadData() {
                try {
                    // Load latest signal
                    const signalRes = await fetch('/api/latest-signal');
                    if (signalRes.ok) {
                        const signal = await signalRes.json();
                        updateSignal(signal);
                    }

                    // Load market data
                    const marketRes = await fetch('/api/market-data');
                    if (marketRes.ok) {
                        const market = await marketRes.json();
                        const priceElement = document.getElementById('current-price');
                        if (market.current_price) {
                            priceElement.textContent = formatCurrency(market.current_price);
                            priceElement.parentElement.style.display = 'flex';
                        } else {
                            priceElement.parentElement.style.display = 'none';
                        }
                        document.getElementById('data-source').textContent = market.data_source || 'Unknown';
                        document.getElementById('instrument-name').textContent = market.instrument_name || 'Unknown';
                        document.getElementById('header-instrument').textContent = market.instrument_name || 'Unknown';
                        document.getElementById('market-status').textContent = market.market_open ? '🟢 OPEN' : '🔴 CLOSED';
                    }

                    // Load performance metrics
                    const metricsRes = await fetch('/metrics/trading');
                    if (metricsRes.ok) {
                        const metrics = await metricsRes.json();
                        document.getElementById('total-pnl').textContent = formatCurrency(metrics.total_pnl || 0);
                        document.getElementById('total-pnl').className = 'metric-value ' + 
                            (metrics.total_pnl >= 0 ? 'positive' : 'negative');
                        document.getElementById('win-rate').textContent = formatPercent(metrics.win_rate || 0);
                        document.getElementById('total-trades').textContent = metrics.total_trades || 0;
                        document.getElementById('open-positions').textContent = metrics.open_positions || 0;
                    }

                    // Load recent trades
                    const tradesRes = await fetch('/api/recent-trades');
                    if (tradesRes.ok) {
                        const trades = await tradesRes.json();
                        displayTrades(trades);
                    }

                    // Load agent analysis (with cache busting)
                    const analysisRes = await fetch('/api/latest-analysis?t=' + Date.now());
                    if (analysisRes.ok) {
                        const analysis = await analysisRes.json();
                        displayAgentAnalysis(analysis);
                    }

                    // Load system health
                    const healthRes = await fetch('/api/system-health');
                    if (healthRes.ok) {
                        const health = await healthRes.json();
                        displaySystemHealth(health);
                    }

                    // Load agent status
                    const agentStatusRes = await fetch('/api/agent-status');
                    if (agentStatusRes.ok) {
                        const agentStatus = await agentStatusRes.json();
                        displayAgentStatus(agentStatus);
                    }

                    document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
                } catch (error) {
                    console.error('Error loading data:', error);
                }
            }

            function displayTrades(trades) {
                const container = document.getElementById('trades-container');
                if (!trades || trades.length === 0) {
                    container.innerHTML = '<p style="color: #6b7280; padding: 20px; text-align: center;">No trades yet</p>';
                    return;
                }

                let html = '<table class="trades-table"><thead><tr>';
                html += '<th>Time</th><th>Signal</th><th>Entry</th><th>Exit</th><th>Quantity</th><th>P&L</th><th>Status</th>';
                html += '</tr></thead><tbody>';

                trades.forEach(trade => {
                    const pnl = trade.pnl || 0;
                    const pnlClass = pnl >= 0 ? 'positive' : 'negative';
                    html += '<tr>';
                    html += '<td>' + new Date(trade.entry_timestamp).toLocaleTimeString() + '</td>';
                    html += '<td><span class="badge badge-' + trade.signal.toLowerCase() + '">' + trade.signal + '</span></td>';
                    html += '<td>' + formatCurrency(trade.entry_price || 0) + '</td>';
                    html += '<td>' + (trade.exit_price ? formatCurrency(trade.exit_price) : '-') + '</td>';
                    html += '<td>' + (trade.quantity || 0) + '</td>';
                    html += '<td class="' + pnlClass + '">' + formatCurrency(pnl) + '</td>';
                    html += '<td><span class="badge badge-' + trade.status.toLowerCase() + '">' + trade.status + '</span></td>';
                    html += '</tr>';
                });

                html += '</tbody></table>';
                container.innerHTML = html;
            }

            function displayAgentAnalysis(analysis) {
                const container = document.getElementById('agent-analysis');
                if (!analysis || !analysis.agents || Object.keys(analysis.agents).length === 0) {
                    const message = analysis?.message || 'No agent analysis available yet. Agents run every 60 seconds.';
                    container.innerHTML = '<p style="color: #6b7280; padding: 20px;">' + message + '</p>';
                    if (analysis?.timestamp) {
                        container.innerHTML += '<p style="color: #9ca3af; padding: 0 20px 20px; font-size: 12px;">Last check: ' + new Date(analysis.timestamp).toLocaleString() + '</p>';
                    }
                    return;
                }

                let html = '';
                
                // Show timestamp and signal if available
                if (analysis.timestamp) {
                    html += '<div style="margin-bottom: 15px; padding: 10px; background: #f3f4f6; border-radius: 5px;">';
                    html += '<strong>Analysis Time:</strong> ' + new Date(analysis.timestamp).toLocaleString();
                    if (analysis.final_signal) {
                        html += ' | <strong>Signal:</strong> <span style="color: ' + 
                            (analysis.final_signal === 'BUY' ? '#10b981' : analysis.final_signal === 'SELL' ? '#ef4444' : '#6b7280') + 
                            '">' + analysis.final_signal + '</span>';
                    }
                    if (analysis.trend_signal) {
                        const trendColor = analysis.trend_signal === 'BULLISH' ? '#10b981' : 
                                          analysis.trend_signal === 'BEARISH' ? '#ef4444' : '#6b7280';
                        html += ' | <strong>Trend:</strong> <span style="color: ' + trendColor + 
                            '; font-weight: bold;">' + analysis.trend_signal + '</span>';
                    }
                    if (analysis.current_price) {
                        html += ' | <strong>Price:</strong> ' + formatCurrency(analysis.current_price);
                    }
                    html += '</div>';
                }
                
                // Show bullish/bearish score bar if available
                if (analysis.bullish_score !== undefined && analysis.bearish_score !== undefined && 
                    analysis.bullish_score !== null && analysis.bearish_score !== null) {
                    const bullishScore = parseFloat(analysis.bullish_score) || 0;
                    const bearishScore = parseFloat(analysis.bearish_score) || 0;
                    const totalScore = bullishScore + bearishScore;
                    
                    // Calculate percentages (normalize to 0-100%)
                    // Use total score if > 0, otherwise show relative to max possible (1.0 each = 2.0 total)
                    let bullishPct = 0;
                    let bearishPct = 0;
                    if (totalScore > 0) {
                        bullishPct = (bullishScore / totalScore) * 100;
                        bearishPct = (bearishScore / totalScore) * 100;
                    } else if (bullishScore === 0 && bearishScore === 0) {
                        // Both zero - show 50/50
                        bullishPct = 50;
                        bearishPct = 50;
                    } else {
                        // One is zero, show relative to max (1.0)
                        bullishPct = bullishScore * 100;
                        bearishPct = bearishScore * 100;
                    }
                    
                    html += '<div style="margin-bottom: 15px; padding: 10px; background: white; border-radius: 5px; border: 1px solid #e5e7eb;">';
                    html += '<div style="display: flex; justify-content: space-between; margin-bottom: 5px;">';
                    html += '<span style="color: #10b981; font-weight: bold;">Bullish: ' + bullishPct.toFixed(1) + '%</span>';
                    html += '<span style="color: #ef4444; font-weight: bold;">Bearish: ' + bearishPct.toFixed(1) + '%</span>';
                    html += '</div>';
                    
                    // Progress bar
                    html += '<div style="display: flex; height: 30px; border-radius: 5px; overflow: hidden; border: 1px solid #e5e7eb;">';
                    html += '<div style="background: linear-gradient(90deg, #10b981 0%, #34d399 100%); width: ' + bullishPct + '%; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 12px;">';
                    html += bullishPct.toFixed(0) + '%';
                    html += '</div>';
                    html += '<div style="background: linear-gradient(90deg, #f87171 0%, #ef4444 100%); width: ' + bearishPct + '%; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 12px;">';
                    html += bearishPct.toFixed(0) + '%';
                    html += '</div>';
                    html += '</div>';
                    
                    // Score values
                    html += '<div style="margin-top: 5px; font-size: 11px; color: #6b7280; text-align: center;">';
                    html += 'Bullish Score: ' + bullishScore.toFixed(2) + ' | Bearish Score: ' + bearishScore.toFixed(2);
                    html += '</div>';
                    html += '</div>';
                }
                
                // Show agent explanations if available
                if (analysis.agent_explanations && analysis.agent_explanations.length > 0) {
                    html += '<div style="margin-bottom: 15px;">';
                    html += '<strong style="color: #667eea;">Agent Explanations:</strong>';
                    analysis.agent_explanations.forEach(explanation => {
                        html += '<div style="margin-top: 5px; padding: 8px; background: #f9fafb; border-left: 3px solid #667eea; font-size: 13px;">';
                        html += explanation;
                        html += '</div>';
                    });
                    html += '</div>';
                }
                
                // Show individual agent outputs
                Object.entries(analysis.agents).forEach(([agentName, agentData]) => {
                    html += '<div class="agent-output">';
                    html += '<div class="agent-name">' + agentName.charAt(0).toUpperCase() + agentName.slice(1).replace(/_/g, ' ') + '</div>';
                    
                    // Handle different data structures
                    if (typeof agentData === 'string') {
                        html += '<div>' + agentData + '</div>';
                    } else if (agentData.thesis) {
                        html += '<div><strong>Thesis:</strong> ' + agentData.thesis + '</div>';
                        if (agentData.confidence !== undefined) {
                            html += '<div style="margin-top: 5px; color: #6b7280; font-size: 12px;">';
                            html += 'Confidence: ' + formatPercent(agentData.confidence * 100);
                            html += '</div>';
                        }
                    } else if (agentData.explanation) {
                        html += '<div>' + agentData.explanation + '</div>';
                        if (agentData.confidence !== undefined) {
                            html += '<div style="margin-top: 5px; color: #6b7280; font-size: 12px;">';
                            html += 'Confidence: ' + formatPercent(agentData.confidence * 100);
                            html += '</div>';
                        }
                    } else {
                        // Display full JSON with proper formatting
                        const jsonStr = JSON.stringify(agentData, null, 2);
                        html += '<div style="font-size: 11px; color: #374151; background: #f9fafb; padding: 10px; border-radius: 5px; overflow-x: auto; max-height: 300px; overflow-y: auto; font-family: monospace; white-space: pre-wrap; word-wrap: break-word;">';
                        html += jsonStr;
                        html += '</div>';
                    }
                    html += '</div>';
                });

                container.innerHTML = html || '<p style="color: #6b7280; padding: 20px;">No analysis available</p>';
            }

            function displaySystemHealth(health) {
                const container = document.getElementById('system-health');
                if (!health || !health.components) {
                    container.innerHTML = '<p style="color: #6b7280; padding: 20px;">Health check unavailable</p>';
                    return;
                }

                let html = '';
                const statusColors = {
                    'healthy': '#10b981',
                    'degraded': '#f59e0b',
                    'unhealthy': '#ef4444'
                };

                Object.entries(health.components).forEach(([componentName, componentData]) => {
                    const status = componentData.status || 'unknown';
                    const color = statusColors[status] || '#6b7280';
                    html += '<div class="metric">';
                    html += '<span class="metric-label">' + componentName.charAt(0).toUpperCase() + componentName.slice(1) + '</span>';
                    html += '<span class="metric-value" style="color: ' + color + '">' + status.toUpperCase() + '</span>';
                    html += '</div>';
                    if (componentData.message) {
                        html += '<div style="font-size: 12px; color: #6b7280; padding-left: 10px; margin-bottom: 5px;">';
                        html += componentData.message;
                        html += '</div>';
                    }
                });

                container.innerHTML = html || '<p style="color: #6b7280; padding: 20px;">No health data</p>';
            }

            function displayAgentStatus(status) {
                const container = document.getElementById('agent-status');
                if (!status) {
                    container.innerHTML = '<p style="color: #6b7280; padding: 20px;">Agent status unavailable</p>';
                    return;
                }

                const statusValue = status.status || 'unknown';
                const statusColors = {
                    'active': '#10b981',
                    'waiting': '#f59e0b',
                    'error': '#ef4444'
                };
                const color = statusColors[statusValue] || '#6b7280';

                let html = '<div class="metric">';
                html += '<span class="metric-label">Status</span>';
                html += '<span class="metric-value" style="color: ' + color + '">' + statusValue.toUpperCase() + '</span>';
                html += '</div>';
                
                if (status.last_analysis) {
                    html += '<div class="metric">';
                    html += '<span class="metric-label">Last Analysis</span>';
                    html += '<span class="metric-value">' + new Date(status.last_analysis).toLocaleString() + '</span>';
                    html += '</div>';
                }

                if (status.agents && Object.keys(status.agents).length > 0) {
                    html += '<div class="metric">';
                    html += '<span class="metric-label">Active Agents</span>';
                    html += '<span class="metric-value">' + Object.keys(status.agents).length + '</span>';
                    html += '</div>';
                }

                if (status.message) {
                    html += '<div style="margin-top: 10px; font-size: 12px; color: #6b7280;">';
                    html += status.message;
                    html += '</div>';
                }

                container.innerHTML = html;
            }

            // Auto-refresh every 5 seconds
            loadData();
            updateInterval = setInterval(loadData, 5000);

            // Cleanup on page unload
            window.addEventListener('beforeunload', () => {
                if (updateInterval) clearInterval(updateInterval);
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


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
            return {
                "signal": latest_trade.get("signal", "HOLD"),
                "position_size": latest_trade.get("quantity", 0),
                "entry_price": latest_trade.get("entry_price", 0),
                "stop_loss": latest_trade.get("stop_loss", 0),
                "take_profit": latest_trade.get("take_profit", 0),
                "confidence": 0.65,  # Default confidence
                "reasoning": "Based on multi-agent analysis"
            }
        
        # If no trades, return HOLD signal
        return {
            "signal": "HOLD",
            "position_size": 0,
            "entry_price": 0,
            "stop_loss": 0,
            "take_profit": 0,
            "confidence": 0.0,
            "reasoning": "Waiting for market analysis"
        }
    except Exception as e:
        logger.error(f"Error getting latest signal: {e}")
        return {
            "signal": "HOLD",
            "reasoning": f"Error: {str(e)}"
        }


@app.get("/api/market-data")
async def get_market_data() -> Dict[str, Any]:
    """Get current market data."""
    try:
        current_price = None
        
        # Try to get price from Redis first
        instrument_key = settings.instrument_symbol.replace("-", "").replace(" ", "").upper()
        current_price = market_memory.get_current_price(instrument_key)
        
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
        
        # Check if market is open
        now = datetime.now()
        try:
            open_time = datetime.strptime(settings.market_open_time, "%H:%M:%S").time()
            close_time = datetime.strptime(settings.market_close_time, "%H:%M:%S").time()
        except ValueError:
            open_time = datetime.strptime("09:15:00", "%H:%M:%S").time()
            close_time = datetime.strptime("15:30:00", "%H:%M:%S").time()
        
        # Check market hours - for 24/7 markets (crypto), always open
        if settings.market_24_7:
            market_open = True
        else:
            market_open = (now.weekday() < 5 and open_time <= now.time() <= close_time)
        
        # Determine data source from settings
        data_source_map = {
            "CRYPTO": "Binance WebSocket",
            "ZERODHA": "Zerodha Kite",
            "FINNHUB": "Finnhub"
        }
        data_source = data_source_map.get(settings.data_source, settings.data_source or "Unknown")
        
        return {
            "current_price": current_price,
            "data_source": data_source,
            "instrument_name": settings.instrument_name,
            "instrument_symbol": settings.instrument_symbol,
            "market_open": market_open,
            "redis_available": market_memory._redis_available,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting market data: {e}")
        return {
            "current_price": None,
            "data_source": "Unknown",
            "market_open": False,
            "redis_available": False
        }


@app.get("/api/recent-trades")
async def get_recent_trades(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent trades."""
    try:
        mongo_client = get_mongo_client()
        db = mongo_client[settings.mongodb_db_name]
        trades_collection = get_collection(db, "trades_executed")
        
        trades = list(trades_collection.find(
            {},
            sort=[("entry_timestamp", -1)]
        ).limit(limit))
        
        # Convert ObjectId to string for JSON serialization
        for trade in trades:
            if "_id" in trade:
                trade["_id"] = str(trade["_id"])
        
        return trades
    except Exception as e:
        logger.error(f"Error getting recent trades: {e}")
        return []


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
            # Get portfolio manager output for scores
            portfolio_output = latest_analysis.get("agent_decisions", {}).get("portfolio_manager", {})
            
            # Extract scores, handling None/empty cases
            bullish_score = portfolio_output.get("bullish_score")
            bearish_score = portfolio_output.get("bearish_score")
            
            # Try to parse as float if they're strings or None
            try:
                if bullish_score is not None:
                    bullish_score = float(bullish_score)
                else:
                    bullish_score = None
            except (ValueError, TypeError):
                bullish_score = None
            
            try:
                if bearish_score is not None:
                    bearish_score = float(bearish_score)
                else:
                    bearish_score = None
            except (ValueError, TypeError):
                bearish_score = None
            
            # Debug: Log if scores are None
            if bullish_score is None or bearish_score is None:
                logger.debug(f"Portfolio manager output: {portfolio_output}")
                logger.debug(f"Extracted scores: bullish={bullish_score}, bearish={bearish_score}")
            
            return {
                "agents": latest_analysis["agent_decisions"],
                "timestamp": latest_analysis.get("timestamp"),
                "final_signal": latest_analysis.get("final_signal", "HOLD"),
                "trend_signal": latest_analysis.get("trend_signal", "NEUTRAL"),
                "current_price": latest_analysis.get("current_price"),
                "bullish_score": bullish_score,
                "bearish_score": bearish_score,
                "agent_explanations": latest_analysis.get("agent_explanations", [])
            }
        
        # Fallback: Get most recent trade with agent decisions
        latest_trade = trades_collection.find_one(
            {"agent_decisions": {"$exists": True}},
            sort=[("entry_timestamp", -1)]
        )
        
        if latest_trade and latest_trade.get("agent_decisions"):
            return {
                "agents": latest_trade["agent_decisions"],
                "timestamp": latest_trade.get("entry_timestamp"),
                "final_signal": latest_trade.get("signal", "HOLD"),
                "trend_signal": latest_trade.get("trend_signal", "NEUTRAL")
            }
        
        return {"agents": {}, "message": "No analysis available yet. Agents are running every 60 seconds."}
    except Exception as e:
        logger.error(f"Error getting latest analysis: {e}", exc_info=True)
        return {"agents": {}, "error": str(e)}


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
            return {
                "total_trades": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "average_pnl": 0,
                "open_positions": len(open_trades)
            }
        
        profitable_trades = sum(1 for t in closed_trades if t.get("pnl", 0) > 0)
        total_pnl = sum(t.get("pnl", 0) for t in closed_trades)
        
        return {
            "total_trades": len(closed_trades),
            "profitable_trades": profitable_trades,
            "win_rate": (profitable_trades / len(closed_trades) * 100) if closed_trades else 0,
            "total_pnl": total_pnl,
            "average_pnl": total_pnl / len(closed_trades) if closed_trades else 0,
            "open_positions": len(open_trades)
        }
    except Exception as e:
        logger.error(f"Error getting trading metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics/agents")
async def get_agent_metrics() -> Dict[str, Any]:
    """Get agent performance metrics."""
    try:
        mongo_client = get_mongo_client()
        db = mongo_client[settings.mongodb_db_name]
        decisions_collection = get_collection(db, "agent_decisions")
        
        # Get recent agent decisions
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        decisions = list(decisions_collection.find({
            "timestamp": {"$gte": cutoff}
        }))
        
        # Aggregate by agent
        agent_stats = {}
        for decision in decisions:
            agent_name = decision.get("agent_name")
            if agent_name not in agent_stats:
                agent_stats[agent_name] = {"count": 0, "avg_confidence": 0.0}
            
            agent_stats[agent_name]["count"] += 1
            confidence = decision.get("confidence_score", 0.5)
            agent_stats[agent_name]["avg_confidence"] = (
                (agent_stats[agent_name]["avg_confidence"] * (agent_stats[agent_name]["count"] - 1) + confidence) /
                agent_stats[agent_name]["count"]
            )
        
        return {"agents": agent_stats}
    except Exception as e:
        logger.error(f"Error getting agent metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/system-health")
async def get_system_health() -> Dict[str, Any]:
    """Get comprehensive system health check."""
    try:
        return health_checker.check_all()
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.get("/api/agent-status")
async def get_agent_status() -> Dict[str, Any]:
    """Get detailed agent status."""
    try:
        return health_checker.get_agent_status_details()
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@app.get("/api/llm-providers")
async def get_llm_providers() -> Dict[str, Any]:
    """Get LLM provider status and usage."""
    try:
        llm_manager = get_llm_manager()
        status = llm_manager.get_provider_status()
        return {
            "current_provider": llm_manager.current_provider,
            "providers": status,
            "total_providers": len(status),
            "available_providers": len([p for p in status.values() if p["status"] == "available"]),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting LLM provider status: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    try:
        health = health_checker.check_all()
        return {
            "status": health["overall_status"],
            "timestamp": datetime.now().isoformat(),
            "paper_trading_mode": settings.paper_trading_mode,
            "components": {k: v.get("status", "unknown") for k, v in health["components"].items()}
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
