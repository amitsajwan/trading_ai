import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

from kiteconnect import KiteConnect

# Ensure repo root on path
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

from data.options_chain_fetcher import OptionsChainFetcher
from data.market_memory import MarketMemory


CREDENTIAL_FILES = [
    Path("credentials.json"),
    Path("kite_credentials.json"),
]


def load_kite() -> Optional[KiteConnect]:
    api_key = os.getenv("KITE_API_KEY")
    access_token = os.getenv("KITE_ACCESS_TOKEN")

    if not api_key or not access_token:
        cred_path = next((p for p in CREDENTIAL_FILES if p.exists()), None)
        if cred_path:
            creds = json.loads(cred_path.read_text())
            api_key = creds.get("api_key") or creds.get("apiKey")
            access_token = creds.get("access_token") or creds.get("accessToken")

    if not api_key or not access_token:
        print("[ERROR] Missing KITE_API_KEY/KITE_ACCESS_TOKEN or credentials.json")
        return None

    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    return kite


def find_banknifty_token(kite: KiteConnect) -> Optional[int]:
    """Resolve BankNifty token robustly.

    Strategy:
    1) Prefer NSE index exact match 'NIFTY BANK' (stable, token ~26009)
    2) Fallback to NFO futures (segment 'NFO-FUT', tradingsymbol contains 'BANKNIFTY'),
       choose nearest non-expired expiry.
    """
    try:
        # NSE index first (exact match)
        try:
            nse_insts = kite.instruments("NSE")
            for inst in nse_insts:
                ts = (inst.get("tradingsymbol") or "").upper()
                if ts == "NIFTY BANK":
                    return inst.get("instrument_token")
        except Exception:
            pass

        # NFO FUT fallback (nearest expiry)
        nfo_insts = kite.instruments("NFO")
        futs: List[Dict[str, Any]] = []
        today = datetime.now().date()
        for inst in nfo_insts:
            if inst.get("segment") != "NFO-FUT":
                continue
            ts = (inst.get("tradingsymbol") or "").upper()
            if "BANKNIFTY" not in ts:
                continue
            expiry = inst.get("expiry")
            try:
                exp_date = expiry.date() if hasattr(expiry, "date") else expiry
            except Exception:
                exp_date = expiry
            if exp_date and exp_date >= today:
                futs.append(inst)
        if futs:
            futs.sort(key=lambda x: x.get("expiry"))
            return futs[0].get("instrument_token")
        return None
    except Exception as e:
        print(f"[ERROR] Token lookup failed: {e}")
        return None


def main():
    kite = load_kite()
    if not kite:
        return 1

    token = find_banknifty_token(kite)
    if not token:
        print("[WARN] Could not resolve BANKNIFTY token (FUT/index)")
        return 1

    print(f"[INFO] Using instrument token: {token}")

    # Quotes / LTP
    q = kite.quote([token])
    data = q.get(str(token)) or q.get(token) or {}
    ltp = data.get("last_price")
    print(f"[OK] LTP: {ltp}")

    # Depth
    depth = data.get("depth")
    if depth and isinstance(depth, dict):
        buy_levels = depth.get("buy", []) or []
        sell_levels = depth.get("sell", []) or []
        print(f"[OK] Depth available: buy={len(buy_levels)} sell={len(sell_levels)}")
        if buy_levels:
            print("  Top buy:", buy_levels[0])
        if sell_levels:
            print("  Top sell:", sell_levels[0])
    else:
        print("[INFO] Depth not available on current plan/instrument")

    # Options chain snapshot (BANKNIFTY)
    mm = MarketMemory()
    fetcher = OptionsChainFetcher(kite, mm, instrument_symbol="BANKNIFTY")

    import asyncio
    async def run_chain():
        await fetcher.initialize()
        chain = await fetcher.fetch_options_chain()
        if not chain.get("available"):
            print(f"[WARN] Options chain unavailable: {chain}")
            return
        fp = chain.get("futures_price")
        strikes = chain.get("strikes", {})
        print(f"[OK] Options chain: futures_price={fp} strikes_count={len(strikes)}")
        # Show a few strikes with CE/PE
        shown = 0
        for k in sorted(strikes.keys()):
            sdata = strikes[k]
            ce = (sdata.get("ce_ltp"), sdata.get("ce_oi"), sdata.get("ce_volume"))
            pe = (sdata.get("pe_ltp"), sdata.get("pe_oi"), sdata.get("pe_volume"))
            if any(v is not None for v in ce + pe):
                print(f"  Strike {k}: CE(LTP/OI/Vol)={ce} PE(LTP/OI/Vol)={pe}")
                shown += 1
            if shown >= 5:
                break
    asyncio.run(run_chain())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
