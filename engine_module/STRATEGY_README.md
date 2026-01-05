# Options Strategy Engine (Preview)

This module provides a configurable scaffold for Options Buy/Sell strategies that can later translate into trades.

## Data Inputs
- Options chain: strike, CE/PE LTP, CE/PE OI, expiry (via `/api/options-chain`).
- Order flow: depth ladder, total depth bid/ask, imbalance (via `/api/order-flow`).
- Latest signal: BUY/SELL/HOLD consensus (via `agent_decisions` collection).

## Rule Parameters
Defined in `options_strategy_engine.RuleConfig`:
- **min_oi**: minimum open interest per leg (filter strikes).
- **prefer_expiry**: desired expiry (YYYY-MM-DD).
- **lot_size**: quantity per recommendation (BANKNIFTY lot default 25).
- **premium_sl_pct** / **premium_tp_pct**: base stop-loss / take-profit on premium (default 40%).
- **orderflow_tilt_threshold**: imbalance threshold to tilt strike selection.
- **selection**: selection policy placeholder (ATM_NEAREST etc.).
- **target_delta**: select strike closest to target delta (e.g., 0.35). When absent, falls back to ATM.
- **max_iv**: cap IV% for the leg (skip strikes above this IV).
- **iv_adjust_sl** / **iv_adjust_tp**: widen SL/TP by `iv% * factor` for higher IV environments.

## Output
`evaluate()` returns a `recommendation` block suitable for UI and later order placement:

```
{
  instrument, expiry,
  side: "BUY",
  option_type: "CE" | "PE",
  strike, premium,
  stop_loss_price, take_profit_price,
  quantity,
  reasoning
}
```

## API
The dashboard exposes:
- `/api/options-strategy-advanced?min_oi=75000&prefer_expiry=YYYY-MM-DD&target_delta=0.35&max_iv=30`

## Next Steps (for trading)
- Integrate with `automatic_trading_service` to create an options execution path.
- Add IV percentile/skew and broker chain feed; prefer deltas by regime and avoid IV%ile > 80.
- Add expiry filtering across multiple expiries.
- Position sizing via `risk_metrics` and cash/portfolio constraints.
- Add backtesting gates before auto-placement.
