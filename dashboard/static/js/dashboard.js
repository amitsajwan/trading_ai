// Currency symbol - detect from instrument metadata
let currencySymbol = '₹';  // Default to INR
const dataTimestamps = {};
let refreshCountdown = 10;

// Detect currency from backend or instrument symbol
function detectCurrency(instrument) {
    if (!instrument) return '₹';
    const sym = String(instrument).toUpperCase();
    if (sym.includes('BTC') || sym.includes('ETH') || sym.includes('USD')) return '$';
    return '₹';
}

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
        const [signal, market, metrics, risk, trades, agents, portfolio, health, technicals, latestAnalysis, llm, orderflow, optionsChain, optionsStrategy] = await Promise.all([
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
            fetch('/api/metrics/llm').then(r => r.json()).catch(() => ({})),
            fetch('/api/order-flow').then(r => r.json()).catch(() => ({available:false})),
            fetch('/api/options-chain').then(r => r.json()).catch(() => ({available:false})),
            // Prefer advanced strategy; fallback to basic
            fetch('/api/options-strategy-advanced').then(r => r.json()).catch(() => ({available:false}))
        ]);
        
        // Update currency symbol based on instrument
        currencySymbol = detectCurrency(window.INSTRUMENT_SYMBOL);
        
        // Calculate win/loss ratio from trading metrics
        const avgWin = metrics.avg_win || metrics.avgwin || 0;
        const avgLoss = Math.abs(metrics.avg_loss || metrics.avgloss || 0);
        const winLossRatio = avgLoss > 0 ? avgWin / avgLoss : (avgWin > 0 ? avgWin : 0);

        // Add win/loss ratio to risk data
        risk.win_loss_ratio = winLossRatio;

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
        displayOrderFlow(orderflow);
        displayOptionsChain(optionsChain);
        // Persist latest strategy for trade button
        window.LATEST_OPTIONS_STRATEGY = optionsStrategy || {};
        displayOptionsStrategy(optionsStrategy);
        
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
    document.getElementById('signal-entry').textContent = signal.entry_price ? formatCurrency(signal.entry_price) : '-';
    document.getElementById('signal-sl').textContent = signal.stop_loss ? formatCurrency(signal.stop_loss) : '-';
    document.getElementById('signal-tp').textContent = signal.take_profit ? formatCurrency(signal.take_profit) : '-';
    card.className = 'signal-banner ' + (signal.signal || 'HOLD').toLowerCase();
}

function updateMarketData(market) {
    const timestamp = market.timestamp || market.updated_at || new Date().toISOString();
    dataTimestamps.market = timestamp;
    updateTimestamp('market-timestamp', timestamp);
    
    const hasData = market.currentprice || market.current_price || market.ltp;
    document.getElementById('current-price').textContent = hasData ? formatCurrency(market.currentprice || market.current_price || market.ltp) : 'No data';
    
    const changePercent = market.changepercent24h || market.change_percent_24h || market.changePercent || 0;
    const changeEl = document.getElementById('change-24h');
    changeEl.textContent = hasData ? formatPercent(changePercent) : 'No data';
    changeEl.className = 'metric-value ' + (changePercent >= 0 ? 'metric-positive' : 'metric-negative');
    
    // Volume - format with K/M/B suffix
    const volume = (market.volume24h ?? market.volume_24h ?? market.volume);
    let volumeText = 'No data';
    if (volume !== undefined && volume !== null) {
        const volNum = Number(volume) || 0;
        if (volNum >= 1e9) volumeText = (volNum / 1e9).toFixed(2) + 'B';
        else if (volNum >= 1e6) volumeText = (volNum / 1e6).toFixed(2) + 'M';
        else if (volNum >= 1e3) volumeText = (volNum / 1e3).toFixed(2) + 'K';
        else volumeText = volNum.toFixed(0);
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

    const totalPnl = m.total_pnl || m.totalpnl || 0;
    const winRate = m.win_rate || m.winrate || 0;
    const totalTrades = m.total_trades || m.totaltrades || 0;

    document.getElementById('total-pnl').textContent = totalTrades > 0 ? formatCurrency(totalPnl) : 'No trades yet';
    document.getElementById('win-rate').textContent = totalTrades > 0 ? formatPercent(winRate) : 'No trades yet';
    document.getElementById('total-trades').textContent = totalTrades;
}

function updateRisk(r) {
    const timestamp = r.timestamp || r.updated_at || new Date().toISOString();
    dataTimestamps.risk = timestamp;
    updateTimestamp('risk-timestamp', timestamp);
    
    const hasData = r.sharperatio || r.sharpe_ratio;
    document.getElementById('sharpe').textContent = hasData ? (r.sharperatio || r.sharpe_ratio).toFixed(2) : 'No data';
    document.getElementById('drawdown').textContent = hasData ? formatCurrency(r.maxdrawdown || r.max_drawdown || 0) : 'No data';
    document.getElementById('var-95').textContent = r.var95 || r.var_95 ? formatCurrency(r.var95 || r.var_95) : 'Not calculated';
    document.getElementById('total-exposure').textContent = r.totalexposure || r.total_exposure ? formatCurrency(r.totalexposure || r.total_exposure) : 'Not calculated';
    document.getElementById('portfolio-value').textContent = r.portfoliovalue || r.portfolio_value ? formatCurrency(r.portfoliovalue || r.portfolio_value) : 'Not calculated';
    const winLossRatio = r.win_loss_ratio || r.winlossratio || 0;
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
            '<td>' + new Date(t.timestamp).toLocaleTimeString() + '</td>' +
            '<td><span class="badge-small badge-' + (t.side || 'hold').toLowerCase() + '">' + (t.side || 'HOLD') + '</span></td>' +
            '<td>' + formatCurrency(t.price || 0) + '</td>' +
            '<td>' + (t.exit_price ? formatCurrency(t.exit_price) : '-') + '</td>' +
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
        const agentList = Object.values(agents.agents || {});
        const activeAgents = agentList.filter(a => a.status === 'active').length;
        const totalAgents = agentList.length;

        // Determine overall status based on agent activity
        let overallStatus = 'unknown';
        if (totalAgents > 0) {
            if (activeAgents === totalAgents) {
                overallStatus = 'active';
            } else if (activeAgents > 0) {
                overallStatus = 'partial';
            } else {
                overallStatus = 'inactive';
            }
        }

        const lastTs = agents.last_analysis || agents.lastAnalysis || (latestAnalysis && (latestAnalysis.timestamp || latestAnalysis.analysisTimestamp));
        let statusLabel = 'Initializing';
        let statusColor = '#f59e0b';
        let statusText = 'Waiting for first analysis run';

        if (overallStatus === 'active') {
            statusLabel = 'Active';
            statusColor = '#10b981';
            statusText = `All ${totalAgents} agents are running analysis on schedule`;
        } else if (overallStatus === 'partial') {
            statusLabel = 'Partial';
            statusColor = '#f59e0b';
            statusText = `${activeAgents}/${totalAgents} agents active - some agents may be offline`;
        } else if (overallStatus === 'inactive') {
            statusLabel = 'Inactive';
            statusColor = '#ef4444';
            statusText = 'No agents are currently active';
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
    if (!data || !data.indicators || data.indicators.length === 0) {
        container.innerHTML = '<div class="loading" style="grid-column: 1/-1;">No indicators available</div>';
        return;
    }

    let html = '';

    // Overall trend indicator
    if (data.trend) {
        const trendColor = data.trend === 'bullish' ? '#10b981' : data.trend === 'bearish' ? '#ef4444' : '#6b7280';
        html += '<div class="indicator-card" style="grid-column: 1/-1; background: #f8fafc; border: 2px solid ' + trendColor + ';">';
        html += '<div class="indicator-label">Market Trend</div>';
        html += '<div class="indicator-value" style="color: ' + trendColor + '; font-weight: bold;">' + data.trend.toUpperCase() + '</div>';
        html += '<div class="indicator-status ' + data.strength + '">' + (data.strength || 'neutral').toUpperCase() + '</div>';
        html += '</div>';
    }

    // Individual indicators
    data.indicators.forEach(indicator => {
        const signalColor = indicator.signal === 'bullish' ? '#10b981' :
                           indicator.signal === 'bearish' ? '#ef4444' : '#6b7280';

        html += '<div class="indicator-card">';
        html += '<div class="indicator-label">' + indicator.name + '</div>';

        // Format value based on indicator type
        let formattedValue;
        if (indicator.name.includes('SMA') || indicator.name.includes('BB_')) {
            formattedValue = formatCurrency(indicator.value);
        } else if (indicator.name.includes('%') || indicator.value > 0 && indicator.value < 1) {
            formattedValue = (indicator.value * 100).toFixed(1) + '%';
        } else {
            formattedValue = typeof indicator.value === 'number' ? indicator.value.toFixed(indicator.name.includes('RSI') || indicator.name.includes('STOCHASTIC') ? 1 : 2) : indicator.value;
        }

        html += '<div class="indicator-value">' + formattedValue + '</div>';
        html += '<div class="indicator-status" style="color: ' + signalColor + '; font-weight: bold;">' + indicator.signal.toUpperCase() + '</div>';
        html += '</div>';
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
        const pnl = p.unrealized_pnl || p.pnl || 0;
        html += '<tr>' +
            '<td>' + p.instrument + '</td>' +
            '<td>' + p.quantity + '</td>' +
            '<td>' + formatCurrency(p.entry_price) + '</td>' +
            '<td>' + formatCurrency(p.current_price) + '</td>' +
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
    Object.entries(health.components).forEach(([name, status]) => {
        const color = status === 'operational' || status === 'healthy' ? '#10b981' : '#f59e0b';
        html += '<div class="metric-row"><span class="metric-label">' + name + '</span><span class="metric-value" style="color: ' + color + ';">' + (status || 'unknown').toUpperCase() + '</span></div>';
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

    const providersObj = metrics.providers;
    const summary = metrics.summary || {};

    // Convert providers object to array and calculate summary
    const providers = Object.entries(providersObj).map(([name, data]) => ({ name, ...data }));
    const healthy = providers.filter(p => p.status === 'active' || p.status === 'available').length;
    const total = providers.length;
    const totalTokens = providers.reduce((sum, p) => sum + (p.tokens_today || 0), 0);

    let html = '<div style="display:flex;flex-direction:column;gap:8px;">';

    // Summary row
    html += '<div style="display:flex;justify-content:space-between;padding:6px 8px;border-radius:6px;background:#eef2ff;font-size:12px;">';
    html += `<div>Providers: <strong>${healthy}/${total} healthy</strong></div>`;
    html += `<div style="text-align:right;">Tokens today: <strong>${totalTokens.toLocaleString()}</strong></div>`;
    html += '</div>';

    // Individual providers
    providers.forEach(p => {
        const color = (p.status === 'active' || p.status === 'available') ? '#10b981' : '#f59e0b';
        const tokensToday = p.tokens_today || 0;
        const dailyLimit = p.daily_token_quota || 0;
        const usagePercent = dailyLimit ? (tokensToday / dailyLimit) * 100 : 0;

        html += '<div style="padding:6px 8px;border-radius:6px;background:#f9fafb;display:flex;flex-direction:column;gap:4px;">';
        html += `<div style="display:flex;justify-content:space-between;align-items:center;">` +
            `<div style="font-weight:600;">${p.name.toUpperCase()}</div>` +
            `<div style="font-size:12px;color:${color};">${(p.status || 'unknown').toUpperCase()}</div>` +
            '</div>';

        html += '<div style="display:flex;justify-content:space-between;font-size:11px;color:#6b7280;">';
        html += `<div>Requests: <strong>${p.requests_today || 0}</strong> (${(p.requests_per_minute || 0).toFixed(1)}/min)</div>`;
        if (dailyLimit) {
            const usageColor = usagePercent > 80 ? '#ef4444' : usagePercent > 60 ? '#f59e0b' : '#10b981';
            html += `<div style="color:${usageColor};">Tokens: <strong>${tokensToday.toLocaleString()}</strong> / ${dailyLimit.toLocaleString()}</div>`;
        } else {
            html += `<div>Tokens: <strong>${tokensToday.toLocaleString()}</strong></div>`;
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

function displayOrderFlow(data) {
    const card = document.getElementById('orderflow-card');
    if (!card) return;
    if (!data || data.available === false) {
        card.style.display = 'none';
        return;
    }
    card.style.display = 'block';
    const ts = data.timestamp || new Date().toISOString();
    updateTimestamp('orderflow-timestamp', ts);
    document.getElementById('orderflow-lastprice').textContent = data.last_price ? formatCurrency(data.last_price) : '-';

    // Handle imbalance - could be object or number
    const imbalanceVal = typeof data.imbalance === 'object' ? data.imbalance.imbalance_pct : data.imbalance;
    const imbalanceStatus = typeof data.imbalance === 'object' ? data.imbalance.imbalance_status : 'NEUTRAL';
    const pct = imbalanceVal != null ? (imbalanceVal * 100).toFixed(2) + '%' : '-';
    document.getElementById('orderflow-imbalance').textContent = `${pct} (${imbalanceStatus || 'NEUTRAL'})`;

    // Handle spread - could be object or number
    const spreadVal = typeof data.spread === 'object' ? data.spread.spread_pct : data.spread;
    const spreadStatus = typeof data.spread === 'object' ? data.spread.spread_status : 'UNKNOWN';
    const spreadText = spreadVal != null ? (spreadVal * 100).toFixed(2) + '%' : 'n/a';
    document.getElementById('orderflow-spread').textContent = `${spreadText} (${spreadStatus || 'UNKNOWN'})`;

    // Display total depth quantities
    const totalBidQty = data.total_bid_quantity || data.total_depth_bid || 0;
    const totalAskQty = data.total_ask_quantity || data.total_depth_ask || 0;
    document.getElementById('orderflow-total-depth').textContent = `${totalBidQty} / ${totalAskQty}`;

    // Render depth ladder (top 5 levels from Kite)
    const depthBuy = data.depth_buy || [];
    const depthSell = data.depth_sell || [];
    const ladderBody = document.getElementById('depth-ladder-body');
    
    if (!depthBuy.length || !depthSell.length) {
        ladderBody.innerHTML = '<tr><td colspan="4" class="loading">No depth data</td></tr>';
        return;
    }
    
    let ladderHtml = '';
    const maxLevels = Math.max(depthBuy.length, depthSell.length);
    
    for (let i = 0; i < Math.min(maxLevels, 5); i++) {
        const bid = depthBuy[i] || {};
        const ask = depthSell[i] || {};
        
        const bidQty = bid.quantity || '-';
        const bidPrice = bid.price ? formatCurrency(bid.price) : '-';
        const askPrice = ask.price ? formatCurrency(ask.price) : '-';
        const askQty = ask.quantity || '-';
        
        ladderHtml += '<tr>' +
            `<td style="color: #10b981;">${bidQty}</td>` +
            `<td style="color: #10b981; font-weight: 600;">${bidPrice}</td>` +
            `<td style="color: #ef4444; font-weight: 600;">${askPrice}</td>` +
            `<td style="color: #ef4444;">${askQty}</td>` +
            '</tr>';
    }
    
    ladderBody.innerHTML = ladderHtml;
}

function displayOptionsChain(chain) {
    const card = document.getElementById('options-card');
    if (!card) return;
    
    // Show card if instrument supports options (NFO), hide for crypto
    const isCrypto = currencySymbol === '$';
    if (isCrypto || !chain || chain.available === false) {
        card.style.display = 'none';
        return;
    }
    
    card.style.display = 'block';
    const ts = chain.timestamp || new Date().toISOString();
    updateTimestamp('options-timestamp', ts);
    document.getElementById('options-fut-price').textContent = chain.futures_price ? formatCurrency(chain.futures_price) : '-';

    const tbody = document.getElementById('options-body');
    const optionsData = chain.chain || chain.strikes || [];
    let strikeList = [];

    // Handle both array and object formats
    if (Array.isArray(optionsData)) {
        strikeList = optionsData.slice(0, 8);
    } else {
        // Object format (fallback)
        strikeList = Object.keys(optionsData).sort((a,b) => Number(a)-Number(b)).slice(0, 8).map(s => ({strike: s, ...optionsData[s]}));
    }

    if (!strikeList.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="loading">No options data (market closed or no recent expiry)</td></tr>';
        return;
    }

    let html = '';
    strikeList.forEach(row => {
        html += '<tr>' +
            `<td>${row.strike}</td>` +
            `<td>${row.ce_ltp != null ? formatCurrency(row.ce_ltp) : '-'}</td>` +
            `<td>${row.ce_oi != null ? row.ce_oi : '-'}</td>` +
            `<td>${row.pe_ltp != null ? formatCurrency(row.pe_ltp) : '-'}</td>` +
            `<td>${row.pe_oi != null ? row.pe_oi : '-'}</td>` +
            '</tr>';
    });
    tbody.innerHTML = html;
}

function displayOptionsStrategy(data) {
    const card = document.getElementById('options-strategy-card');
    if (!card) return;
    if (!data || data.available === false || !data.recommendation) {
        card.style.display = 'none';
        return;
    }
    card.style.display = 'block';
    updateTimestamp('options-strategy-timestamp', data.timestamp || new Date().toISOString());

    const rec = data.recommendation || {};
    const legs = data.legs || [];
    const strategyType = data.strategy_type || '-';
    const netDebit = (data.net_debit != null) ? data.net_debit : null;
    const legsEl = document.getElementById('opt-legs');
    document.getElementById('opt-strategy-type').textContent = strategyType;
    document.getElementById('opt-side').textContent = rec.side || '-';
    document.getElementById('opt-type').textContent = rec.option_type || '-';
    document.getElementById('opt-strike').textContent = rec.strike != null ? rec.strike : '-';
    document.getElementById('opt-premium').textContent = rec.premium != null ? formatCurrency(rec.premium) : '-';
    document.getElementById('opt-sl').textContent = rec.stop_loss_price != null ? formatCurrency(rec.stop_loss_price) : '-';
    document.getElementById('opt-tp').textContent = rec.take_profit_price != null ? formatCurrency(rec.take_profit_price) : '-';
    document.getElementById('opt-qty').textContent = rec.quantity != null ? rec.quantity : '-';
    document.getElementById('opt-expiry').textContent = data.expiry || '-';
    document.getElementById('opt-reason').textContent = rec.reasoning || '-';
    document.getElementById('opt-net-debit').textContent = netDebit != null ? formatCurrency(netDebit) : '-';

    // Render legs list if available
    if (legsEl) {
        if (Array.isArray(legs) && legs.length) {
            let html = '<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:6px;padding:6px;border:1px solid #e5e7eb;border-radius:6px;background:#f9fafb;">';
            html += '<div style="font-weight:600;">Side</div><div style="font-weight:600;">Type</div><div style="font-weight:600;">Strike</div><div style="font-weight:600;">Premium</div><div style="font-weight:600;">Qty</div>';
            legs.forEach(l => {
                html += `<div>${l.side || '-'}</div>`;
                html += `<div>${l.option_type || '-'}</div>`;
                html += `<div>${(l.strike != null) ? l.strike : '-'}</div>`;
                html += `<div>${(l.premium != null) ? formatCurrency(l.premium) : '-'}</div>`;
                html += `<div>${(l.quantity != null) ? l.quantity : '-'}</div>`;
            });
            html += '</div>';
            legsEl.innerHTML = html;
        } else {
            legsEl.innerHTML = '<div style="color:#6b7280;">No spread legs</div>';
        }
    }
}

async function executeOptionsPaperTrade() {
    const statusEl = document.getElementById('opt-trade-status');
    try {
        statusEl.textContent = 'Submitting...';
        const payload = window.LATEST_OPTIONS_STRATEGY || {};
        const res = await fetch('/api/paper-trade/options', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload && payload.available ? payload : {})
        });
        const data = await res.json();
        if (data && data.ok) {
            if (Array.isArray(data.trades)) {
                statusEl.textContent = `Created ${data.trades.length} legs` + (data.group_id ? ` | Spread ${data.group_id}` : '');
            } else if (data.trade) {
                statusEl.textContent = `Trade ${data.trade.id} created`;
            } else {
                statusEl.textContent = 'Trade created';
            }
            // Refresh trades and metrics
            loadData();
        } else {
            statusEl.textContent = data.error || 'Trade failed';
        }
    } catch (e) {
        statusEl.textContent = 'Error: ' + (e && e.message ? e.message : String(e));
    }
}

async function closeLastPaperTrade() {
    const statusEl = document.getElementById('opt-close-status');
    try {
        statusEl.textContent = 'Closing...';
        const res = await fetch('/api/paper-trade/close', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        const data = await res.json();
        if (data && data.ok) {
            statusEl.textContent = `Closed ${data.id} | P&L: ${formatCurrency(data.pnl || 0)}`;
            loadData();
        } else {
            statusEl.textContent = data.error || 'Close failed';
        }
    } catch (e) {
        statusEl.textContent = 'Error: ' + (e && e.message ? e.message : String(e));
    }
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
