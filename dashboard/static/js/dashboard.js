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
    
    // Don't update if timestamp is invalid or missing
    if (!timestamp || timestamp === 'Never' || timestamp === '') {
        el.textContent = '';
        return;
    }
    
    try {
        const relTime = formatRelativeTime(timestamp);
        const color = getStalenessColor(timestamp);
        // Always display in IST for clarity
        const absIst = new Date(timestamp).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' });
        el.innerHTML = `<span style="color: ${color};">●</span> ${label} ${relTime} (${absIst} IST)`;
    } catch (error) {
        // Invalid timestamp - clear the element
        el.textContent = '';
    }
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

// Helper function to handle API responses
async function fetchWithErrorHandling(url, defaultValue = {}) {
    try {
        const response = await fetch(url);
        if (response.ok) {
            return await response.json();
        } else if (response.status === 400) {
            // Mode not selected - return special object
            return { error: 'MODE_NOT_SELECTED', message: 'No trading mode selected' };
        } else if (response.status === 503) {
            // Service unavailable
            return { error: 'SERVICE_UNAVAILABLE', message: 'Service temporarily unavailable' };
        } else {
            // Other errors
            return defaultValue;
        }
    } catch (error) {
        console.warn(`API call to ${url} failed:`, error);
        return defaultValue;
    }
}

async function loadData() {
    try {
        const [signal, market, metrics, risk, trades, agents, portfolio, health, technicals, latestAnalysis, llm, orderflow, optionsChain, optionsStrategy, systemTime] = await Promise.all([
            fetchWithErrorHandling('/api/latest-signal', {}),
            fetchWithErrorHandling('/api/market-data', {}),
            fetchWithErrorHandling('/metrics/trading', {}),
            fetchWithErrorHandling('/metrics/risk', {}),
            fetchWithErrorHandling('/api/recent-trades?limit=20', []),
            fetchWithErrorHandling('/api/agent-status', {}),
            fetchWithErrorHandling('/api/portfolio', {positions: []}),
            fetchWithErrorHandling('/api/system-health', {}),
            fetchWithErrorHandling('/api/technical-indicators', {}),
            fetchWithErrorHandling('/api/latest-analysis', {}),
            fetchWithErrorHandling('/api/metrics/llm', {}),
            fetchWithErrorHandling('/api/order-flow', {available:false}),
            fetchWithErrorHandling('/api/options-chain', {available:false}),
            // Prefer advanced strategy; fallback to basic
            fetchWithErrorHandling('/api/options-strategy-advanced', {available:false}),
            fetchWithErrorHandling('/api/system-time', {})
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
        updateSystemTime(systemTime);
        updateMarketData(market);
        updateMetrics(metrics);
        updateRisk(risk);
        displayTrades(trades);
        displayAgents(agents, latestAnalysis);
        updateAgentConditions(agents);
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
        
        // Update data freshness and connection status based on actual market data
        const lastUpdateEl = document.getElementById('last-update');
        const connectionEl = document.getElementById('connection-status');
        
        // Check if we have real market data
        const hasRealMarketData = market && !market.error && market.timestamp && (market.currentprice || market.current_price || market.ltp);
        
        if (hasRealMarketData) {
            if (lastUpdateEl) {
                lastUpdateEl.textContent = 'Last updated: ' + new Date(market.timestamp).toLocaleTimeString();
            }
            if (connectionEl) {
                connectionEl.textContent = '● CONNECTED';
                connectionEl.style.color = '#28a745';
            }
            // Update lastDataUpdate for freshness tracking (if available in this scope)
            if (typeof lastDataUpdate !== 'undefined') {
                lastDataUpdate = new Date(market.timestamp);
            }
        } else {
            // No real data - show disconnected state
            if (lastUpdateEl) {
                lastUpdateEl.textContent = 'Never';
            }
            if (connectionEl) {
                connectionEl.textContent = '● DISCONNECTED';
                connectionEl.style.color = '#dc3545';
            }
            if (typeof lastDataUpdate !== 'undefined') {
                lastDataUpdate = null;
            }
            
            // Update data status
            const dataStatusEl = document.getElementById('data-status');
            if (dataStatusEl) {
                dataStatusEl.textContent = 'NO DATA';
                dataStatusEl.style.color = '#dc3545';
            }
        }
    } catch (error) {
        console.error('Load error:', error);
    }
}

function updateSignal(signal) {
    const card = document.getElementById('signal-card');
    const icon = {'BUY': '🚀', 'SELL': '📉', 'HOLD': '📊'}[signal.signal] || '📊';
    
    const signalIconEl = document.getElementById('signal-icon');
    const signalTextEl = document.getElementById('signal-text');
    const signalReasoningEl = document.getElementById('signal-reasoning');
    const signalConfEl = document.getElementById('signal-conf');
    const signalEntryEl = document.getElementById('signal-entry');
    const signalSlEl = document.getElementById('signal-sl');
    const signalTpEl = document.getElementById('signal-tp');
    
    if (signalIconEl) signalIconEl.textContent = icon;
    if (signalTextEl) signalTextEl.textContent = signal.signal || 'HOLD';
    if (signalReasoningEl) signalReasoningEl.textContent = signal.reasoning || 'Analysis in progress';
    if (signalConfEl) signalConfEl.textContent = signal.confidence ? formatPercent(signal.confidence) : '-';
    if (signalEntryEl) signalEntryEl.textContent = signal.entry_price ? formatCurrency(signal.entry_price) : '-';
    if (signalSlEl) signalSlEl.textContent = signal.stop_loss ? formatCurrency(signal.stop_loss) : '-';
    if (signalTpEl) signalTpEl.textContent = signal.take_profit ? formatCurrency(signal.take_profit) : '-';
    if (card) card.className = 'signal-banner ' + (signal.signal || 'HOLD').toLowerCase();
    
    // Update system time display if available
    if (signal.system_date) {
        const dateEl = document.getElementById('system-date');
        if (dateEl) dateEl.textContent = signal.system_date;
    }
    if (signal.system_time_formatted) {
        const timeEl = document.getElementById('system-time');
        if (timeEl) timeEl.textContent = signal.system_time_formatted + ' IST';
    }
}

function updateSystemTime(timeData) {
    const dateEl = document.getElementById('system-date');
    const timeEl = document.getElementById('system-time');
    const modeEl = document.getElementById('time-mode');
    const marketStatusEl = document.getElementById('market-status');
    
    if (dateEl && timeData.date) {
        dateEl.textContent = timeData.date;
    }
    
    if (timeEl && timeData.time) {
        timeEl.textContent = timeData.time + ' IST';
    }
    
    if (modeEl) {
        if (timeData.is_virtual) {
            modeEl.innerHTML = '<span style="color: #f59e0b; font-weight: 700;">⏱️ VIRTUAL (Replay)</span>';
            modeEl.title = 'Using virtual time for historical replay';
        } else {
            modeEl.innerHTML = '<span style="color: #10b981; font-weight: 700;">🕐 REAL-TIME (Live)</span>';
            modeEl.title = 'Using real-time system clock';
        }
    }
}

function updateMarketData(market) {
    // Update market data timestamp first
    const marketDataTimeEl = document.getElementById('market-data-time');
    if (marketDataTimeEl && market.timestamp && !market.error) {
        try {
            const dataTime = new Date(market.timestamp);
            const formattedTime = dataTime.toLocaleString('en-IN', { 
                timeZone: 'Asia/Kolkata',
                year: 'numeric',
                month: '2-digit', 
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            marketDataTimeEl.textContent = formattedTime + ' IST';
            marketDataTimeEl.title = 'Time when this market data was captured';
        } catch (e) {
            marketDataTimeEl.textContent = 'Invalid time';
        }
    } else if (marketDataTimeEl) {
        marketDataTimeEl.textContent = 'No data';
    }
    
    // Check for errors first - don't update timestamps if there's an error
    if (market.error || market.error === 'MODE_NOT_SELECTED' || market.error === 'SERVICE_UNAVAILABLE') {
        // Clear timestamps and show no data state
        const timestampEls = ['market-timestamp', 'market-context-timestamp', 'market-conditions-timestamp'];
        timestampEls.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '';
        });
        
        const currentPriceEl = document.getElementById('current-price');
        if (currentPriceEl) currentPriceEl.textContent = market.error === 'MODE_NOT_SELECTED' ? 'Select mode first' : 'No data';
        
        const changeEl = document.getElementById('change-24h');
        if (changeEl) {
            changeEl.textContent = market.error === 'MODE_NOT_SELECTED' ? 'No mode selected' : 'No data';
            changeEl.style.color = '#6b7280';
        }
        
        // Update connection status
        const connectionEl = document.getElementById('connection-status');
        if (connectionEl) {
            connectionEl.textContent = '● DISCONNECTED';
            connectionEl.style.color = '#dc3545';
        }
        
        return;
    }
    
    const hasData = market.currentprice || market.current_price || market.ltp;
    
    // Only update timestamps if we have real data
    if (hasData && market.timestamp) {
        const timestamp = market.timestamp || market.updated_at;
        if (timestamp) {
            dataTimestamps.market = timestamp;
            updateTimestamp('market-timestamp', timestamp);
            updateTimestamp('market-context-timestamp', timestamp);
            updateTimestamp('market-conditions-timestamp', timestamp);
        }
        
        // Update connection status to connected
        const connectionEl = document.getElementById('connection-status');
        if (connectionEl) {
            connectionEl.textContent = '● CONNECTED';
            connectionEl.style.color = '#28a745';
        }
    } else {
        // No real data - clear timestamps
        const timestampEls = ['market-timestamp', 'market-context-timestamp', 'market-conditions-timestamp'];
        timestampEls.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '';
        });
        
        // Update connection status
        const connectionEl = document.getElementById('connection-status');
        if (connectionEl) {
            connectionEl.textContent = '● DISCONNECTED';
            connectionEl.style.color = '#dc3545';
        }
    }
    
    // Safe element updates with null checks
    const currentPriceEl = document.getElementById('current-price');
    if (currentPriceEl) {
        currentPriceEl.textContent = hasData ? formatCurrency(market.currentprice || market.current_price || market.ltp) : 'No data';
    }
    
    const changePercent = market.changepercent24h || market.change_percent_24h || market.changePercent || 0;
    const changeAmount = market.change24h || market.change_24h || market.change || 0;
    
    const changeEl = document.getElementById('change-24h');
    if (changeEl) {
        changeEl.textContent = hasData ? (changePercent >= 0 ? '↗ ' : '↘ ') + formatPercent(Math.abs(changePercent)) : 'No data';
        changeEl.style.color = changePercent >= 0 ? '#28a745' : '#dc3545';
    }
    
    const dailyChangeEl = document.getElementById('daily-change');
    if (dailyChangeEl) {
        dailyChangeEl.textContent = hasData ? formatCurrency(changeAmount) : 'No data';
        dailyChangeEl.style.color = changeAmount >= 0 ? '#28a745' : '#dc3545';
    }
    
    const changePercentEl = document.getElementById('change-percent');
    if (changePercentEl) {
        changePercentEl.textContent = hasData ? formatPercent(changePercent) : 'No data';
        changePercentEl.style.color = changePercent >= 0 ? '#28a745' : '#dc3545';
    }
    
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
    const volumeEl = document.getElementById('volume-24h');
    if (volumeEl) volumeEl.textContent = volumeText;
    
    const highEl = document.getElementById('high-24h');
    if (highEl) highEl.textContent = market.high24h || market.high_24h || market.high ? formatCurrency(market.high24h || market.high_24h || market.high) : 'No data';
    
    const lowEl = document.getElementById('low-24h');
    if (lowEl) lowEl.textContent = market.low24h || market.low_24h || market.low ? formatCurrency(market.low24h || market.low_24h || market.low) : 'No data';
    
    const vwapEl = document.getElementById('vwap');
    if (vwapEl) vwapEl.textContent = market.vwap ? formatCurrency(market.vwap) : 'No data';
    
    const marketStatusEl = document.getElementById('market-status');
    if (marketStatusEl) marketStatusEl.textContent = market.marketopen || market.market_open || market.isOpen ? '🟢 Open' : '🔴 Closed';
}

function updateMetrics(m) {
    // Check for errors first - don't update timestamps if there's an error
    if (m.error || m.error === 'MODE_NOT_SELECTED' || m.error === 'SERVICE_UNAVAILABLE') {
        // Clear timestamps
        const timestampEls = ['metrics-timestamp', 'performance-timestamp', 'performance-metrics-timestamp', 'risk-monitor-timestamp'];
        timestampEls.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '';
        });
        
        const totalPnlEl = document.getElementById('total-pnl');
        if (totalPnlEl) totalPnlEl.textContent = m.error === 'MODE_NOT_SELECTED' ? 'Select mode first' : 'No data';
        
        const winRateEl = document.getElementById('win-rate');
        if (winRateEl) winRateEl.textContent = m.error === 'MODE_NOT_SELECTED' ? 'Select mode first' : 'No data';
        
        // Update Full Dashboard tab metrics
        const totalPnlFullEl = document.getElementById('total-pnl-full');
        if (totalPnlFullEl) totalPnlFullEl.textContent = m.error === 'MODE_NOT_SELECTED' ? 'Select mode first' : 'No data';
        
        const winRateFullEl = document.getElementById('win-rate-full');
        if (winRateFullEl) winRateFullEl.textContent = m.error === 'MODE_NOT_SELECTED' ? 'Select mode first' : 'No data';
        
        return;
    }
    
    // Only update timestamps if we have real data
    if (m.timestamp) {
        const timestamp = m.timestamp || m.updated_at;
        if (timestamp) {
            dataTimestamps.metrics = timestamp;
            updateTimestamp('metrics-timestamp', timestamp);
            updateTimestamp('performance-timestamp', timestamp);
            updateTimestamp('performance-metrics-timestamp', timestamp);
        }
    } else {
        // Clear timestamps if no timestamp in response
        const timestampEls = ['metrics-timestamp', 'performance-timestamp', 'performance-metrics-timestamp', 'risk-monitor-timestamp'];
        timestampEls.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '';
        });
    }

    const totalPnl = m.total_pnl || m.totalpnl || 0;
    const winRate = m.win_rate || m.winrate || 0;
    const totalTrades = m.total_trades || m.totaltrades || 0;
    const profitFactor = m.profit_factor || m.profitfactor || 0;
    const sharpeRatio = m.sharpe_ratio || m.sharperatio || 0;
    const avgWin = m.avg_win || m.avgwin || 0;

    const totalPnlEl = document.getElementById('total-pnl');
    if (totalPnlEl) totalPnlEl.textContent = totalTrades > 0 ? formatCurrency(totalPnl) : 'No trades yet';
    
    const winRateEl = document.getElementById('win-rate');
    if (winRateEl) winRateEl.textContent = totalTrades > 0 ? formatPercent(winRate) : 'No trades yet';
    
    const totalTradesEl = document.getElementById('total-trades');
    if (totalTradesEl) totalTradesEl.textContent = totalTrades || 'No data';
    
    const profitFactorEl = document.getElementById('profit-factor');
    if (profitFactorEl) profitFactorEl.textContent = totalTrades > 0 ? profitFactor.toFixed(2) : 'No data';
    
    const sharpeRatioEl = document.getElementById('sharpe-ratio');
    if (sharpeRatioEl) sharpeRatioEl.textContent = totalTrades > 0 ? sharpeRatio.toFixed(2) : 'No data';
    
    const avgWinEl = document.getElementById('avg-win');
    if (avgWinEl) avgWinEl.textContent = totalTrades > 0 ? formatCurrency(avgWin) : 'No data';
    
    // Update Full Dashboard tab metrics
    const totalPnlFullEl = document.getElementById('total-pnl-full');
    if (totalPnlFullEl) {
        totalPnlFullEl.textContent = totalTrades > 0 ? formatCurrency(totalPnl) : 'No trades yet';
        totalPnlFullEl.style.color = totalPnl >= 0 ? '#28a745' : '#dc3545';
    }
    
    const winRateFullEl = document.getElementById('win-rate-full');
    if (winRateFullEl) winRateFullEl.textContent = totalTrades > 0 ? formatPercent(winRate) : 'No trades yet';
    
    const sharpeRatioFullEl = document.getElementById('sharpe-ratio-full');
    if (sharpeRatioFullEl) sharpeRatioFullEl.textContent = totalTrades > 0 ? sharpeRatio.toFixed(2) : 'No data';
    
    const maxDrawdownFullEl = document.getElementById('max-drawdown-full');
    if (maxDrawdownFullEl) {
        const maxDrawdown = m.max_drawdown || m.maxdrawdown || 0;
        maxDrawdownFullEl.textContent = totalTrades > 0 ? formatPercent(maxDrawdown) : 'No data';
        maxDrawdownFullEl.style.color = '#dc3545'; // Always red for drawdown
    }
}

function updateRisk(r) {
    // Check for errors first - don't update timestamps if there's an error
    if (r.error || r.error === 'MODE_NOT_SELECTED' || r.error === 'SERVICE_UNAVAILABLE') {
        // Clear timestamps
        const timestampEls = ['risk-timestamp', 'risk-monitor-timestamp'];
        timestampEls.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '';
        });
        return;
    }
    
    // Only update timestamps if we have real data
    if (r.timestamp) {
        const timestamp = r.timestamp || r.updated_at;
        if (timestamp) {
            dataTimestamps.risk = timestamp;
            updateTimestamp('risk-timestamp', timestamp);
            updateTimestamp('risk-monitor-timestamp', timestamp);
        }
    } else {
        // Clear timestamps if no timestamp in response
        const timestampEls = ['risk-timestamp', 'risk-monitor-timestamp'];
        timestampEls.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '';
        });
    }
    
    const hasData = r.sharperatio || r.sharpe_ratio;
    
    const sharpeEl = document.getElementById('sharpe');
    if (sharpeEl) sharpeEl.textContent = hasData ? (r.sharperatio || r.sharpe_ratio).toFixed(2) : 'No data';
    
    const drawdownEl = document.getElementById('drawdown');
    if (drawdownEl) drawdownEl.textContent = hasData ? formatCurrency(r.maxdrawdown || r.max_drawdown || 0) : 'No data';
    
    const var95El = document.getElementById('var-95');
    if (var95El) var95El.textContent = r.var95 || r.var_95 ? formatCurrency(r.var95 || r.var_95) : 'Not calculated';
    
    const exposureEl = document.getElementById('total-exposure');
    if (exposureEl) exposureEl.textContent = r.totalexposure || r.total_exposure ? formatCurrency(r.totalexposure || r.total_exposure) : 'Not calculated';
    
    const portfolioEl = document.getElementById('portfolio-value');
    if (portfolioEl) portfolioEl.textContent = r.portfoliovalue || r.portfolio_value ? formatCurrency(r.portfoliovalue || r.portfolio_value) : 'Not calculated';
    
    const winLossRatio = r.win_loss_ratio || r.winlossratio || 0;
    const ratioEl = document.getElementById('win-loss-ratio');
    if (ratioEl) ratioEl.textContent = winLossRatio ? winLossRatio.toFixed(2) : 'Not calculated';
}

function displayTrades(trades) {
    // Get timestamp from first trade or use current time
    const timestamp = (trades && trades.length > 0 && trades[0].timestamp) ? trades[0].timestamp : new Date().toISOString();
    updateTimestamp('recent-trades-timestamp', timestamp);
    
    const tbody = document.getElementById('trades-body');
    if (!trades || trades.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading">No trades yet</td></tr>';
        return;
    }
    let html = '';
    trades.forEach(t => {
        const pnl = t.pnl || 0;
        html += '<tr>' +
            '<td>' + new Date(t.timestamp).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' }) + '</td>' +
            '<td><span class="badge-small badge-' + (t.side || 'hold').toLowerCase() + '">' + (t.side || 'HOLD') + '</span></td>' +
            '<td>' + (t.strike != null ? t.strike : '-') + '</td>' +
            '<td>' + (t.option_type || '-') + '</td>' +
            '<td>' + formatCurrency(t.price || t.entry_price || 0) + '</td>' +
            '<td>' + (t.exit_price ? formatCurrency(t.exit_price) : '-') + '</td>' +
            '<td style="color: ' + (pnl >= 0 ? '#10b981' : '#ef4444') + '">' + formatCurrency(pnl) + '</td>' +
            '<td><span class="badge-small badge-' + (t.status || 'open').toLowerCase() + '">' + (t.status || 'OPEN') + '</span></td>' +
            '</tr>';
    });
    tbody.innerHTML = html;
}

function displayAgents(agents, latestAnalysis) {
    // Update timestamps
    const timestamp = agents.timestamp || agents.last_analysis || agents.updated_at || new Date().toISOString();
    updateTimestamp('agent-summary-timestamp', timestamp);
    updateTimestamp('agent-decisions-timestamp', timestamp);
    updateTimestamp('agent-conditions-timestamp', timestamp);
    
    const container = document.getElementById('agents-container');
    const discussionEl = document.getElementById('agent-discussion-time');

    if (!agents || agents.error) {
        if (container) container.innerHTML = '<div class="loading" style="grid-column: 1/-1;">Agents unavailable</div>';
        if (discussionEl) discussionEl.textContent = 'No recent discussion';
        return;
    }

    if (!agents.agents || Object.keys(agents.agents).length === 0) {
        container.innerHTML = '<div class="loading" style="grid-column: 1/-1;">No agents active</div>';
        if (discussionEl) discussionEl.textContent = 'No discussion yet';
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
        let lastColor = '#9ca3af';
        if (lastTs) {
            const rel = formatRelativeTime(lastTs);
            const absTime = new Date(lastTs).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' });
            lastText = `${rel} (${absTime} IST)`;
            lastColor = '#007bff';
            const freshness = agents.data_freshness || {};
            if (freshness.analysis_stale || freshness.last_discussion_age_seconds > freshness.stale_threshold_seconds) {
                lastColor = '#ef4444';
                lastText = `Stale • ${lastText}`;
            }
        }

        if (discussionEl) {
            discussionEl.textContent = lastText;
            discussionEl.style.color = lastColor;
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

function updateAgentConditions(agents) {
    // Check for mode selection error
    if (agents && agents.error === 'MODE_NOT_SELECTED') {
        const agentMappings = {
            'momentum': { statusId: 'momentum-status', conditionId: 'momentum-condition' },
            'trend': { statusId: 'trend-status', conditionId: 'trend-condition' },
            'mean_reversion': { statusId: 'reversion-status', conditionId: 'reversion-condition' },
            'volume': { statusId: 'volume-status', conditionId: 'volume-condition' }
        };

        Object.values(agentMappings).forEach(mapping => {
            const statusEl = document.getElementById(mapping.statusId);
            const conditionEl = document.getElementById(mapping.conditionId);
            if (statusEl) statusEl.textContent = 'Select mode first';
            if (conditionEl) conditionEl.textContent = 'No mode selected';
        });
        
        const messageEl = document.getElementById('agent-status-message');
        if (messageEl) {
            messageEl.innerHTML = '<strong>🔄 Live Status:</strong> Please select a trading mode to view agent status.';
        }
        return;
    }

    // Update agent condition monitoring section
    const agentMappings = {
        'momentum': { statusId: 'momentum-status', conditionId: 'momentum-condition', defaultCondition: 'RSI > 70 + Volume spike' },
        'trend': { statusId: 'trend-status', conditionId: 'trend-condition', defaultCondition: 'ADX > 25 + SMA breakout' },
        'mean_reversion': { statusId: 'reversion-status', conditionId: 'reversion-condition', defaultCondition: 'BB touch + RSI extreme' },
        'volume': { statusId: 'volume-status', conditionId: 'volume-condition', defaultCondition: 'Volume 3x + price action' }
    };

    if (!agents || !agents.agents) {
        // Set all to loading state
        Object.values(agentMappings).forEach(mapping => {
            const statusEl = document.getElementById(mapping.statusId);
            const conditionEl = document.getElementById(mapping.conditionId);
            if (statusEl) statusEl.textContent = 'Loading...';
            if (conditionEl) conditionEl.textContent = 'Loading conditions...';
        });
        
        const messageEl = document.getElementById('agent-status-message');
        if (messageEl) {
            messageEl.innerHTML = '<strong>🔄 Live Status:</strong> Connecting to agent system...';
        }
        return;
    }

    let readyCount = 0;
    let totalCount = 0;

    Object.entries(agentMappings).forEach(([agentKey, mapping]) => {
        const agent = agents.agents[agentKey];
        const statusEl = document.getElementById(mapping.statusId);
        const conditionEl = document.getElementById(mapping.conditionId);
        totalCount++;

        if (agent) {
            // Update status
            let statusText = 'UNKNOWN';
            let statusColor = '#6b7280'; // gray

            if (agent.status === 'active') {
                statusText = 'READY';
                statusColor = '#28a745'; // green
                readyCount++;
            } else if (agent.status === 'waiting' || agent.status === 'inactive') {
                statusText = 'WAITING';
                statusColor = '#ffc107'; // yellow
            } else if (agent.status === 'stale') {
                statusText = 'STALE';
                statusColor = '#fd7e14'; // orange
            }

            if (statusEl) {
                statusEl.textContent = statusText;
                statusEl.style.color = statusColor;
            }

            // Update condition
            const condition = agent.condition || agent.conditions || mapping.defaultCondition;
            if (conditionEl) {
                conditionEl.textContent = condition;
            }
        } else {
            // Agent not found, show default
            if (statusEl) {
                statusEl.textContent = 'WAITING';
                statusEl.style.color = '#ffc107';
            }
            if (conditionEl) {
                conditionEl.textContent = mapping.defaultCondition;
            }
        }
    });

    // Update status message
    const messageEl = document.getElementById('agent-status-message');
    if (messageEl) {
        if (readyCount === totalCount) {
            messageEl.innerHTML = '<strong>🔄 Live Status:</strong> All agents are actively monitoring technical conditions.';
        } else if (readyCount > 0) {
            messageEl.innerHTML = `<strong>🔄 Live Status:</strong> ${readyCount}/${totalCount} agents ready. Use "Check Conditions" on signals for real-time status.`;
        } else {
            messageEl.innerHTML = '<strong>🔄 Live Status:</strong> Agents are initializing. Check back in a few moments.';
        }
    }
}

function displayTechnicals(data) {
    const timestamp = data.timestamp || data.updated_at || new Date().toISOString();
    updateTimestamp('technical-indicators-timestamp', timestamp);
    
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
    const timestamp = portfolio.timestamp || portfolio.updated_at || new Date().toISOString();
    updateTimestamp('positions-timestamp', timestamp);
    
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
    const timestamp = health.timestamp || health.updated_at || new Date().toISOString();
    updateTimestamp('system-status-timestamp', timestamp);
    
    const providerLabel = document.getElementById('llm-provider');
    const systemTextEl = document.getElementById('system-status-text');

    // Choose active LLM provider from health check or metrics
    let activeProvider = (health && health.llm_active_provider) || null;
    if (!activeProvider && llmMetrics && Array.isArray(llmMetrics.providers) && llmMetrics.providers.length) {
        const healthy = llmMetrics.providers.find(p => p.status === 'available' || p.status === 'healthy');
        activeProvider = (healthy && healthy.name) || llmMetrics.providers[0].name;
    }
    if (providerLabel) providerLabel.textContent = activeProvider || 'Unknown';

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
    if (dataFeedEl) {
        if (mongodb && mongodb.status === 'healthy') {
            dataFeedEl.textContent = '✓ Active';
            dataFeedEl.style.color = '#10b981';
        } else {
            dataFeedEl.textContent = '✗ Error';
            dataFeedEl.style.color = '#ef4444';
        }
    }

    const agentsEl = document.getElementById('agents-status');
    if (agentsEl) {
        if (agents.agents && Object.keys(agents.agents).length > 0) {
            const activeCount = Object.values(agents.agents).filter(a => a.status === 'active').length;
            agentsEl.textContent = `${activeCount} Active`;
            agentsEl.style.color = '#10b981';
        } else {
            agentsEl.textContent = 'Initializing';
            agentsEl.style.color = '#f59e0b';
        }
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
    document.getElementById('options-expiry').textContent = chain.expiry || '-';
    document.getElementById('options-pcr').textContent = chain.pcr != null ? chain.pcr.toFixed(2) : '-';
    document.getElementById('options-max-pain').textContent = chain.max_pain ? formatCurrency(chain.max_pain) : '-';

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
            `<td style="text-align: center; padding: 6px;">${row.strike}</td>` +
            `<td style="text-align: center; padding: 6px;">${row.ce_ltp != null ? formatCurrency(row.ce_ltp) : '-'}</td>` +
            `<td style="text-align: center; padding: 6px;">${row.ce_oi != null ? row.ce_oi.toLocaleString() : '-'}</td>` +
            `<td style="text-align: center; padding: 6px;">${row.pe_ltp != null ? formatCurrency(row.pe_ltp) : '-'}</td>` +
            `<td style="text-align: center; padding: 6px;">${row.pe_oi != null ? row.pe_oi.toLocaleString() : '-'}</td>` +
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
            html += '<div style="font-weight:600;">Side</div><div style="font-weight:600;">Type</div><div style="font-weight:600;">Strike</div><div style="font-weight:600;">Option Premium (₹)</div><div style="font-weight:600;">Qty</div>';
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
    
    // Check for auto-switch every 30 seconds
    if (refreshCountdown % 30 === 0) {
        updateModeStatus();
    }
}, 1000);

// Auto-load data on page load and every 10 seconds
loadData();
updateModeStatus(); // Load mode status on startup
setInterval(() => {
    refreshCountdown = 10;
    loadData();
    updateModeStatus(); // Check mode status periodically
}, 10000);


// ============================================================================
// CONTROL PANEL FUNCTIONS
// ============================================================================

// Historical Replay UI Functions
function updateHistoricalReplayInfo(histConfig) {
    const infoPanel = document.getElementById('mode-switch-info');
    const infoText = document.getElementById('historical-info-text');
    if (infoPanel && infoText && histConfig) {
        infoText.textContent = `${histConfig.start_date} to ${histConfig.end_date || 'Today'} (${histConfig.interval})`;
        infoPanel.style.display = 'block';
    }
}

function toggleHistoricalReplayOptions() {
    // This function is no longer needed as historical replay is independent
    // But keeping for backward compatibility
}

function toggleHistoricalDateInputs() {
    const enableCheckbox = document.getElementById('enable-historical-replay');
    const dateInputs = document.getElementById('historical-date-inputs');
    
    if (enableCheckbox && dateInputs) {
        if (enableCheckbox.checked) {
            dateInputs.style.display = 'block';
        } else {
            dateInputs.style.display = 'none';
        }
    }
}

function loadHistoricalReplayPreferences() {
    try {
        let config = null;
        
        // 1. Try to load from server config first (persistent)
        if (typeof SERVER_PAPER_CONFIG !== 'undefined' && SERVER_PAPER_CONFIG.historical_replay) {
            config = SERVER_PAPER_CONFIG.historical_replay;
            config.enabled = true;
        } 
        // 2. Fallback to localStorage (browser cache)
        else {
            const saved = localStorage.getItem('historical_replay_config');
            if (saved) {
                config = JSON.parse(saved);
            }
        }

        if (config) {
            const enableCheckbox = document.getElementById('enable-historical-replay');
            const startDateInput = document.getElementById('historical-start-date');
            const endDateInput = document.getElementById('historical-end-date');
            const intervalSelect = document.getElementById('historical-interval');
            
            if (config.enabled && enableCheckbox) {
                enableCheckbox.checked = true;
                toggleHistoricalDateInputs();
                
                if (config.start_date && startDateInput) {
                    startDateInput.value = config.start_date;
                }
                if (config.end_date && endDateInput) {
                    endDateInput.value = config.end_date;
                }
                if (config.interval && intervalSelect) {
                    intervalSelect.value = config.interval;
                }
            }
        } else {
            // Set default: last 30 days
            const today = new Date();
            const thirtyDaysAgo = new Date(today);
            thirtyDaysAgo.setDate(today.getDate() - 30);
            
            const startDateInput = document.getElementById('historical-start-date');
            if (startDateInput) {
                startDateInput.value = thirtyDaysAgo.toISOString().split('T')[0];
            }
        }
    } catch (e) {
        console.error('Error loading historical replay preferences:', e);
    }
}

// Historical Replay Preset Functions
function setHistoricalPreset(preset) {
    const enableCheckbox = document.getElementById('enable-historical-replay');
    const startDateInput = document.getElementById('historical-start-date');
    const endDateInput = document.getElementById('historical-end-date');
    
    if (!enableCheckbox || !startDateInput) return;
    
    // Enable historical replay
    enableCheckbox.checked = true;
    toggleHistoricalDateInputs();
    
    // Calculate dates
    const today = new Date();
    let startDate = new Date();
    
    switch(preset) {
        case 'last7days':
            startDate.setDate(today.getDate() - 7);
            break;
        case 'last30days':
            startDate.setDate(today.getDate() - 30);
            break;
        case 'last90days':
            startDate.setDate(today.getDate() - 90);
            break;
        case 'lastyear':
            startDate.setFullYear(today.getFullYear() - 1);
            break;
    }
    
    startDateInput.value = startDate.toISOString().split('T')[0];
    if (endDateInput) {
        endDateInput.value = ''; // Clear end date (defaults to today)
    }
}

// Update mode switch info when paper_mock is selected
function updateModeSwitchInfo() {
    const paperMockRadio = document.getElementById('mode_paper_mock');
    const infoPanel = document.getElementById('mode-switch-info');
    
    if (paperMockRadio && paperMockRadio.checked) {
        const enableHistorical = document.getElementById('enable-historical-replay')?.checked;
        const startDate = document.getElementById('historical-start-date')?.value;
        const endDate = document.getElementById('historical-end-date')?.value;
        const interval = document.getElementById('historical-interval')?.value;
        
        if (enableHistorical && startDate && infoPanel) {
            const infoText = document.getElementById('historical-info-text');
            if (infoText) {
                infoText.textContent = `${startDate} to ${endDate || 'Today'} (${interval})`;
                infoPanel.style.display = 'block';
            }
        } else if (infoPanel) {
            infoPanel.style.display = 'none';
        }
    } else if (infoPanel) {
        infoPanel.style.display = 'none';
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Load historical replay preferences
    loadHistoricalReplayPreferences();
    
    // Add change listeners to all mode radios
    document.querySelectorAll('input[name="tradingMode"]').forEach(radio => {
        radio.addEventListener('change', updateModeSwitchInfo);
    });
    
    // Update when historical replay checkbox changes
    const enableCheckbox = document.getElementById('enable-historical-replay');
    if (enableCheckbox) {
        enableCheckbox.addEventListener('change', () => {
            toggleHistoricalDateInputs();
            updateModeSwitchInfo();
        });
    }
    
    // Update when date inputs change
    ['historical-start-date', 'historical-end-date', 'historical-interval'].forEach(id => {
        const input = document.getElementById(id);
        if (input) {
            input.addEventListener('change', updateModeSwitchInfo);
        }
    });
});

async function loadControlStatus() {
    try {
        const res = await fetch('/api/control/status');
        const data = await res.json();
        
        if (data.success) {
            // Update mode radio buttons
            const modeRadio = document.querySelector(`input[name="tradingMode"][value="${data.mode}"]`);
            if (modeRadio) {
                modeRadio.checked = true;
                // Trigger UI update for historical replay options
                toggleHistoricalReplayOptions();
            }
            
            // Update mode status display
            const modeStatusEl = document.getElementById('mode-status');
            const currentModeEl = document.getElementById('current-mode-display');
            const modeDescEl = document.getElementById('mode-description');
            
            if (modeStatusEl && currentModeEl) {
                modeStatusEl.style.display = 'block';
                currentModeEl.textContent = data.mode.toUpperCase().replace('_', ' ');
                
                const descriptions = {
                    'paper_mock': 'Using simulated market data with paper trading - Safe for learning',
                    'paper_live': 'Using live Zerodha data with paper trading - Test strategies with real market',
                    'live': '⚠️ Real money trading active - Trades execute with real capital'
                };
                modeDescEl.textContent = descriptions[data.mode] || '';
                
                // Change color based on mode
                if (data.mode === 'live') {
                    modeStatusEl.style.background = '#fee2e2';
                    modeStatusEl.style.borderColor = '#dc3545';
                    currentModeEl.style.color = '#dc3545';
                } else if (data.mode === 'paper_live') {
                    modeStatusEl.style.background = '#fff3cd';
                    modeStatusEl.style.borderColor = '#ffc107';
                    currentModeEl.style.color = '#ffc107';
                } else {
                    modeStatusEl.style.background = '#e7f3ff';
                    modeStatusEl.style.borderColor = '#007bff';
                    currentModeEl.style.color = '#007bff';
                }
            }
            
            // Update Zerodha auth status
            const authStatusEl = document.getElementById('auth-connection-status');
            const credStatusEl = document.getElementById('auth-credentials-status');
            const tokenExpiryEl = document.getElementById('auth-token-expiry');
            const connectBtn = document.getElementById('connect-btn');
            const disconnectBtn = document.getElementById('disconnect-btn');
            
            if (authStatusEl) {
                authStatusEl.textContent = data.zerodha.connected ? '🟢 Connected' : '🔴 Disconnected';
                authStatusEl.style.color = data.zerodha.connected ? '#28a745' : '#dc3545';
            }
            if (credStatusEl) {
                credStatusEl.textContent = data.zerodha.has_credentials ? '✅ Configured' : '❌ Missing';
                credStatusEl.style.color = data.zerodha.has_credentials ? '#28a745' : '#dc3545';
            }
            if (tokenExpiryEl && data.zerodha.token_expiry) {
                const expiry = new Date(data.zerodha.token_expiry);
                tokenExpiryEl.textContent = expiry.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });
            } else if (tokenExpiryEl) {
                tokenExpiryEl.textContent = 'No token';
            }
            
            // Show/hide connect/disconnect buttons
            if (connectBtn && disconnectBtn) {
                if (data.zerodha.connected) {
                    connectBtn.style.display = 'none';
                    disconnectBtn.style.display = 'block';
                } else {
                    connectBtn.style.display = 'block';
                    disconnectBtn.style.display = 'none';
                }
            }
            
            // Update balances
            if (data.balances) {
                const paperMockEl = document.getElementById('balance-paper-mock');
                const paperLiveEl = document.getElementById('balance-paper-live');
                const liveEl = document.getElementById('balance-live');
                const currentEl = document.getElementById('balance-current');
                
                if (paperMockEl) paperMockEl.textContent = formatCurrency(data.balances.paper_mock || 0);
                if (paperLiveEl) paperLiveEl.textContent = formatCurrency(data.balances.paper_live || 0);
                if (liveEl) liveEl.textContent = formatCurrency(data.balances.live || 0);
                if (currentEl) currentEl.textContent = formatCurrency(data.balances[data.mode] || 0);
            }
            
            // Update portfolio stats
            if (data.portfolio) {
                const tradesCountEl = document.getElementById('portfolio-trades-count');
                const positionsCountEl = document.getElementById('portfolio-positions-count');
                
                if (tradesCountEl) tradesCountEl.textContent = data.portfolio.paper_trades_count || 0;
                if (positionsCountEl) positionsCountEl.textContent = data.portfolio.active_positions || 0;
            }
        }
    } catch (e) {
        console.error('Error loading control status:', e);
    }
}

async function updateModeStatus() {
    try {
        const res = await fetch('/api/control/mode/info');
        const data = await res.json();
        
        if (data.success) {
            // Update mode badge
            const modeBadge = document.getElementById('mode-badge');
            if (modeBadge) {
                const modeLabels = {
                    'paper_mock': '📊 MOCK MODE',
                    'paper_live': '🟢 LIVE DATA',
                    'live': '⚠️ LIVE TRADING'
                };
                const modeColors = {
                    'paper_mock': { bg: '#e7f3ff', border: '#007bff', text: '#007bff' },
                    'paper_live': { bg: '#fff3cd', border: '#ffc107', text: '#ffc107' },
                    'live': { bg: '#fee2e2', border: '#dc3545', text: '#dc3545' }
                };
                const mode = data.current_mode;
                
                if (!mode) {
                    // No mode selected
                    modeBadge.textContent = '❌ NO MODE SELECTED';
                    modeBadge.style.background = '#f8f9fa';
                    modeBadge.style.borderColor = '#6c757d';
                    modeBadge.style.color = '#6c757d';
                } else {
                    modeBadge.textContent = modeLabels[mode] || '❓ UNKNOWN';
                    const colors = modeColors[mode] || modeColors['paper_mock'];
                    modeBadge.style.background = colors.bg;
                    modeBadge.style.borderColor = colors.border;
                    modeBadge.style.color = colors.text;
                }
            }
            
            // Update market status badge
            const marketBadge = document.getElementById('market-status-badge');
            const replayTimeBadge = document.getElementById('historical-replay-time');
            
            if (marketBadge && data.market) {
                // Check if historical replay is active
                if (data.historical_replay && data.historical_replay.active) {
                    // Show yellow badge for historical replay
                    marketBadge.textContent = '🟡 Historical Replay';
                    marketBadge.style.background = '#f59e0b'; // Yellow/amber
                    marketBadge.style.color = '#ffffff';
                    marketBadge.title = `Replaying: ${data.historical_replay.start_date} to ${data.historical_replay.end_date || 'Today'} (${data.historical_replay.interval})`;
                    
                    // Show separate replay time badge
                    if (replayTimeBadge) {
                        const currentTime = data.historical_replay.current_time;
                        if (currentTime) {
                            try {
                                const replayDate = new Date(currentTime);
                                const dateStr = replayDate.toLocaleDateString('en-IN', { 
                                    year: 'numeric', 
                                    month: 'short', 
                                    day: 'numeric' 
                                });
                                const timeStr = replayDate.toLocaleTimeString('en-IN', { 
                                    hour: '2-digit', 
                                    minute: '2-digit',
                                    second: '2-digit',
                                    timeZone: 'Asia/Kolkata'
                                });
                                replayTimeBadge.textContent = `📅 ${dateStr} ${timeStr} IST`;
                                replayTimeBadge.style.display = 'inline-block';
                                replayTimeBadge.title = `Current Replay Time\nRange: ${data.historical_replay.start_date} to ${data.historical_replay.end_date || 'Today'}`;
                            } catch (e) {
                                console.error('Error parsing replay time:', e);
                                replayTimeBadge.style.display = 'none';
                            }
                        } else {
                            replayTimeBadge.style.display = 'none';
                        }
                    }
                } else {
                    // Hide replay time badge when not in historical mode
                    if (replayTimeBadge) {
                        replayTimeBadge.style.display = 'none';
                    }
                    
                    if (data.market.open) {
                        marketBadge.textContent = '🟢 Market OPEN';
                        marketBadge.style.background = '#10b981';
                        marketBadge.style.color = '#ffffff';
                        marketBadge.title = data.market.status;
                    } else {
                        marketBadge.textContent = '🔴 Market CLOSED';
                        marketBadge.style.background = '#ef4444';
                        marketBadge.style.color = '#ffffff';
                        marketBadge.title = data.market.status;
                    }
                }
            }
            
            // Update database badge
            const dbBadge = document.getElementById('database-badge');
            if (dbBadge && data.database) {
                const dbName = data.database.replace('zerodha_trading_', '');
                dbBadge.textContent = `📊 ${dbName.toUpperCase()}`;
                dbBadge.title = `Database: ${data.database}`;
            }
            
            // Show auto-switch notification if needed
            if (data.mode_info && data.mode_info.should_auto_switch && !data.mode_info.has_manual_override) {
                const suggested = data.mode_info.auto_switch_suggested;
                if (suggested && suggested !== 'live') {
                    // Auto-switch for non-live modes
                    setTimeout(async () => {
                        await performAutoSwitch();
                    }, 2000);
                } else if (suggested === 'live') {
                    // Show notification for live mode (requires confirmation)
                    showAutoSwitchNotification(data.mode_info);
                }
            }
        }
    } catch (e) {
        console.error('Error updating mode status:', e);
    }
}

async function performAutoSwitch() {
    try {
        const res = await fetch('/api/control/mode/auto-switch');
        const data = await res.json();
        
        if (data.success && data.should_switch) {
            console.log(`Auto-switched to ${data.suggested_mode}: ${data.reason}`);
            await updateModeStatus();
            await loadControlStatus();
            await loadData();
        }
    } catch (e) {
        console.error('Error performing auto-switch:', e);
    }
}

function showAutoSwitchNotification(modeInfo) {
    // Create notification element if it doesn't exist
    let notification = document.getElementById('auto-switch-notification');
    if (!notification) {
        notification = document.createElement('div');
        notification.id = 'auto-switch-notification';
        notification.style.cssText = 'position: fixed; top: 20px; right: 20px; background: #fff3cd; border: 2px solid #ffc107; padding: 15px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); z-index: 10000; max-width: 400px;';
        document.body.appendChild(notification);
    }
    
    notification.innerHTML = `
        <div style="font-weight: bold; margin-bottom: 10px;">🔄 Auto-Switch Available</div>
        <div style="margin-bottom: 10px;">${modeInfo.auto_switch_reason}</div>
        <div style="display: flex; gap: 10px;">
            <button onclick="confirmAutoSwitch('${modeInfo.auto_switch_suggested}')" style="flex: 1; padding: 8px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer;">Switch to ${modeInfo.auto_switch_suggested}</button>
            <button onclick="dismissAutoSwitch()" style="flex: 1; padding: 8px; background: #6c757d; color: white; border: none; border-radius: 4px; cursor: pointer;">Dismiss</button>
        </div>
    `;
}

async function confirmAutoSwitch(mode) {
    if (mode === 'live') {
        const confirmed = confirm(
            '⚠️ WARNING: Auto-switching to LIVE TRADING mode.\n\n' +
            'This will execute REAL trades with REAL money.\n\n' +
            'Are you absolutely sure you want to continue?'
        );
        if (!confirmed) {
            dismissAutoSwitch();
            return;
        }
    }
    
    try {
        const res = await fetch('/api/control/mode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode, confirm: mode === 'live' })
        });
        
        const data = await res.json();
        
        if (data.success) {
            dismissAutoSwitch();
            await updateModeStatus();
            await loadControlStatus();
            await loadData();
        } else if (data.error === 'CONFIRMATION_REQUIRED') {
            // Already handled above
        } else {
            alert(`❌ Failed to switch: ${data.error}`);
        }
    } catch (e) {
        alert(`Error: ${e.message}`);
        console.error('Error confirming auto-switch:', e);
    }
}

function dismissAutoSwitch() {
    const notification = document.getElementById('auto-switch-notification');
    if (notification) {
        notification.remove();
    }
}

async function applyTradingMode() {
    const selectedMode = document.querySelector('input[name="tradingMode"]:checked');
    if (!selectedMode) {
        alert('Please select a trading mode');
        return;
    }
    
    const mode = selectedMode.value;
    
    // Confirm if switching to live mode
    let confirmFlag = false;
    if (mode === 'live') {
        const confirmed = confirm(
            '⚠️ WARNING: You are switching to LIVE TRADING mode.\n\n' +
            'This will execute REAL trades with REAL money.\n\n' +
            'Are you absolutely sure you want to continue?'
        );
        if (!confirmed) return;
        confirmFlag = true;
    }
    
    // Collect historical replay parameters if paper_mock mode
    // Automatically use configured dates from Historical Replay Configuration panel
    const payload = { mode, confirm: confirmFlag };
    
    if (mode === 'paper_mock') {
        // Always check if historical replay is enabled (from the configuration panel)
        const enableHistorical = document.getElementById('enable-historical-replay')?.checked;
        if (enableHistorical) {
            const startDate = document.getElementById('historical-start-date')?.value;
            const endDate = document.getElementById('historical-end-date')?.value;
            const interval = document.getElementById('historical-interval')?.value;
            
            if (startDate) {
                payload.historical_start_date = startDate;
                if (endDate) {
                    payload.historical_end_date = endDate;
                }
                if (interval) {
                    payload.historical_interval = interval;
                }
            } else {
                // Warn if enabled but no date selected
                const proceed = confirm(
                    'Historical Replay is enabled but no start date is set.\n\n' +
                    'Would you like to continue with simulated data instead?'
                );
                if (!proceed) return;
            }
        }
    }
    
    try {
        const res = await fetch('/api/control/mode/switch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const data = await res.json();
        
        if (data.success) {
            let message = `✅ Successfully switched to ${mode.toUpperCase().replace('_', ' ')} mode\n\nDatabase: ${data.database}\n\n${data.message}`;
            if (data.historical_replay) {
                message += `\n\n📅 Historical Replay Active:\nStart: ${data.historical_replay.start_date}\nEnd: ${data.historical_replay.end_date || 'Today'}\nInterval: ${data.historical_replay.interval}`;
                // Update UI to show historical replay info
                updateHistoricalReplayInfo(data.historical_replay);
            } else {
                // Hide historical replay info if not active
                const infoPanel = document.getElementById('mode-switch-info');
                if (infoPanel) infoPanel.style.display = 'none';
            }
            alert(message);
            
            // Save historical replay preferences to localStorage
            if (mode === 'paper_mock' && data.historical_replay) {
                localStorage.setItem('historical_replay_config', JSON.stringify({
                    enabled: true,
                    start_date: data.historical_replay.start_date,
                    end_date: data.historical_replay.end_date,
                    interval: data.historical_replay.interval
                }));
            } else if (mode === 'paper_mock') {
                localStorage.setItem('historical_replay_config', JSON.stringify({ enabled: false }));
            }
            
            await updateModeStatus();
            await loadControlStatus();
            await loadData(); // Refresh dashboard data
        } else {
            if (data.error === 'CONFIRMATION_REQUIRED') {
                const confirmed = confirm(
                    '⚠️ WARNING: Switching to LIVE TRADING mode requires confirmation.\n\n' +
                    'This will execute REAL trades with REAL money.\n\n' +
                    'Are you absolutely sure you want to continue?'
                );
                if (confirmed) {
                    // Retry with confirmation
                    const retryPayload = { mode, confirm: true };
                    if (mode === 'paper_mock') {
                        const enableHistorical = document.getElementById('enable-historical-replay')?.checked;
                        if (enableHistorical) {
                            const startDate = document.getElementById('historical-start-date')?.value;
                            const endDate = document.getElementById('historical-end-date')?.value;
                            const interval = document.getElementById('historical-interval')?.value;
                            if (startDate) {
                                retryPayload.historical_start_date = startDate;
                                if (endDate) retryPayload.historical_end_date = endDate;
                                if (interval) retryPayload.historical_interval = interval;
                            }
                        }
                    }
                    const retryRes = await fetch('/api/control/mode/switch', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(retryPayload)
                    });
                    const retryData = await retryRes.json();
                    if (retryData.success) {
                        alert(`✅ Successfully switched to ${mode.toUpperCase().replace('_', ' ')} mode`);
                        await updateModeStatus();
                        await loadControlStatus();
                        await loadData();
                    } else {
                        alert(`❌ Failed: ${retryData.error}`);
                    }
                }
            } else {
                alert(`❌ Failed to switch mode:\n${data.error}`);
                
                // If auth required, show instructions
                if (data.action_required === 'authenticate') {
                    const authInstr = document.getElementById('auth-instructions');
                    if (authInstr) authInstr.style.display = 'block';
                }
                
                // Reload to reset radio button
                await loadControlStatus();
            }
        }
    } catch (e) {
        alert(`Error: ${e.message}`);
        console.error('Error applying trading mode:', e);
    }
}

async function connectZerodha() {
    try {
        const res = await fetch('/api/control/auth/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await res.json();
        
        if (data.success) {
            // Show instructions
            const instrEl = document.getElementById('auth-instructions');
            if (instrEl) instrEl.style.display = 'block';
            
            // Show login URL
            const loginUrlPanel = document.getElementById('login-url-panel');
            const loginUrlInput = document.getElementById('login-url-input');
            if (loginUrlPanel && loginUrlInput) {
                loginUrlInput.value = data.login_url;
                loginUrlPanel.style.display = 'block';
            }
            
            // Open login URL in new tab
            window.open(data.login_url, '_blank');
            
            // Show alert with clearer instructions
            alert(
                '📝 Zerodha Authentication Started\n\n' +
                '1. Login page opened in new tab\n' +
                '2. Login with your Zerodha credentials\n' +
                '3. After login, COPY the entire redirect URL\n' +
                '4. PASTE it in the field below and click "Complete Authentication"\n\n' +
                'The URL will look like:\n' +
                'https://127.0.0.1:5000?request_token=XXX&action=login&status=success'
            );
        } else {
            alert(`❌ Error: ${data.error}\n\n${data.instructions || ''}`);
        }
    } catch (e) {
        alert(`Error connecting to Zerodha: ${e.message}`);
        console.error('Error starting auth:', e);
    }
}

async function completeZerodhaAuth() {
    const urlInput = document.getElementById('request-token-url');
    const fullUrl = urlInput ? urlInput.value.trim() : '';
    
    if (!fullUrl) {
        alert('Please paste the redirect URL from your browser');
        return;
    }
    
    // Extract request_token from URL
    let requestToken = '';
    try {
        const url = new URL(fullUrl);
        requestToken = url.searchParams.get('request_token');
    } catch {
        // Try parsing as query string
        const match = fullUrl.match(/request_token=([^&]+)/);
        if (match) requestToken = match[1];
    }
    
    if (!requestToken) {
        alert('❌ Could not find request_token in URL.\n\nMake sure you copied the complete redirect URL.');
        return;
    }
    
    try {
        const res = await fetch('/api/control/auth/complete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ request_token: requestToken })
        });
        
        const data = await res.json();
        
        if (data.success) {
            alert(
                `✅ Authentication Successful!\n\n` +
                `Connected as: ${data.user_id || 'User'}\n` +
                `Access token valid until: ${data.token_expiry || 'N/A'}`
            );
            
            // Hide instructions and clear input
            const instrEl = document.getElementById('auth-instructions');
            if (instrEl) instrEl.style.display = 'none';
            if (urlInput) urlInput.value = '';
            
            // Reload control status
            await loadControlStatus();
        } else {
            alert(`❌ Authentication Failed:\n${data.error}`);
        }
    } catch (e) {
        alert(`Error completing authentication: ${e.message}`);
        console.error('Error completing auth:', e);
    }
}

function openLoginUrl() {
    const loginUrlInput = document.getElementById('login-url-input');
    if (loginUrlInput && loginUrlInput.value) {
        window.open(loginUrlInput.value, '_blank');
    }
}

async function disconnectZerodha() {
    const confirmed = confirm(
        'Are you sure you want to disconnect from Zerodha?\n\n' +
        'This will:\n' +
        '- Clear your access token\n' +
        '- Stop live data updates\n' +
        '- Switch to Paper (Mock) mode if currently in live mode'
    );
    
    if (!confirmed) return;
    
    try {
        const res = await fetch('/api/control/auth/disconnect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await res.json();
        
        if (data.success) {
            alert(`✅ ${data.message}`);
            await loadControlStatus();
            await loadData();
        } else {
            alert(`❌ Error: ${data.error}`);
        }
    } catch (e) {
        alert(`Error disconnecting: ${e.message}`);
        console.error('Error disconnecting:', e);
    }
}

async function resetPortfolio() {
    const modeSelect = document.getElementById('reset-mode-select');
    const mode = modeSelect ? modeSelect.value : 'paper_mock';
    
    const confirmed = confirm(
        `⚠️ WARNING: This will permanently delete ALL data for ${mode.toUpperCase().replace('_', ' ')} mode:\n\n` +
        '- All paper trades\n' +
        '- All positions\n' +
        '- P&L history\n' +
        '- Trading statistics\n\n' +
        'Account balance will reset to ₹1,00,000\n\n' +
        'This action CANNOT be undone. Continue?'
    );
    
    if (!confirmed) return;
    
    // Double confirmation for safety
    const doubleConfirm = confirm('Are you ABSOLUTELY sure? This cannot be undone!');
    if (!doubleConfirm) return;
    
    try {
        const res = await fetch('/api/control/portfolio/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode })
        });
        
        const data = await res.json();
        
        if (data.success) {
            alert(
                `✅ Portfolio Reset Successful!\n\n` +
                `Cleared:\n` +
                `- ${data.cleared.memory_trades} in-memory trades\n` +
                `- ${data.cleared.db_trades} database trades\n` +
                `- ${data.cleared.positions} positions\n\n` +
                `New balance: ${formatCurrency(data.new_balance)}`
            );
            await loadControlStatus();
            await loadData();
        } else {
            alert(`❌ Error: ${data.error}`);
        }
    } catch (e) {
        alert(`Error resetting portfolio: ${e.message}`);
        console.error('Error resetting portfolio:', e);
    }
}

// Load control status when Control Panel tab is shown
const originalShowTab = window.showTab;
window.showTab = function(tabId) {
    if (originalShowTab) originalShowTab(tabId);
    if (tabId === 'control') {
        loadControlStatus();
    }
};

async function setPaperBalance() {
    const input = document.getElementById('paper-balance-input');
    const amount = parseFloat(input.value);
    
    if (!amount || amount < 1000) {
        alert('Please enter a valid amount (minimum ₹1,000)');
        return;
    }
    
    try {
        const res = await fetch('/api/control/balance/set', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ balance: amount })
        });
        
        const data = await res.json();
        
        if (data.success) {
            alert(`✅ Paper trading balance set to ${formatCurrency(amount)}`);
            await loadControlStatus();
        } else {
            alert(`❌ Error: ${data.error}`);
        }
    } catch (e) {
        alert(`Error setting balance: ${e.message}`);
        console.error('Error setting paper balance:', e);
    }
}

