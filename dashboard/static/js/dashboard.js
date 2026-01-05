const currencySymbol = window.INSTRUMENT_SYMBOL.includes('BTC') || window.INSTRUMENT_SYMBOL.includes('ETH') ? '$' : '₹';
const dataTimestamps = {};
let refreshCountdown = 10;

function formatCurrency(val) {
    return currencySymbol + parseFloat(val || 0).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
}

function formatPercent(val) {
    const numVal = parseFloat(val || 0);
    const displayVal = (numVal > 0 && numVal <= 1) ? numVal * 100 : numVal;
    return displayVal.toFixed(2) + '%';
}

function formatRelativeTime(timestamp) {
    if (!timestamp) return 'Never';
    const now = Date.now();
    const then = new Date(timestamp).getTime();
    const diffMs = now - then;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    
    if (diffSec < 10) return 'Just now';
    if (diffSec < 60) return diffSec + 's ago';
    if (diffMin < 60) return diffMin + 'm ago';
    return diffHour + 'h ago';
}

function getStalenessColor(timestamp) {
    if (!timestamp) return '#ef4444'; // red - no data
    const diffMs = Date.now() - new Date(timestamp).getTime();
    const diffMin = diffMs / 60000;
    if (diffMin < 1) return '#10b981'; // green - fresh
    if (diffMin < 5) return '#f59e0b'; // yellow - stale
    return '#ef4444'; // red - very stale
}

function updateTimestamp(elementId, timestamp, label = 'Updated') {
    const el = document.getElementById(elementId);
    if (!el) return;
    const relTime = formatRelativeTime(timestamp);
    const color = getStalenessColor(timestamp);
    el.innerHTML = `<span style="color: ${color};">●</span> ${label} ${relTime}`;
}

function toggleTheme() {
    document.body.classList.toggle('dark-mode');
    localStorage.setItem('darkMode', document.body.classList.contains('dark-mode'));
}

function scrollToSection(id) {
    const element = document.getElementById(id);
    if (element) element.scrollIntoView({behavior: 'smooth'});
}

// Initialize dark mode from localStorage
if (localStorage.getItem('darkMode') === 'true') {
    document.body.classList.add('dark-mode');
}

async function loadData() {
    try {
        const [signal, market, metrics, risk, trades, agents, portfolio, health, technicals, latestAnalysis, llm] = await Promise.all([
            fetch('/api/latest-signal').then(r => r.json()).catch(() => ({})),
            fetch('/api/market-data').then(r => r.json()).catch(() => ({})),
            fetch('/metrics/trading').then(r => r.json()).catch(() => ({})),
            fetch('/metrics/risk').then(r => r.json()).catch(() => ({})),
            fetch('/api/recent-trades?limit=20').then(r => r.json()).catch(() => []),
            fetch('/api/agent-status').then(r => r.json()).catch(() => ({})),
            fetch('/api/portfolio').then(r => r.json()).catch(() => ({positions: []})),
            fetch('/api/system-health').then(r => r.json()).catch(() => ({})),
            fetch('/api/technical-indicators').then(r => r.json()).catch(() => ({})),
            fetch('/api/latest-analysis').then(r => r.json()).catch(() => ({})),
            fetch('/api/metrics/llm').then(r => r.json()).catch(() => ({}))
        ]);
        
        updateSignal(signal);
        updateMarketData(market);
        updateMetrics(metrics);
        updateRisk(risk);
        displayTrades(trades);
        displayAgents(agents, latestAnalysis);
        displayPortfolio(portfolio);
        displayHealth(health);
        updateSystemStatus(health, agents, llm);
        displayTechnicals(technicals);
        updateLLMProviders(llm);
        
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
    const timestamp = market.timestamp || market.updated_at || new Date().toISOString();
    dataTimestamps.market = timestamp;
    updateTimestamp('market-timestamp', timestamp);
    
    const hasData = market.currentprice || market.current_price || market.ltp;
    document.getElementById('current-price').textContent = hasData ? formatCurrency(market.currentprice || market.current_price || market.ltp) : 'No data';
    
    const change = market.change24h || market.change_24h || market.change || 0;
    const changeEl = document.getElementById('change-24h');
    changeEl.textContent = hasData ? formatPercent(change) : 'No data';
    changeEl.className = 'metric-value ' + (change >= 0 ? 'metric-positive' : 'metric-negative');
    
    // Volume - format with K/M/B suffix
    const volume = market.volume24h || market.volume_24h || market.volume || 0;
    let volumeText = 'No data';
    if (volume > 0) {
        if (volume >= 1e9) volumeText = (volume / 1e9).toFixed(2) + 'B';
        else if (volume >= 1e6) volumeText = (volume / 1e6).toFixed(2) + 'M';
        else if (volume >= 1e3) volumeText = (volume / 1e3).toFixed(2) + 'K';
        else volumeText = volume.toFixed(0);
    }
    document.getElementById('volume-24h').textContent = volumeText;
    
    document.getElementById('high-24h').textContent = market.high24h || market.high_24h || market.high ? formatCurrency(market.high24h || market.high_24h || market.high) : 'No data';
    document.getElementById('low-24h').textContent = market.low24h || market.low_24h || market.low ? formatCurrency(market.low24h || market.low_24h || market.low) : 'No data';
    document.getElementById('vwap').textContent = market.vwap ? formatCurrency(market.vwap) : 'No data';
    document.getElementById('market-status').textContent = market.marketopen || market.market_open || market.isOpen ? '🟢 Open' : '🔴 Closed';
}

function updateMetrics(m) {
    const timestamp = m.timestamp || m.updated_at || new Date().toISOString();
    dataTimestamps.metrics = timestamp;
    updateTimestamp('metrics-timestamp', timestamp);
    
    document.getElementById('total-pnl').textContent = m.totalpnl ? formatCurrency(m.totalpnl) : 'No trades yet';
    document.getElementById('win-rate').textContent = m.winrate ? formatPercent(m.winrate) : 'No trades yet';
    document.getElementById('total-trades').textContent = m.totaltrades || 0;
}

function updateRisk(r) {
    const timestamp = r.timestamp || r.updated_at || new Date().toISOString();
    dataTimestamps.risk = timestamp;
    updateTimestamp('risk-timestamp', timestamp);
    
    const hasData = r.sharperatio || r.sharpe_ratio;
    document.getElementById('sharpe').textContent = hasData ? (r.sharperatio || r.sharpe_ratio).toFixed(2) : 'No data';
    document.getElementById('drawdown').textContent = hasData ? formatPercent(r.maxdrawdown || r.max_drawdown || 0) : 'No data';
    document.getElementById('var-95').textContent = r.var95 || r.var_95 ? formatCurrency(r.var95 || r.var_95) : 'Not calculated';
    document.getElementById('total-exposure').textContent = r.totalexposure || r.total_exposure ? formatCurrency(r.totalexposure || r.total_exposure) : 'Not calculated';
    document.getElementById('portfolio-value').textContent = r.portfoliovalue || r.portfolio_value ? formatCurrency(r.portfoliovalue || r.portfolio_value) : 'Not calculated';
    const winLossRatio = r.winlossratio || r.win_loss_ratio || 0;
    document.getElementById('win-loss-ratio').textContent = winLossRatio ? winLossRatio.toFixed(2) : 'Not calculated';
}

function displayTrades(trades) {
    const tbody = document.getElementById('trades-body');
    if (!trades || trades.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="loading">No trades yet</td></tr>';
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
            '<td style="color: ' + (pnl >= 0 ? '#10b981' : '#ef4444') + '">' + formatCurrency(pnl) + '</td>' +
            '<td><span class="badge-small badge-' + (t.status || 'open').toLowerCase() + '">' + (t.status || 'OPEN') + '</span></td>' +
            '</tr>';
    });
    tbody.innerHTML = html;
}

function displayAgents(agents, latestAnalysis) {
    const container = document.getElementById('agents-container');
    if (!agents || !agents.agents || Object.keys(agents.agents).length === 0) {
        container.innerHTML = '<div class="loading" style="grid-column: 1/-1;">No agents active</div>';
        return;
    }
    
    let html = '';
    
    // Overall agent system status + last analysis time
    try {
        const overallStatus = agents.status || 'unknown';
        const lastTs = agents.last_analysis || agents.lastAnalysis || (latestAnalysis && (latestAnalysis.timestamp || latestAnalysis.analysisTimestamp));
        let statusLabel = 'Initializing';
        let statusColor = '#f59e0b';
        let statusText = 'Waiting for first analysis run';
        if (overallStatus === 'active') {
            statusLabel = 'Active';
            statusColor = '#10b981';
            statusText = 'Agents are running analysis on schedule';
        } else if (overallStatus === 'stale') {
            statusLabel = 'Stale';
            statusColor = '#f59e0b';
            statusText = 'Last full analysis is older than 15 minutes – waiting for next run';
        } else if (overallStatus === 'error') {
            statusLabel = 'Error';
            statusColor = '#ef4444';
            statusText = 'Agent analysis service reported an error';
        }

        let lastText = 'No analysis yet';
        if (lastTs) {
            const rel = formatRelativeTime(lastTs);
            const absTime = new Date(lastTs).toLocaleTimeString();
            lastText = `${rel} (${absTime})`;
        }

        html += '<div style="grid-column:1/-1;padding:10px 12px;border-radius:8px;background:#eef2ff;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center;gap:8px;">';
        html += '<div style="font-size:0.9rem;">';
        html += '<div style="font-weight:600;margin-bottom:2px;">Agent System Status</div>';
        html += `<div style="font-size:0.8rem;color:#4b5563;">${statusText}</div>`;
        html += '</div>';
        html += '<div style="text-align:right;font-size:0.8rem;">';
        html += `<div style="font-weight:600;color:${statusColor};">${statusLabel}</div>`;
        html += `<div style="color:#4b5563;">Last analysis: ${lastText}</div>`;
        html += '</div>';
        html += '</div>';
    } catch (e) {
        console.error('Error rendering agent header', e);
    }
    
    // Executive summary with Markdown support
    const exec = agents.executive_summary || agents.executiveSummary || null;
    if (exec) {
        const raw = String(exec);
        const formatted = (window.marked && window.DOMPurify) ? 
            DOMPurify.sanitize(marked.parse(raw)) : raw;
        html += '<div style="grid-column:1/-1; padding:12px; border-radius:8px; background:#f9fafb; margin-bottom:12px;"><strong>Executive Summary:</strong><div style="margin-top:6px;font-size:0.95rem;">' + formatted + '</div></div>';
    }
    
    // Scenario Paths panel
    try {
        const scenarios = latestAnalysis.scenarioPaths || latestAnalysis.scenario_paths || null;
        if (scenarios && (scenarios.base_case || scenarios.bull_case || scenarios.bear_case)) {
            html += '<div style="grid-column:1/-1; padding:12px; border-radius:8px; background:#f9fafb; margin-bottom:12px;">';
            html += '<div style="font-weight:600;margin-bottom:8px;">Scenario Paths (15–60 min)</div>';
            html += '<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;font-size:12px;">';
            
            const base = scenarios.base_case || {};
            const bull = scenarios.bull_case || {};
            const bear = scenarios.bear_case || {};
            
            if (Object.keys(base).length) {
                html += '<div style="padding:8px;border-radius:6px;background:#fff;border:1px solid #e5e7eb;">';
                html += '<div style="font-weight:600;">Base</div>';
                html += '<div>15m: ' + (base.target_15m ? formatCurrency(base.target_15m) : '-') + '</div>';
                html += '<div>60m: ' + (base.target_60m ? formatCurrency(base.target_60m) : '-') + '</div>';
                html += '</div>';
            }
            
            if (Object.keys(bull).length) {
                html += '<div style="padding:8px;border-radius:6px;background:#ecfdf3;border:1px solid #bbf7d0;">';
                html += '<div style="font-weight:600;color:#166534;">Bull</div>';
                html += '<div>15m: ' + (bull.target_15m ? formatCurrency(bull.target_15m) : '-') + '</div>';
                html += '<div>60m: ' + (bull.target_60m ? formatCurrency(bull.target_60m) : '-') + '</div>';
                html += '</div>';
            }
            
            if (Object.keys(bear).length) {
                html += '<div style="padding:8px;border-radius:6px;background:#fef2f2;border:1px solid #fecaca;">';
                html += '<div style="font-weight:600;color:#991b1b;">Bear</div>';
                html += '<div>15m: ' + (bear.target_15m ? formatCurrency(bear.target_15m) : '-') + '</div>';
                html += '<div>60m: ' + (bear.target_60m ? formatCurrency(bear.target_60m) : '-') + '</div>';
                html += '</div>';
            }
            
            html += '</div></div>';
        }
    } catch (e) {
        console.error('Error rendering scenarios', e);
    }
    
    // Agent cards
    Object.entries(agents.agents).forEach(([name, agent]) => {
        const summary = agent.summary || {};
        const isStale = agent.status === 'stale';
        const statusIcon = agent.status === 'active' ? '🟢' : (isStale ? '🟡' : '⚪');
        let statusLabel = agent.status || 'Unknown';
        if (isStale) {
            statusLabel = 'Stale (last run >15m ago)';
        }
        
        html += '<div class="agent-card">';
        html += '<div class="agent-name">' + (agent.name || name.replace(/_/g, ' ').toUpperCase()) + '</div>';
        html += '<div class="agent-metric">';
        html += '<span class="agent-label">Status</span>';
        html += '<span class="agent-value">' + statusIcon + ' ' + statusLabel + '</span>';
        html += '</div>';
        
        if (summary.signal) {
            const signalColor = summary.signal === 'BUY' ? '#10b981' : (summary.signal === 'SELL' ? '#ef4444' : '#6b7280');
            html += '<div class="agent-metric">';
            html += '<span class="agent-label">Signal</span>';
            html += '<span class="agent-value" style="color: ' + signalColor + '; font-weight: bold;">' + summary.signal + '</span>';
            html += '</div>';
        }
        
        if (summary.reasoning) {
            html += '<div class="agent-metric" style="grid-column: 1/-1;">';
            html += '<span class="agent-label">Analysis</span>';
            html += '<span class="agent-value" style="font-size: 0.8rem; color: #9ca3af;">' + summary.reasoning.substring(0, 150) + '</span>';
            html += '</div>';
        }
        
        html += '</div>';
    });
    
    container.innerHTML = html;
}

function displayTechnicals(data) {
    const container = document.getElementById('technicals-container');
    if (!data || !data.indicators || Object.keys(data.indicators).length === 0) {
        container.innerHTML = '<div class="loading" style="grid-column: 1/-1;">No indicators available</div>';
        return;
    }
    
    let html = '';
    const indicators = data.indicators;
    
    // RSI
    if (indicators.rsi !== undefined) {
        const rsiStatus = indicators.rsi_status || 'NEUTRAL';
        html += '<div class="indicator-card">';
        html += '<div class="indicator-label">RSI (14)</div>';
        html += '<div class="indicator-value">' + indicators.rsi.toFixed(1) + '</div>';
        html += '<div class="indicator-status ' + rsiStatus.toLowerCase() + '">' + rsiStatus + '</div>';
        html += '</div>';
    }
    
    // Moving Averages
    ['sma_5', 'sma_10', 'sma_20'].forEach(ma => {
        if (indicators[ma] !== undefined) {
            const signal = indicators[ma + '_signal'] || 'NEUTRAL';
            html += '<div class="indicator-card">';
            html += '<div class="indicator-label">' + ma.replace('_', ' ').toUpperCase() + '</div>';
            html += '<div class="indicator-value">' + indicators[ma].toFixed(2) + '</div>';
            html += '<div class="indicator-status ' + signal.toLowerCase() + '">' + signal + '</div>';
            html += '</div>';
        }
    });
    
    // Support/Resistance
    if (indicators.support_level !== undefined) {
        html += '<div class="indicator-card">';
        html += '<div class="indicator-label">Support</div>';
        html += '<div class="indicator-value">' + formatCurrency(indicators.support_level) + '</div>';
        html += '</div>';
    }
    
    if (indicators.resistance_level !== undefined) {
        html += '<div class="indicator-card">';
        html += '<div class="indicator-label">Resistance</div>';
        html += '<div class="indicator-value">' + formatCurrency(indicators.resistance_level) + '</div>';
        html += '</div>';
    }
    
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

function updateSystemStatus(health, agents, llmMetrics) {
    const providerLabel = document.getElementById('llm-provider');
    const systemTextEl = document.getElementById('system-status-text');

    // Choose active LLM provider from health check or metrics
    let activeProvider = (health && health.llm_active_provider) || null;
    if (!activeProvider && llmMetrics && Array.isArray(llmMetrics.providers) && llmMetrics.providers.length) {
        const healthy = llmMetrics.providers.find(p => p.status === 'available' || p.status === 'healthy');
        activeProvider = (healthy && healthy.name) || llmMetrics.providers[0].name;
    }
    providerLabel.textContent = activeProvider || 'Unknown';

    // Derive overall system text
    let systemText = 'All systems operational';
    if (health) {
        if (health.status === 'error') {
            systemText = 'System health check unavailable';
        } else if (health.overall_status) {
            systemText = `Overall status: ${String(health.overall_status).toUpperCase()}`;
        }
    }
    if (systemTextEl) systemTextEl.textContent = systemText;

    const mongodb = health && health.components && health.components.mongodb;
    const dataFeedEl = document.getElementById('data-feed-status');
    if (mongodb && mongodb.status === 'healthy') {
        dataFeedEl.textContent = '✓ Active';
        dataFeedEl.style.color = '#10b981';
    } else {
        dataFeedEl.textContent = '✗ Error';
        dataFeedEl.style.color = '#ef4444';
    }

    const agentsEl = document.getElementById('agents-status');
    if (agents.agents && Object.keys(agents.agents).length > 0) {
        const activeCount = Object.values(agents.agents).filter(a => a.status === 'active').length;
        agentsEl.textContent = `${activeCount} Active`;
        agentsEl.style.color = '#10b981';
    } else {
        agentsEl.textContent = 'Initializing';
        agentsEl.style.color = '#f59e0b';
    }
}

function updateLLMProviders(metrics) {
    const container = document.getElementById('llm-providers-content');
    if (!metrics || !metrics.providers) {
        container.innerHTML = '<div class="loading">No provider metrics available</div>';
        return;
    }

    const providers = metrics.providers;
    const summary = metrics.summary || {};

    let html = '<div style="display:flex;flex-direction:column;gap:8px;">';

    // Summary row
    html += '<div style="display:flex;justify-content:space-between;padding:6px 8px;border-radius:6px;background:#eef2ff;font-size:12px;">';
    const healthy = summary.healthy_providers || 0;
    const total = summary.total_providers || providers.length;
    const tokens = summary.total_tokens_today || 0;
    html += `<div>Providers: <strong>${healthy}/${total} healthy</strong></div>`;
    html += `<div style="text-align:right;">Tokens today: <strong>${tokens}</strong></div>`;
    html += '</div>';

    // Individual providers (show all, not just first 5)
    providers.forEach(p => {
        const color = (p.status === 'healthy' || p.status === 'available') ? '#10b981' : '#f59e0b';
        const tokensToday = p.tokens_today || 0;
        const dailyLimit = p.daily_limit || 0;
        const usagePercent = p.usage_percent != null ? p.usage_percent : (dailyLimit ? (tokensToday / dailyLimit) * 100 : 0);

        html += '<div style="padding:6px 8px;border-radius:6px;background:#f9fafb;display:flex;flex-direction:column;gap:4px;">';
        html += `<div style="display:flex;justify-content:space-between;align-items:center;">` +
            `<div style="font-weight:600;">${p.name}</div>` +
            `<div style="font-size:12px;color:${color};">${(p.status || 'unknown').toUpperCase()}</div>` +
            '</div>';

        html += '<div style="display:flex;justify-content:space-between;font-size:11px;color:#6b7280;">';
        html += `<div>Model: <strong>${p.model || 'N/A'}</strong></div>`;
        if (dailyLimit) {
            html += `<div>Tokens: <strong>${tokensToday}</strong> / ${dailyLimit}</div>`;
        } else {
            html += `<div>Tokens: <strong>${tokensToday}</strong></div>`;
        }
        html += '</div>';

        // Simple usage bar
        html += '<div style="margin-top:2px;height:4px;border-radius:999px;background:#e5e7eb;overflow:hidden;">';
        html += `<div style="height:100%;width:${Math.min(100, usagePercent || 0)}%;background:${color};"></div>`;
        html += '</div>';

        html += '</div>';
    });

    html += '</div>';
    container.innerHTML = html;
}

// Update refresh countdown every second
setInterval(() => {
    refreshCountdown--;
    if (refreshCountdown <= 0) refreshCountdown = 10;
    const el = document.getElementById('refresh-countdown');
    if (el) {
        el.textContent = `Next refresh in ${refreshCountdown}s`;
        el.style.background = refreshCountdown <= 3 ? '#fef3c7' : '#f3f4f6';
    }
    
    // Update all relative timestamps
    if (dataTimestamps.market) updateTimestamp('market-timestamp', dataTimestamps.market);
    if (dataTimestamps.metrics) updateTimestamp('metrics-timestamp', dataTimestamps.metrics);
    if (dataTimestamps.risk) updateTimestamp('risk-timestamp', dataTimestamps.risk);
}, 1000);

// Auto-load data on page load and every 10 seconds
loadData();
setInterval(() => {
    refreshCountdown = 10;
    loadData();
}, 10000);
