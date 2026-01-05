from engine_module.tools.pl_calculator import compute_pnl


def test_compute_pnl_single_leg_buy():
    legs = [{"side": "buy", "entry": 100.0, "ltp": 110.0, "qty": 1}]
    res = compute_pnl(legs)
    # buy sign = -1 => entry_credit = -100, current_cost = -110 => pnl = -100 - (-110) = 10
    assert abs(res["entry_credit"] + 100.0) < 1e-6
    assert abs(res["current_cost"] + 110.0) < 1e-6
    assert abs(res["pnl"] - 10.0) < 1e-6


def test_compute_pnl_multi_leg():
    legs = [
        {"side": "sell", "entry": 50.0, "ltp": 55.0, "qty": 2},
        {"side": "buy", "entry": 20.0, "ltp": 18.0, "qty": 3},
    ]
    res = compute_pnl(legs)
    # sell leg: +50*2=100 entry, current +55*2=110 -> buy leg: -20*3=-60 entry, -18*3=-54 current
    # entry_credit = 100 - 60 = 40; current_cost = 110 - 54 = 56; pnl = 40 - 56 = -16
    assert abs(res["entry_credit"] - 40.0) < 1e-6
    assert abs(res["current_cost"] - 56.0) < 1e-6
    assert abs(res["pnl"] + 16.0) < 1e-6
