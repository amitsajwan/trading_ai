"""P&L calculator moved under engine module."""

# Copied from top-level pl_calculator.py
import json
import os
from pathlib import Path

try:
    from kiteconnect import KiteConnect
except Exception:
    KiteConnect = None  # optional; kiteconnect may not be installed in free environment


def load_credentials():
    p = Path("credentials.json")
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def attempt_fetch_ltp(kite, instrument_token):
    """Attempt to fetch LTP for the given instrument identifier.
    instrument_token should be the instrument identifier expected by Kite's ltp() (eg. 'NSE:INFY' or token string).
    Returns float LTP or None.
    """
    if not kite:
        return None
    try:
        res = kite.ltp(instrument_token)
        # response shape: {"NSE:INFY": {"last_price": 1234.5}} or token-keyed
        for v in res.values():
            if isinstance(v, dict) and "last_price" in v:
                return float(v["last_price"])
    except Exception:
        return None


def input_leg(i):
    print(f"\nLeg #{i+1}")
    side = input("Side (buy/sell): ").strip().lower()
    while side not in ("buy", "sell"):
        side = input("Please enter 'buy' or 'sell': ").strip().lower()

    while True:
        try:
            entry = float(input("Entry price: ").strip())
            break
        except ValueError:
            print("Invalid input. Please enter a numeric value for the entry price.")

    while True:
        try:
            qty = int(input("Quantity (per lot): ").strip())
            break
        except ValueError:
            print("Invalid input. Please enter an integer value for the quantity.")

    instrument = input("(optional) Instrument token/symbol for LTP fetch (eg: NSE:RELIANCE) or leave blank: ").strip()
    return {"side": side, "entry": entry, "qty": qty, "instrument": instrument}


def main():
    creds = load_credentials()
    kite = None
    if creds and KiteConnect is not None:
        try:
            kite = KiteConnect(api_key=creds.get("api_key"))
            kite.set_access_token(creds.get("access_token"))
            print("Kite client ready (will try to fetch LTP where instrument token set).")
        except Exception:
            kite = None

    n = int(input("How many legs? ").strip())
    legs = [input_leg(i) for i in range(n)]

    # Gather LTPs
    for leg in legs:
        ltp = None
        if leg.get("instrument"):
            ltp = attempt_fetch_ltp(kite, leg["instrument"]) if kite else None
        if ltp is None:
            ltp = float(input(f"Enter current LTP for leg (entry {leg['entry']}): ").strip())
        leg["ltp"] = ltp

def compute_pnl(legs):
    """Compute entry credit, current cost and P&L given a list of legs.

    Each leg is a dict with keys: side ('buy'|'sell'), entry (float), ltp (float), qty (int).
    Returns a dict: {"entry_credit": float, "current_cost": float, "pnl": float}
    """
    entry_credit = 0.0
    current_cost = 0.0

    # Use sign: sell = +price*qty, buy = -price*qty
    for leg in legs:
        sign = 1 if leg["side"] == "sell" else -1
        entry_credit += sign * leg["entry"] * leg["qty"]
        current_cost += sign * leg["ltp"] * leg["qty"]

    pnl = entry_credit - current_cost
    return {"entry_credit": entry_credit, "current_cost": current_cost, "pnl": pnl}


# Use the helper in main to keep behavior identical
    result = compute_pnl(legs)
    entry_credit = result["entry_credit"]
    current_cost = result["current_cost"]
    pnl = result["pnl"]

    print("\nSummary:")
    for i, leg in enumerate(legs):
        print(f" Leg {i+1}: {leg['side']} entry={leg['entry']} ltp={leg['ltp']} qty={leg['qty']}")

    print(f"\nEntry credit: {entry_credit:.2f}")
    print(f"Current cost: {current_cost:.2f}")
    print(f"P&L: {pnl:.2f}")


if __name__ == "__main__":
    main()