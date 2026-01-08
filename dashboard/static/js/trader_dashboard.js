// Trader Dashboard JavaScript
let refreshInterval = null;
let lastUpdateTime = null;

// Format currency
function formatCurrency(value) {
    if (value === null || value === undefined || isNaN(value)) return '--';
    return '₹' + parseFloat(value).toLocaleString('en-IN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

// Format percentage
function formatPercent(value) {
    if (value === null || value === undefined || isNaN(value)) return '--';
    const num = parseFloat(value);
    const displayVal = (num > 0 && num <= 1) ? num * 100 : num;
    return displayVal.toFixed(2) + '%';
}

// Format relative time
function formatRelativeTime(timestamp) {
    if (!timestamp) return 'Never';
    const now = Date.now();
    const then = new Date(timestamp).getTime();
    const diffSec = Math.floor((now - then) / 1000);
    
    if (diffSec < 10) return 'Just now';
    if (diffSec < 60) return diffSec + 's ago';
    if (diffSec < 3600) return Math.floor(diffSec / 60) + 'm ago';
    return Math.floor(diffSec / 3600) + 'h ago';
}

// Format time
function formatTime(timestamp) {
    if (!timestamp) return '--:--:--';
    try {
        return new Date(timestamp).toLocaleTimeString('en-IN', {
            timeZone: 'Asia/Kolkata',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    } catch (e) {
        return '--:--:--';
    }
}

// Update system time display
function updateSystemTime() {
    fetch('/api/system-time')
        .then(res => res.json())
        .then(data => {
            const timeEl = document.getElementById('system-time');
            if (timeEl && data.time) {
                timeEl.textContent = data.time + ' IST';
                timeEl.style.color = data.is_virtual ? '#f59e0b' : '#3b82f6';
            }
        })
        .catch(err => console.error('Error updating system time:', err));
}

// Update market data time
function updateMarketDataTime(timestamp) {
    const el = document.getElementById('market-data-time');
    if (el && timestamp) {
        el.textContent = formatTime(timestamp);
        el.title = 'Market data captured at: ' + new Date(timestamp).toLocaleString();
    }
}

// Update agent last run time
function updateAgentLastRun(timestamp) {
    const el = document.getElementById('agent-last-run');
    if (el && timestamp) {
        el.textContent = formatRelativeTime(timestamp);
        el.title = 'Last agent analysis: ' + new Date(timestamp).toLocaleString();
    }
}

// Update signal display
function updateSignal(signal) {
    const icons = { 'BUY': '🚀', 'SELL': '📉', 'HOLD': '📊' };
    const action = signal.signal || 'HOLD';
    
    const cardEl = document.getElementById('current-signal');
    const iconEl = document.getElementById('signal-icon');
    const actionEl = document.getElementById('signal-action');
    const reasonEl = document.getElementById('signal-reason');
    const confEl = document.getElementById('signal-conf-value');
    const entryEl = document.getElementById('signal-entry');
    const slEl = document.getElementById('signal-sl');
    const tpEl = document.getElementById('signal-tp');
    
    if (cardEl) {
        cardEl.className = 'card signal-card ' + action.toLowerCase();
    }
    if (iconEl) iconEl.textContent = icons[action] || '📊';
    if (actionEl) actionEl.textContent = action;
    if (reasonEl) reasonEl.textContent = signal.reasoning || 'Analyzing market conditions...';
    if (confEl) confEl.textContent = signal.confidence ? formatPercent(signal.confidence) : '--';
    if (entryEl) entryEl.textContent = signal.entry_price ? formatCurrency(signal.entry_price) : '--';
    if (slEl) slEl.textContent = signal.stop_loss ? formatCurrency(signal.stop_loss) : '--';
    if (tpEl) tpEl.textContent = signal.take_profit ? formatCurrency(signal.take_profit) : '--';
}

// Update market data
function updateMarketData(market) {
    if (!market || market.error) {
        document.getElementById('current-price').textContent = '--';
        document.getElementById('price-change').textContent = '--';
        return;
    }
    
    const price = market.currentprice || market.current_price || market.ltp || 0;
    const change = market.change || 0;
    const changePct = market.change_pct || market.changepct || 0;
    
    const priceEl = document.getElementById('current-price');
    const changeEl = document.getElementById('price-change');
    const highEl = document.getElementById('day-high');
    const lowEl = document.getElementById('day-low');
    const volEl = document.getElementById('volume');
    const vwapEl = document.getElementById('vwap');
    
    if (priceEl) priceEl.textContent = formatCurrency(price);
    
    if (changeEl) {
        const sign = changePct >= 0 ? '+' : '';
        changeEl.textContent = sign + changePct.toFixed(2) + '%';
        changeEl.className = 'price-change ' + (changePct >= 0 ? 'positive' : 'negative');
    }
    
    if (highEl) highEl.textContent = formatCurrency(market.high || price * 1.02);
    if (lowEl) lowEl.textContent = formatCurrency(market.low || price * 0.98);
    if (volEl) volEl.textContent = market.volume ? Math.floor(market.volume).toLocaleString() : '--';
    if (vwapEl) vwapEl.textContent = market.vwap ? formatCurrency(market.vwap) : '--';
    
    if (market.timestamp) {
        updateMarketDataTime(market.timestamp);
    }
}

// Update technical indicators
function updateTechnicals(data) {
    if (!data || !data.indicators) return;
    
    data.indicators.forEach(ind => {
        const name = ind.name.toLowerCase();
        let valueId = null;
        let signalId = null;
        
        if (name.includes('rsi')) {
            valueId = 'rsi-value';
            signalId = 'rsi-signal';
        } else if (name.includes('macd')) {
            valueId = 'macd-value';
            signalId = 'macd-signal';
        } else if (name.includes('sma')) {
            valueId = 'sma-value';
            signalId = 'sma-signal';
        } else if (name.includes('adx')) {
            valueId = 'adx-value';
            signalId = 'adx-signal';
        }
        
        if (valueId && signalId) {
            const valEl = document.getElementById(valueId);
            const sigEl = document.getElementById(signalId);
            
            if (valEl) valEl.textContent = typeof ind.value === 'number' ? ind.value.toFixed(1) : ind.value;
            if (sigEl) {
                sigEl.textContent = ind.signal.toUpperCase();
                sigEl.className = 'ind-signal ' + ind.signal.toLowerCase();
            }
        }
    });
}

// Update positions
function updatePositions(portfolio) {
    const container = document.getElementById('positions-container');
    const countEl = document.getElementById('positions-count');
    
    if (!portfolio || !portfolio.positions || portfolio.positions.length === 0) {
        container.innerHTML = '<div class="empty-state">No active positions</div>';
        if (countEl) countEl.textContent = '0';
        return;
    }
    
    if (countEl) countEl.textContent = portfolio.positions.length;
    
    const html = portfolio.positions.map(pos => {
        const pnl = pos.unrealized_pnl || pos.pnl || 0;
        const pnlClass = pnl >= 0 ? 'profit' : 'loss';
        
        return `
            <div class="position-item">
                <div class="position-header">
                    <span class="position-symbol">${pos.instrument}</span>
                    <span class="position-pnl ${pnlClass}">${formatCurrency(pnl)}</span>
                </div>
                <div class="position-details">
                    <div>Qty: ${pos.quantity}</div>
                    <div>Entry: ${formatCurrency(pos.entry_price)}</div>
                    <div>Current: ${formatCurrency(pos.current_price)}</div>
                    <div>Type: ${pos.option_type || 'FUT'}</div>
                </div>
            </div>
        `;
    }).join('');
    
    container.innerHTML = html;
}

// Update performance metrics
function updatePerformance(metrics) {
    if (!metrics) return;
    
    const pnl = metrics.total_pnl || metrics.totalpnl || 0;
    const winRate = metrics.win_rate || metrics.winrate || 0;
    const trades = metrics.total_trades || metrics.totaltrades || 0;
    const sharpe = metrics.sharpe_ratio || metrics.sharperatio || 0;
    
    const pnlEl = document.getElementById('total-pnl');
    const winRateEl = document.getElementById('win-rate');
    const tradesEl = document.getElementById('total-trades');
    const sharpeEl = document.getElementById('sharpe-ratio');
    
    if (pnlEl) {
        pnlEl.textContent = formatCurrency(pnl);
        pnlEl.className = 'perf-value ' + (pnl >= 0 ? 'positive' : 'negative');
    }
    if (winRateEl) winRateEl.textContent = formatPercent(winRate);
    if (tradesEl) tradesEl.textContent = trades;
    if (sharpeEl) sharpeEl.textContent = sharpe ? sharpe.toFixed(2) : '--';
}

// Update trades table
function updateTrades(trades) {
    const tbody = document.getElementById('trades-tbody');
    
    if (!trades || trades.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No trades yet</td></tr>';
        return;
    }
    
    const html = trades.slice(0, 10).map(trade => {
        const pnl = trade.pnl || 0;
        const pnlStyle = pnl >= 0 ? 'color: var(--color-success)' : 'color: var(--color-danger)';
        
        return `
            <tr>
                <td>${formatTime(trade.timestamp)}</td>
                <td>${trade.side || 'N/A'}</td>
                <td>${trade.strike || '--'}</td>
                <td>${formatCurrency(trade.price || trade.entry_price)}</td>
                <td>${trade.exit_price ? formatCurrency(trade.exit_price) : '--'}</td>
                <td style="${pnlStyle}">${formatCurrency(pnl)}</td>
            </tr>
        `;
    }).join('');
    
    tbody.innerHTML = html;
}

// Update pending signals
function updatePendingSignals(signals) {
    const container = document.getElementById('pending-signals-container');
    const countEl = document.getElementById('pending-count');
    
    const pending = signals.filter(s => s.status === 'pending');
    
    if (pending.length === 0) {
        container.innerHTML = '<div class="empty-state">No pending signals</div>';
        if (countEl) countEl.textContent = '0';
        return;
    }
    
    if (countEl) countEl.textContent = pending.length;
    
    const html = pending.map(sig => {
        const conf = (sig.confidence * 100).toFixed(0);
        
        return `
            <div class="pending-signal-item">
                <div class="pending-header">
                    <span class="pending-symbol">${sig.symbol}</span>
                    <span class="pending-conf">${conf}%</span>
                </div>
                <div class="pending-details">
                    ${sig.action} | Entry: ${formatCurrency(sig.entry_price)} | SL: ${formatCurrency(sig.stop_loss)}
                </div>
                <div class="pending-actions">
                    <button class="pending-btn execute" onclick="executeSignal('${sig.id}')">Execute</button>
                    <button class="pending-btn reject" onclick="rejectSignal('${sig.id}')">Reject</button>
                </div>
            </div>
        `;
    }).join('');
    
    container.innerHTML = html;
}

// Update agents
function updateAgents(agents) {
    if (!agents || !agents.agents) return;
    
    // Update consensus
    const consensusEl = document.getElementById('consensus-signal');
    const agreementEl = document.getElementById('consensus-agreement');
    
    const agentList = Object.values(agents.agents);
    const signals = agentList.map(a => a.summary?.signal).filter(Boolean);
    const buyCount = signals.filter(s => s === 'BUY').length;
    const sellCount = signals.filter(s => s === 'SELL').length;
    const holdCount = signals.filter(s => s === 'HOLD').length;
    
    let consensus = 'HOLD';
    if (buyCount > sellCount && buyCount > holdCount) consensus = 'BUY';
    else if (sellCount > buyCount && sellCount > holdCount) consensus = 'SELL';
    
    if (consensusEl) consensusEl.textContent = consensus;
    if (agreementEl) agreementEl.textContent = `${Math.max(buyCount, sellCount, holdCount)}/${agentList.length} agents agree`;
    
    // Update individual agents
    const agentMappings = {
        'momentum': { statusId: 'momentum-status', signalId: 'momentum-signal', reasonId: 'momentum-reasoning' },
        'trend': { statusId: 'trend-status', signalId: 'trend-signal', reasonId: 'trend-reasoning' },
        'mean_reversion': { statusId: 'reversion-status', signalId: 'reversion-signal', reasonId: 'reversion-reasoning' },
        'volume': { statusId: 'volume-agent-status', signalId: 'volume-agent-signal', reasonId: 'volume-agent-reasoning' }
    };
    
    Object.entries(agentMappings).forEach(([key, ids]) => {
        const agent = agents.agents[key];
        const statusEl = document.getElementById(ids.statusId);
        const signalEl = document.getElementById(ids.signalId);
        const reasonEl = document.getElementById(ids.reasonId);
        
        if (agent) {
            const status = agent.status === 'active' ? '🟢 ACTIVE' : agent.status === 'stale' ? '🟡 STALE' : '⚪ WAITING';
            const signal = agent.summary?.signal || 'HOLD';
            const reasoning = agent.summary?.reasoning || 'Analyzing...';
            
            if (statusEl) statusEl.textContent = status;
            if (signalEl) {
                signalEl.textContent = signal;
                signalEl.className = 'agent-signal ' + signal.toLowerCase();
            }
            if (reasonEl) reasonEl.textContent = reasoning.substring(0, 100) + (reasoning.length > 100 ? '...' : '');
        }
    });
    
    // Update agent last run time
    if (agents.last_analysis) {
        updateAgentLastRun(agents.last_analysis);
    }
}

// Update risk metrics
function updateRisk(risk) {
    if (!risk) return;
    
    const exposureEl = document.getElementById('risk-exposure');
    const drawdownEl = document.getElementById('risk-drawdown');
    const ratioEl = document.getElementById('risk-ratio');
    const portfolioEl = document.getElementById('risk-portfolio');
    
    if (exposureEl) exposureEl.textContent = risk.totalexposure || risk.total_exposure ? formatCurrency(risk.totalexposure || risk.total_exposure) : '--';
    if (drawdownEl) drawdownEl.textContent = risk.maxdrawdown || risk.max_drawdown ? formatCurrency(risk.maxdrawdown || risk.max_drawdown) : '--';
    if (ratioEl) ratioEl.textContent = risk.win_loss_ratio || risk.winlossratio ? (risk.win_loss_ratio || risk.winlossratio).toFixed(2) : '--';
    if (portfolioEl) portfolioEl.textContent = risk.portfoliovalue || risk.portfolio_value ? formatCurrency(risk.portfoliovalue || risk.portfolio_value) : '--';
}

// Update system health
function updateHealth(health) {
    if (!health || !health.components) return;
    
    const dbEl = document.getElementById('health-db');
    const feedEl = document.getElementById('health-feed');
    const llmEl = document.getElementById('health-llm');
    const agentsEl = document.getElementById('health-agents');
    
    const setHealth = (el, status) => {
        if (!el) return;
        const isOk = status === 'operational' || status === 'healthy' || status === 'ok';
        el.textContent = isOk ? '🟢 OK' : '🔴 ERROR';
        el.className = 'health-status ' + (isOk ? 'ok' : 'error');
    };
    
    setHealth(dbEl, health.components.mongodb);
    setHealth(feedEl, health.components.data_feed || health.components.mongodb);
    setHealth(llmEl, health.components.llm || health.components.genai);
    setHealth(agentsEl, health.components.agents || 'ok');
}

// Update connection and market status badges
function updateStatusBadges(health, market) {
    const marketBadge = document.getElementById('market-badge');
    const connectionBadge = document.getElementById('connection-badge');
    
    if (marketBadge && health) {
        const isOpen = health.market_open || false;
        marketBadge.textContent = isOpen ? '🟢 OPEN' : '🔴 CLOSED';
        marketBadge.className = 'badge badge-market ' + (isOpen ? 'open' : '');
    }
    
    if (connectionBadge) {
        const hasData = market && !market.error && market.currentprice;
        connectionBadge.textContent = hasData ? '🟢 CONNECTED' : '🔴 DISCONNECTED';
        connectionBadge.className = 'badge badge-connection ' + (hasData ? 'connected' : '');
    }
}

// Main refresh function
async function refreshAll() {
    try {
        // Fetch all data in parallel
        const [signal, market, technicals, portfolio, metrics, risk, trades, agents, health] = await Promise.all([
            fetch('/api/latest-signal').then(r => r.json()).catch(() => ({})),
            fetch('/api/market-data').then(r => r.json()).catch(() => ({})),
            fetch('/api/technical-indicators').then(r => r.json()).catch(() => ({})),
            fetch('/api/portfolio').then(r => r.json()).catch(() => ({})),
            fetch('/metrics/trading').then(r => r.json()).catch(() => ({})),
            fetch('/metrics/risk').then(r => r.json()).catch(() => ({})),
            fetch('/api/recent-trades?limit=10').then(r => r.json()).catch(() => []),
            fetch('/api/agent-status').then(r => r.json()).catch(() => ({})),
            fetch('/api/system-health').then(r => r.json()).catch(() => ({}))
        ]);
        
        // Update all displays
        updateSignal(signal);
        updateMarketData(market);
        updateTechnicals(technicals);
        updatePositions(portfolio);
        updatePerformance(metrics);
        updateTrades(trades);
        
        // Fetch pending signals separately
        fetch('/api/trading/signals')
            .then(r => r.json())
            .then(data => updatePendingSignals(data.signals || []))
            .catch(err => console.error('Error loading signals:', err));
        
        updateAgents(agents);
        updateRisk(risk);
        updateHealth(health);
        updateStatusBadges(health, market);
        updateSystemTime();
        
        lastUpdateTime = new Date();
        
    } catch (error) {
        console.error('Error refreshing dashboard:', error);
    }
}

// Signal execution functions
async function executeSignal(signalId) {
    if (!confirm('Execute this signal immediately?')) return;
    
    try {
        const response = await fetch('/api/trading/execute-signal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ signal_id: signalId, execute_immediately: true })
        });
        
        const result = await response.json();
        if (result.success) {
            alert('Signal executed successfully!');
            refreshAll();
        } else {
            alert('Failed to execute signal: ' + (result.message || 'Unknown error'));
        }
    } catch (error) {
        alert('Error executing signal: ' + error.message);
    }
}

async function rejectSignal(signalId) {
    if (!confirm('Reject this signal?')) return;
    
    try {
        const response = await fetch('/api/trading/reject-signal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ signal_id: signalId })
        });
        
        const result = await response.json();
        if (result.success) {
            alert('Signal rejected');
            refreshAll();
        } else {
            alert('Failed to reject signal: ' + (result.message || 'Unknown error'));
        }
    } catch (error) {
        alert('Error rejecting signal: ' + error.message);
    }
}

// Quick action functions
function runTradingCycle() {
    window.location.href = '/full-dashboard#trading';
}

function openOptionsChain() {
    window.location.href = '/full-dashboard#options';
}

function viewFullDashboard() {
    window.location.href = '/full-dashboard';
}

function openControlPanel() {
    window.location.href = '/full-dashboard#control';
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    // Initial load
    refreshAll();
    
    // Auto-refresh every 10 seconds
    refreshInterval = setInterval(refreshAll, 10000);
    
    // Update system time every second
    setInterval(updateSystemTime, 1000);
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
});
