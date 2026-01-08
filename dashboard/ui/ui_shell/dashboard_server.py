#!/usr/bin/env python3
"""Trader Dashboard Web Server."""

from flask import Flask, render_template_string, jsonify
from datetime import datetime

app = Flask(__name__)

# Market data API base URL
MARKET_DATA_URL = "http://127.0.0.1:8006"

# HTML template for the dashboard
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trader Dashboard - BANKNIFTY</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a0a;
            color: #e0e0e0;
            line-height: 1.6;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background: linear-gradient(135deg, #1e3a8a, #3b82f6);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
        }
        .header h1 { margin-bottom: 10px; }
        .status { font-size: 14px; opacity: 0.9; }
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        .card {
            background: #1f1f1f;
            border-radius: 10px;
            padding: 20px;
            border: 1px solid #333;
        }
        .card h3 {
            color: #60a5fa;
            margin-bottom: 15px;
            border-bottom: 2px solid #60a5fa;
            padding-bottom: 5px;
        }
        .price-display {
            font-size: 32px;
            font-weight: bold;
            color: #10b981;
            text-align: center;
            margin: 20px 0;
        }
        .stale { color: #f59e0b !important; }
        .error { color: #ef4444 !important; }
        .options-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }
        .options-table th, .options-table td {
            padding: 8px;
            text-align: center;
            border-bottom: 1px solid #333;
        }
        .options-table th {
            background: #2a2a2a;
            color: #60a5fa;
        }
        .strike-header { background: #374151 !important; }
        .call-cell { color: #10b981; }
        .put-cell { color: #ef4444; }
        .chart-container {
            position: relative;
            height: 300px;
            margin: 20px 0;
        }
        .indicators-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
        }
        .indicator-card {
            background: #2a2a2a;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
        }
        .indicator-value {
            font-size: 18px;
            font-weight: bold;
            color: #60a5fa;
        }
        .indicator-label {
            font-size: 12px;
            color: #9ca3af;
        }
        .refresh-btn {
            background: #3b82f6;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin: 10px 0;
        }
        .refresh-btn:hover { background: #2563eb; }
        .last-updated {
            font-size: 12px;
            color: #6b7280;
            text-align: center;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏛️ BANKNIFTY Trader Dashboard</h1>
            <div class="status" id="system-status">Loading...</div>
        </div>

        <button class="refresh-btn" onclick="refreshData()">🔄 Refresh Data</button>

        <div class="grid">
            <div class="card">
                <h3>📊 Current Price</h3>
                <div class="price-display" id="current-price">--</div>
                <div id="price-details"></div>
            </div>

            <div class="card">
                <h3>📈 Technical Indicators</h3>
                <div class="indicators-grid" id="indicators">
                    <div class="indicator-card">
                        <div class="indicator-value" id="rsi">--</div>
                        <div class="indicator-label">RSI (14)</div>
                    </div>
                    <div class="indicator-card">
                        <div class="indicator-value" id="macd">--</div>
                        <div class="indicator-label">MACD</div>
                    </div>
                    <div class="indicator-card">
                        <div class="indicator-value" id="bb-upper">--</div>
                        <div class="indicator-label">BB Upper</div>
                    </div>
                    <div class="indicator-card">
                        <div class="indicator-value" id="sma">--</div>
                        <div class="indicator-label">SMA (20)</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="card">
            <h3>⚡ Options Chain</h3>
            <div id="options-chain">
                <p>Loading options data...</p>
            </div>
        </div>

        <div class="card">
            <h3>📉 Price Chart</h3>
            <div class="chart-container">
                <canvas id="priceChart"></canvas>
            </div>
        </div>

        <div class="last-updated" id="last-updated">
            Last updated: Never
        </div>
    </div>

    <script>
        let priceChart;
        let priceHistory = [];

        // Initialize chart
        function initChart() {
            const ctx = document.getElementById('priceChart').getContext('2d');
            priceChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'BANKNIFTY Price',
                        data: [],
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: false,
                            grid: { color: '#374151' },
                            ticks: { color: '#9ca3af' }
                        },
                        x: {
                            grid: { color: '#374151' },
                            ticks: { color: '#9ca3af' }
                        }
                    },
                    plugins: {
                        legend: {
                            labels: { color: '#e0e0e0' }
                        }
                    }
                }
            });
        }

        // Update price chart
        function updatePriceChart(price) {
            const now = new Date().toLocaleTimeString();

            priceHistory.push({ time: now, price: price });

            // Keep only last 50 points
            if (priceHistory.length > 50) {
                priceHistory.shift();
            }

            priceChart.data.labels = priceHistory.map(p => p.time);
            priceChart.data.datasets[0].data = priceHistory.map(p => p.price);
            priceChart.update();
        }

        // Update dashboard with data
        function updateDashboard(data) {
            // Update system status
            document.getElementById('system-status').textContent =
                `System: ${data.system_health?.status || 'Unknown'}`;

            // Update price
            if (data.price_data && data.price_data.price) {
                const price = data.price_data.price;
                const isStale = data.price_data.is_stale;

                document.getElementById('current-price').textContent =
                    `₹${price.toLocaleString()}`;
                document.getElementById('current-price').className =
                    `price-display ${isStale ? 'stale' : ''}`;

                document.getElementById('price-details').innerHTML = `
                    Volume: ${data.price_data.volume || 'N/A'}<br>
                    Status: ${isStale ? 'After Hours' : 'Live'}
                `;

                updatePriceChart(price);
            } else {
                document.getElementById('current-price').textContent = 'No Data';
                document.getElementById('current-price').className = 'price-display error';
            }

            // Update indicators
            if (data.technical_indicators && data.technical_indicators.indicators) {
                const trend = data.technical_indicators.indicators.trend || {};
                document.getElementById('rsi').textContent = trend.rsi_14 ? trend.rsi_14.toFixed(1) : '--';
                document.getElementById('macd').textContent = trend.macd_value ? trend.macd_value.toFixed(2) : '--';

                const volatility = data.technical_indicators.indicators.volatility || {};
                document.getElementById('bb-upper').textContent = volatility.bollinger_upper ? volatility.bollinger_upper.toFixed(0) : '--';

                document.getElementById('sma').textContent = trend.sma_20 ? trend.sma_20.toFixed(0) : '--';
            }

            // Update options chain
            if (data.options_chain && data.options_chain.strikes) {
                const strikes = data.options_chain.strikes.slice(0, 10); // Show first 10
                let html = `
                    <table class="options-table">
                        <thead>
                            <tr>
                                <th>Strike</th>
                                <th>Call Price</th>
                                <th>Call OI</th>
                                <th>Put Price</th>
                                <th>Put OI</th>
                            </tr>
                        </thead>
                        <tbody>
                `;

                strikes.forEach(strike => {
                    const call = strike.call || {};
                    const put = strike.put || {};

                    html += `
                        <tr>
                            <td class="strike-header">${strike.strike}</td>
                            <td class="call-cell">${call.price || '-'}</td>
                            <td class="call-cell">${call.oi || '-'}</td>
                            <td class="put-cell">${put.price || '-'}</td>
                            <td class="put-cell">${put.oi || '-'}</td>
                        </tr>
                    `;
                });

                html += '</tbody></table>';
                html += `<p style="margin-top: 10px; font-size: 12px; color: #6b7280;">Showing ${strikes.length} of ${data.options_chain.strikes.length} strikes</p>`;

                document.getElementById('options-chain').innerHTML = html;
            } else {
                document.getElementById('options-chain').innerHTML = '<p>No options data available</p>';
            }

            // Update timestamp
            document.getElementById('last-updated').textContent =
                `Last updated: ${new Date(data.timestamp).toLocaleString()}`;
        }

        // Fetch dashboard data
        async function fetchDashboardData() {
            try {
                const response = await fetch('/api/dashboard');
                if (response.ok) {
                    const data = await response.json();
                    updateDashboard(data);
                } else {
                    console.error('Failed to fetch dashboard data');
                }
            } catch (error) {
                console.error('Error fetching data:', error);
            }
        }

        // Refresh data manually
        function refreshData() {
            fetchDashboardData();
        }

        // Auto-refresh every 30 seconds
        setInterval(fetchDashboardData, 30000);

        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            initChart();
            fetchDashboardData();
        });
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """Serve the main dashboard."""
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/dashboard')
def get_dashboard_data():
    """Get dashboard data from market data APIs."""
    try:
        # Get all data sequentially (simpler than async for Flask compatibility)
        import requests

        data = {
            "timestamp": datetime.now().isoformat(),
        }

        # Health check
        try:
            health_resp = requests.get(f"{MARKET_DATA_URL}/health", timeout=5)
            data["system_health"] = health_resp.json() if health_resp.status_code == 200 else {"status": "error"}
        except Exception as e:
            data["system_health"] = {"status": "error", "error": str(e)}

        # Price data
        try:
            price_resp = requests.get(f"{MARKET_DATA_URL}/api/v1/market/price/BANKNIFTY", timeout=5)
            data["price_data"] = price_resp.json() if price_resp.status_code == 200 else None
        except Exception as e:
            data["price_data"] = None

        # Options chain
        try:
            options_resp = requests.get(f"{MARKET_DATA_URL}/api/v1/options/chain/BANKNIFTY", timeout=5)
            data["options_chain"] = options_resp.json() if options_resp.status_code == 200 else None
        except Exception as e:
            data["options_chain"] = None

        # Technical indicators
        try:
            indicators_resp = requests.get(f"{MARKET_DATA_URL}/api/v1/technical/indicators/BANKNIFTY", timeout=5)
            data["technical_indicators"] = indicators_resp.json() if indicators_resp.status_code == 200 else None
        except Exception as e:
            data["technical_indicators"] = None

        return jsonify(data)

    except Exception as e:
        return jsonify({
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "system_health": {"status": "error"}
        })

if __name__ == '__main__':
    print("🚀 Starting Trader Dashboard...")
    print("📊 Visit: http://127.0.0.1:5000")
    print("🔗 Make sure market_data server is running on port 8006")
    app.run(host='127.0.0.1', port=5000, debug=True)
