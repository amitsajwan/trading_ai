from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime

@dataclass
class RuleConfig:
    instrument: str = "BANKNIFTY"
    min_oi: int = 75000            # minimum OI per leg
    prefer_expiry: Optional[str] = None  # e.g. "2026-01-30"
    lot_size: int = 25
    premium_sl_pct: float = 0.40   # base SL percent on premium
    premium_tp_pct: float = 0.40   # base TP percent on premium
    orderflow_tilt_threshold: float = 0.10  # +/- imbalance threshold
    selection: str = "ATM_NEAREST"  # ATM_NEAREST | OTM_1 | ITM_1
    # IV/Greeks refinements
    target_delta: Optional[float] = 0.35
    max_iv: Optional[float] = None       # cap IV% for selected leg (e.g., 30)
    iv_adjust_sl: float = 0.5            # widen SL by iv% * factor
    iv_adjust_tp: float = 0.5            # widen TP by iv% * factor

@dataclass
class TradeIntent:
    instrument: str
    expiry: Optional[str]
    side: str              # BUY
    option_type: str       # CE or PE
    strike: int
    quantity: int
    entry_premium: float
    stop_loss_price: float
    take_profit_price: float
    reasoning: str


def nearest_by_fut(strikes: List[Dict[str, Any]], fut_price: float) -> Dict[str, Any]:
    def key(row: Dict[str, Any]) -> float:
        try:
            return abs((row.get("strike") or 0) - fut_price)
        except Exception:
            return float("inf")
    return sorted(strikes, key=key)[0]


def apply_orderflow_tilt(best_row: Dict[str, Any], strikes_sorted: List[Dict[str, Any]],
                         option_type: str, imbalance_val: Optional[float], threshold: float) -> Dict[str, Any]:
    if imbalance_val is None:
        return best_row
    try:
        if option_type == "CE" and float(imbalance_val) > threshold:
            # bullish – prefer slightly OTM CE (next higher strike)
            for row in strikes_sorted:
                if row.get("strike", 0) >= best_row.get("strike", 0) and row.get("ce_ltp"):
                    return row
        if option_type == "PE" and float(imbalance_val) < -threshold:
            # bearish – prefer slightly OTM PE (next lower strike)
            for row in strikes_sorted:
                if row.get("strike", 0) <= best_row.get("strike", 0) and row.get("pe_ltp"):
                    return row
    except Exception:
        return best_row
    return best_row


def select_leg(signal: str, chain: Dict[str, Any], orderflow: Dict[str, Any], cfg: RuleConfig) -> Optional[TradeIntent]:
    if not chain or chain.get("available") is False:
        return None

    fut_price = chain.get("futures_price")
    strikes = chain.get("chain", [])
    expiry = chain.get("expiry")
    if not fut_price or not strikes:
        return None

    # expiry filter (if set)
    if cfg.prefer_expiry and expiry and cfg.prefer_expiry != expiry:
        # In a real system, we'd query another expiry; here we continue but mark reasoning
        pass

    # OI threshold filter + IV cap
    filtered: List[Dict[str, Any]] = []
    for row in strikes:
        ce_ok = (row.get("ce_oi") or 0) >= cfg.min_oi
        pe_ok = (row.get("pe_oi") or 0) >= cfg.min_oi
        iv_val = row.get("ce_iv") if signal == "BUY" else row.get("pe_iv")
        iv_pass = True if cfg.max_iv is None else (iv_val is not None and float(iv_val) <= float(cfg.max_iv))
        if signal == "BUY" and ce_ok and iv_pass:
            filtered.append(row)
        elif signal == "SELL" and pe_ok and iv_pass:
            filtered.append(row)
    if not filtered:
        # fallback to full list
        filtered = strikes

    # base selection by delta if available, else nearest by futures
    option_type = "CE" if signal == "BUY" else "PE"
    if cfg.target_delta is not None:
        def delta_diff(row: Dict[str, Any]) -> float:
            val = row.get("ce_delta") if option_type == "CE" else row.get("pe_delta")
            if val is None:
                return float("inf")
            # PE deltas often negative; compare absolute distance to target
            try:
                return abs(abs(float(val)) - abs(float(cfg.target_delta)))
            except Exception:
                return float("inf")
        best_row = sorted(filtered, key=delta_diff)[0] if filtered else None
    else:
        best_row = nearest_by_fut(filtered, float(fut_price))

    # orderflow tilt
    imbalance = orderflow.get("imbalance") if isinstance(orderflow, dict) else None
    imb_val = (imbalance or {}).get("imbalance_pct") if isinstance(imbalance, dict) else imbalance

    strikes_sorted = sorted(filtered, key=lambda r: r.get("strike") or 0)
    best_row = apply_orderflow_tilt(best_row, strikes_sorted, option_type, imb_val, cfg.orderflow_tilt_threshold)

    # premium and SL/TP
    premium = float(best_row.get("ce_ltp") if option_type == "CE" else best_row.get("pe_ltp") or 0.0)
    if not premium:
        return None
    iv_used = best_row.get("ce_iv") if option_type == "CE" else best_row.get("pe_iv")
    try:
        iv_pct = float(iv_used) / 100.0 if iv_used is not None else 0.0
    except Exception:
        iv_pct = 0.0
    sl_pct_eff = cfg.premium_sl_pct + (iv_pct * cfg.iv_adjust_sl)
    tp_pct_eff = cfg.premium_tp_pct + (iv_pct * cfg.iv_adjust_tp)
    sl_price = round(premium * (1.0 - sl_pct_eff), 2)
    tp_price = round(premium * (1.0 + tp_pct_eff), 2)

    reason_parts: List[str] = [
        f"Signal {signal}",
        "ATM/near-ATM selection",
        f"OI >= {cfg.min_oi}",
    ]
    if imb_val is not None:
        reason_parts.append("Order-flow tilt applied")
    if iv_used is not None:
        reason_parts.append(f"IV {iv_used:.1f}% → SL/TP widened")
    delta_used = best_row.get("ce_delta") if option_type == "CE" else best_row.get("pe_delta")
    if delta_used is not None and cfg.target_delta is not None:
        try:
            reason_parts.append(f"Delta≈{float(delta_used):.2f} vs target {float(cfg.target_delta):.2f}")
        except Exception:
            pass
    if cfg.prefer_expiry:
        reason_parts.append(f"Prefer expiry {cfg.prefer_expiry}")

    return TradeIntent(
        instrument=cfg.instrument,
        expiry=expiry,
        side="BUY",
        option_type=option_type,
        strike=int(best_row.get("strike") or 0),
        quantity=cfg.lot_size,
        entry_premium=premium,
        stop_loss_price=sl_price,
        take_profit_price=tp_price,
        reasoning="; ".join(reason_parts),
    )


def evaluate(signal: str, chain: Dict[str, Any], orderflow: Dict[str, Any], cfg: Optional[RuleConfig] = None) -> Dict[str, Any]:
    cfg = cfg or RuleConfig()
    intent = select_leg(signal, chain, orderflow, cfg)
    result: Dict[str, Any] = {
        "available": intent is not None,
        "timestamp": datetime.now().isoformat(),
        "instrument": cfg.instrument,
        "expiry": chain.get("expiry") if chain else None,
        "config": cfg.__dict__,
    }
    if intent:
        result["recommendation"] = {
            "side": intent.side,
            "option_type": intent.option_type,
            "strike": intent.strike,
            "premium": intent.entry_premium,
            "stop_loss_price": intent.stop_loss_price,
            "take_profit_price": intent.take_profit_price,
            "quantity": intent.quantity,
            "reasoning": intent.reasoning,
        }

        # Derive proper two-leg spread (debit) for professionals
        # BUY signal -> Bull Call Spread (Buy CE lower, Sell CE higher)
        # SELL signal -> Bear Put Spread (Buy PE higher, Sell PE lower)
        try:
            strikes = chain.get("chain", []) if chain else []
            if strikes:
                # Sort by strike
                strikes_sorted = sorted(strikes, key=lambda r: r.get("strike") or 0)
                base_idx = next((i for i, r in enumerate(strikes_sorted) if int(r.get("strike") or 0) == intent.strike), None)
                option_type = intent.option_type
                lot = intent.quantity
                legs: List[Dict[str, Any]] = []
                strategy_type = None

                def leg_premium(row: Dict[str, Any], opt: str) -> Optional[float]:
                    val = row.get("ce_ltp") if opt == "CE" else row.get("pe_ltp")
                    return float(val) if val is not None else None

                def oi_ok(row: Dict[str, Any], opt: str) -> bool:
                    return (row.get("ce_oi") or 0) >= cfg.min_oi if opt == "CE" else (row.get("pe_oi") or 0) >= cfg.min_oi

                if base_idx is not None:
                    base_row = strikes_sorted[base_idx]
                    buy_prem = leg_premium(base_row, option_type)
                    if buy_prem:
                        # Choose hedge leg index: next higher for CE, next lower for PE
                        hedge_idx = base_idx + 1 if option_type == "CE" else base_idx - 1
                        if 0 <= hedge_idx < len(strikes_sorted):
                            hedge_row = strikes_sorted[hedge_idx]
                            sell_prem = leg_premium(hedge_row, option_type)
                            if sell_prem and oi_ok(hedge_row, option_type):
                                strategy_type = "Bull Call Spread" if option_type == "CE" else "Bear Put Spread"
                                legs = [
                                    {
                                        "side": "BUY",
                                        "option_type": option_type,
                                        "strike": int(base_row.get("strike") or intent.strike),
                                        "premium": float(buy_prem),
                                        "quantity": lot,
                                    },
                                    {
                                        "side": "SELL",
                                        "option_type": option_type,
                                        "strike": int(hedge_row.get("strike") or intent.strike),
                                        "premium": float(sell_prem),
                                        "quantity": lot,
                                    },
                                ]
                                net_debit = round(float(buy_prem) - float(sell_prem), 2)
                                result["strategy_type"] = strategy_type
                                result["legs"] = legs
                                result["net_debit"] = net_debit
                                # For simple display, keep single-leg recommendation; spreads available in fields above
        except Exception:
            # If anything fails, we still return single-leg recommendation
            pass
    else:
        result["reason"] = "No valid leg matched constraints"
    return result

