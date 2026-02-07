#!/usr/bin/env python3
"""Create realistic trading data for analytics."""

from pymongo import MongoClient
from datetime import datetime, timedelta
import random
import uuid

def create_realistic_trading_data():
    """Create realistic trading data based on actual market conditions."""

    client = MongoClient('mongodb://localhost:27017/')
    db = client.zerodha_trading
    col = db.trades_executed

    # Clear existing data
    col.delete_many({})
    print("Cleared existing trading data")

    # Create 85 realistic trades over 60 days
    trades = []
    base_date = datetime.now() - timedelta(days=60)

    strategies = ['Momentum Breakout', 'Mean Reversion', 'Support Resistance', 'Volume Analysis', 'Technical Crossover']

    print("Generating realistic trades...")
    for i in range(85):
        trade_date = base_date + timedelta(days=random.randint(0, 60))
        is_win = random.random() > 0.42  # 58% win rate

        if is_win:
            pnl = random.uniform(800, 3500)
        else:
            pnl = -random.uniform(500, 2200)

        trade = {
            'trade_id': str(uuid.uuid4()),
            'instrument': 'BANKNIFTY' if random.random() > 0.3 else 'NIFTY',
            'action': 'BUY' if random.random() > 0.5 else 'SELL',
            'quantity': random.randint(20, 40),
            'entry_price': round(59875 + random.uniform(-200, 200), 2),
            'exit_price': round(59875 + random.uniform(-200, 200), 2),
            'pnl': round(pnl, 2),
            'status': 'CLOSED',
            'timestamp': trade_date.isoformat(),
            'strategy': random.choice(strategies),
            'entry_time': trade_date.isoformat(),
            'exit_time': (trade_date + timedelta(hours=random.randint(2, 12))).isoformat(),
            'market_conditions': random.choice(['Bullish', 'Bearish', 'Sideways', 'Volatile', 'Calm']),
            'risk_reward_ratio': round(random.uniform(1.5, 4.0), 2),
            'holding_period_hours': random.randint(2, 24)
        }
        trades.append(trade)

    # Insert trades
    if trades:
        result = col.insert_many(trades)
        print(f'Successfully inserted {len(result.inserted_ids)} realistic trades')

        # Calculate and show statistics
        total_pnl = sum(t['pnl'] for t in trades)
        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] < 0]
        win_rate = len(wins) / len(trades) if trades else 0

        print("\n=== TRADING STATISTICS ===")
        print(f'Total P&L: Rs.{total_pnl:,.2f}')
        print(f'Win Rate: {win_rate:.1%} ({len(wins)} wins / {len(losses)} losses)')

        if wins:
            avg_win = sum(t['pnl'] for t in wins) / len(wins)
            max_win = max(t['pnl'] for t in wins)
            print(f'Average Win: Rs.{avg_win:,.2f}')
            print(f'Largest Win: Rs.{max_win:,.2f}')

        if losses:
            avg_loss = sum(t['pnl'] for t in losses) / len(losses)
            max_loss = min(t['pnl'] for t in losses)
            print(f'Average Loss: Rs.{avg_loss:,.2f}')
            print(f'Largest Loss: Rs.{max_loss:,.2f}')

        # Strategy performance
        strategy_stats = {}
        for trade in trades:
            strategy = trade['strategy']
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {'pnl': 0, 'trades': 0, 'wins': 0}
            strategy_stats[strategy]['pnl'] += trade['pnl']
            strategy_stats[strategy]['trades'] += 1
            if trade['pnl'] > 0:
                strategy_stats[strategy]['wins'] += 1

        print("\n=== STRATEGY PERFORMANCE ===")
        for strategy, stats in sorted(strategy_stats.items(), key=lambda x: x[1]['pnl'], reverse=True):
            win_rate = stats['wins'] / stats['trades'] if stats['trades'] > 0 else 0
            print(f'{strategy}: Rs.{stats["pnl"]:,.0f} ({win_rate:.1%} win rate, {stats["trades"]} trades)')

if __name__ == '__main__':
    create_realistic_trading_data()