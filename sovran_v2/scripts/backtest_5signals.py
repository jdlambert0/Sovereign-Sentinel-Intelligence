"""
Backtest: 5-Signal Architecture vs Historical MNQ Tick Data
============================================================
Loads Databento MBP-10 .dbn files, reconstructs the same signals that
_compute_signals() produces during live trading, simulates trade entries
and SL/TP fills, and reports performance.

Usage:
    py -3.12 scripts/backtest_5signals.py [path/to/file.dbn]

Default data: C:/KAI/sae5.8/data/MNQ_2025_12_03.dbn
"""

import sys
import math
import json
import pathlib
from collections import deque
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "mcp_server"))

from run_server import _compute_signals

# ── Config ─────────────────────────────────────────────────────────────────
DBN_FILE = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("C:/KAI/sae5.8/data/MNQ_2025_12_03.dbn")
BAR_SECONDS   = 60          # 1-minute bars
OFI_WINDOW    = 20          # bars for OFI z-score
VPIN_WINDOW   = 50          # volume buckets for VPIN
CONVICTION_THRESHOLD = 65   # matches live system
SL_ATR_MULT   = 0.8
TP_ATR_MULT   = 1.44        # SL * 1.8
TICK_SIZE     = 0.25        # MNQ tick size
TICK_VALUE    = 2.0         # MNQ dollars per tick
CONTRACT_ID   = "CON.F.US.MNQ.M26"
REQUIRE_RTH   = False       # True = only 8:30am-3:30pm CT; False = full Globex session

# ── Helpers ────────────────────────────────────────────────────────────────

def compute_atr(bars: list, period: int = 14) -> float:
    if len(bars) < 2:
        return bars[-1]["h"] - bars[-1]["l"] if bars else 12.0
    ranges = [b["h"] - b["l"] for b in bars[-period:]]
    return sum(ranges) / len(ranges)


def compute_ofi_zscore(ofi_history: deque) -> float:
    """Z-score of current OFI relative to recent window."""
    if len(ofi_history) < 3:
        return 0.0
    vals = list(ofi_history)
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    std = math.sqrt(var) if var > 0 else 1.0
    return (vals[-1] - mean) / std


def compute_vpin(buy_vol_history: deque, total_vol_history: deque) -> float:
    """Simplified VPIN: fraction of volume that is buy-initiated."""
    bv = sum(buy_vol_history)
    tv = sum(total_vol_history)
    return bv / tv if tv > 0 else 0.5


def build_snap(bar: dict, bars: list, ofi_z: float, vpin: float,
               vwap_pv: float, vwap_vol: float) -> dict:
    price = bar["c"]
    atr = compute_atr(bars)
    vwap = vwap_pv / vwap_vol if vwap_vol > 0 else price
    prices_hist = [b["c"] for b in bars[-20:]]
    return {
        "contract_id": CONTRACT_ID,
        "price": price,
        "ofi_z": ofi_z,
        "vpin": vpin,
        "vwap": vwap,
        "atr_ticks": atr / TICK_SIZE,     # convert points -> ticks
        "avg_atr_ticks": atr / TICK_SIZE,
        "high_of_session": max(b["h"] for b in bars),
        "low_of_session": min(b["l"] for b in bars),
        "prices_history": prices_hist,
        "tick_value": TICK_VALUE,
    }


# ── Load and resample .dbn to 1-minute bars ────────────────────────────────

def load_bars_from_dbn(filepath: pathlib.Path):
    """Return list of OHLCV bar dicts + buy/sell volume per bar."""
    try:
        import databento as db
    except ImportError:
        print("ERROR: databento not installed. Run: py -3.12 -m pip install databento")
        sys.exit(1)

    print(f"Loading {filepath} ...")
    store = db.DBNStore.from_file(str(filepath))

    raw_bars: dict = {}   # bar_ts -> {o,h,l,c, buy_vol, sell_vol}
    bid1_by_time: dict = {}  # for OFI: best bid at each trade

    prev_bid1 = None
    for record in store:
        ts_ns = record.ts_event
        ts_sec = ts_ns / 1e9
        bar_ts = int(ts_sec // BAR_SECONDS) * BAR_SECONDS

        # Get best bid from levels (for OFI)
        bid1 = None
        if hasattr(record, "levels") and record.levels:
            lvl = record.levels[0]
            raw_bid = getattr(lvl, "bid_px", 0) or 0
            if raw_bid > 0:
                bid1 = raw_bid / 1e9  # databento fixed-point

        action = getattr(record, "action", "")
        if action == "T":
            raw_price = record.price / 1e9
            if raw_price <= 0:
                continue
            size = getattr(record, "size", 1) or 1
            side = getattr(record, "side", "")
            is_buy = side == "B"

            if bar_ts not in raw_bars:
                raw_bars[bar_ts] = {"o": raw_price, "h": raw_price, "l": raw_price,
                                     "c": raw_price, "buy_vol": 0, "sell_vol": 0,
                                     "ofi": 0}
            b = raw_bars[bar_ts]
            b["h"] = max(b["h"], raw_price)
            b["l"] = min(b["l"], raw_price)
            b["c"] = raw_price
            if is_buy:
                b["buy_vol"] += size
            else:
                b["sell_vol"] += size

            # OFI: delta bid depth at best level (proxy: buy - sell pressure)
            if bid1 is not None and prev_bid1 is not None:
                ofi_delta = bid1 - prev_bid1
                b["ofi"] = b.get("ofi", 0) + ofi_delta

        if bid1 is not None:
            prev_bid1 = bid1

    bars_sorted = sorted(raw_bars.items())
    print(f"  Loaded {len(bars_sorted)} 1-minute bars")
    return bars_sorted


# ── Main backtest ──────────────────────────────────────────────────────────

def run_backtest(bar_data: list):
    """Simulate hunt_and_trade logic on historical bars."""
    bars = []             # growing OHLCV list
    ofi_history = deque(maxlen=OFI_WINDOW)
    buy_vol_hist = deque(maxlen=VPIN_WINDOW)
    tot_vol_hist = deque(maxlen=VPIN_WINDOW)

    vwap_pv = 0.0
    vwap_vol = 0

    trades = []
    open_trade = None

    for ts, bdata in bar_data:
        bar = {
            "o": bdata["o"], "h": bdata["h"], "l": bdata["l"], "c": bdata["c"],
            "buy_vol": bdata["buy_vol"], "sell_vol": bdata["sell_vol"],
        }
        bars.append(bar)

        # Rolling accumulators
        bvol = bdata["buy_vol"]
        tvol = bdata["buy_vol"] + bdata["sell_vol"]
        l2_ofi = bdata.get("ofi", 0)
        ofi_val = l2_ofi if l2_ofi != 0 else (bvol - (tvol - bvol))  # use L2 OFI if available, else trade flow
        ofi_history.append(ofi_val)
        buy_vol_hist.append(bvol)
        tot_vol_hist.append(tvol)
        vwap_pv += bar["c"] * tvol
        vwap_vol += tvol

        # Need warmup bars before trading
        if len(bars) < OFI_WINDOW + 1:
            continue

        # Check if open trade hit SL/TP on this bar
        if open_trade:
            entry_price = open_trade["entry"]
            direction = open_trade["direction"]
            sl = open_trade["sl"]
            tp = open_trade["tp"]

            hit_tp = hit_sl = False
            if direction == "LONG":
                if bar["l"] <= sl:
                    hit_sl = True
                elif bar["h"] >= tp:
                    hit_tp = True
            else:  # SHORT
                if bar["h"] >= sl:
                    hit_sl = True
                elif bar["l"] <= tp:
                    hit_tp = True

            if hit_tp or hit_sl:
                exit_price = tp if hit_tp else sl
                pnl_ticks = (exit_price - entry_price) / TICK_SIZE
                if direction == "SHORT":
                    pnl_ticks = -pnl_ticks
                pnl_dollars = pnl_ticks * TICK_VALUE * open_trade["contracts"]
                open_trade["exit"] = exit_price
                open_trade["pnl_dollars"] = round(pnl_dollars, 2)
                open_trade["outcome"] = "WIN" if hit_tp else "LOSS"
                open_trade["hold_bars"] = len(bars) - open_trade["entry_bar"]
                trades.append(open_trade)
                open_trade = None

        # Don't open a new trade while one is open
        if open_trade:
            continue

        # Session filter: RTH 8:30am-3:30pm CT preferred; fall back to full Globex session for backtest
        dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
        dt_ct = dt_utc.astimezone(timezone(timedelta(hours=-6)))  # CST in Dec (UTC-6)
        ct_mins = dt_ct.hour * 60 + dt_ct.minute
        # If data has RTH bars, restrict to RTH; otherwise allow full Globex session
        if REQUIRE_RTH and not (510 <= ct_mins <= 930):   # 8:30am-3:30pm CT
            continue

        # Build signals
        ofi_z = compute_ofi_zscore(ofi_history)
        vpin = compute_vpin(buy_vol_hist, tot_vol_hist)
        snap = build_snap(bar, bars, ofi_z, vpin, vwap_pv, vwap_vol)

        try:
            signals = _compute_signals(snap)
        except Exception as e:
            continue

        # Conviction (same formula as live system)
        of_conv = signals["of_conv"]
        of_dir  = signals["of_dir"]
        alignment_bonus = 10 if signals["ps_dir"] == of_dir and of_dir != "NEUTRAL" else 0
        mom_bonus = 5 if signals["mom_dir"] == of_dir and of_dir != "NEUTRAL" else 0
        vol_penalty = -10 if signals["vol_regime"] == "high" else 0
        conviction = max(0, min(100, of_conv + alignment_bonus + mom_bonus + vol_penalty))

        if of_dir == "NEUTRAL" or conviction < CONVICTION_THRESHOLD:
            continue

        # Entry
        atr = snap["atr_ticks"] * TICK_SIZE
        sl_pts = max(2 * TICK_SIZE, atr * SL_ATR_MULT)
        tp_pts = sl_pts * 1.8

        entry = bar["c"]
        if of_dir == "LONG":
            sl_price = entry - sl_pts
            tp_price = entry + tp_pts
        else:
            sl_price = entry + sl_pts
            tp_price = entry - tp_pts

        # Position size based on conviction
        if conviction >= 75:
            contracts = 2       # using conservative base for backtest
        elif conviction >= 55:
            contracts = 1
        else:
            contracts = 1

        open_trade = {
            "direction": of_dir,
            "entry": entry,
            "sl": sl_price,
            "tp": tp_price,
            "conviction": conviction,
            "contracts": contracts,
            "entry_bar": len(bars),
            "entry_time": dt_ct.strftime("%H:%M"),
            "signals": {
                "of": signals["of_label"][:50],
                "ps": signals["ps_dir"],
                "mom": signals["mom_dir"],
            }
        }

    # Force close any open trade at end of day
    if open_trade and bar_data:
        last_bar = bar_data[-1][1]
        exit_price = last_bar["c"]
        pnl_ticks = (exit_price - open_trade["entry"]) / TICK_SIZE
        if open_trade["direction"] == "SHORT":
            pnl_ticks = -pnl_ticks
        pnl_dollars = pnl_ticks * TICK_VALUE * open_trade["contracts"]
        open_trade["exit"] = exit_price
        open_trade["pnl_dollars"] = round(pnl_dollars, 2)
        open_trade["outcome"] = "EOD_CLOSE"
        open_trade["hold_bars"] = len(bars) - open_trade["entry_bar"]
        trades.append(open_trade)

    return trades


def print_report(trades: list):
    if not trades:
        print("\nNo trades generated. Lower CONVICTION_THRESHOLD or check data.")
        return

    wins = [t for t in trades if t["outcome"] == "WIN"]
    losses = [t for t in trades if t["outcome"] == "LOSS"]
    total_pnl = sum(t["pnl_dollars"] for t in trades)
    win_pnl = sum(t["pnl_dollars"] for t in wins)
    loss_pnl = sum(t["pnl_dollars"] for t in losses)

    print(f"\n{'='*60}")
    print(f"  5-SIGNAL BACKTEST RESULTS — {DBN_FILE.name}")
    print(f"{'='*60}")
    print(f"  Total trades:   {len(trades)}")
    print(f"  Wins:           {len(wins)} ({len(wins)/len(trades)*100:.0f}%)")
    print(f"  Losses:         {len(losses)} ({len(losses)/len(trades)*100:.0f}%)")
    print(f"  EOD closes:     {sum(1 for t in trades if t['outcome']=='EOD_CLOSE')}")
    print(f"  Total PnL:      ${total_pnl:+.2f}")
    print(f"  Win PnL:        ${win_pnl:+.2f}")
    print(f"  Loss PnL:       ${loss_pnl:+.2f}")
    if wins and losses:
        avg_win  = win_pnl / len(wins)
        avg_loss = loss_pnl / len(losses)
        print(f"  Avg win:        ${avg_win:+.2f}")
        print(f"  Avg loss:       ${avg_loss:+.2f}")
        print(f"  Win/loss ratio: {abs(avg_win/avg_loss):.2f}x")
    print(f"\n  Conviction threshold: {CONVICTION_THRESHOLD}")
    print(f"  SL: {SL_ATR_MULT}x ATR | TP: {TP_ATR_MULT:.2f}x ATR (1.8 R:R)")
    print(f"\n  TRADE LOG:")
    print(f"  {'Time':6s} {'Dir':5s} {'Conv':5s} {'Entry':8s} {'Exit':8s} {'PnL':8s} {'Outcome':12s} {'OF signal'}")
    print(f"  {'-'*90}")
    for t in trades:
        sig = t.get("signals", {}).get("of", "")[:35]
        print(f"  {t.get('entry_time','?'):6s} {t['direction']:5s} {t['conviction']:5d} "
              f"{t['entry']:8.2f} {t.get('exit',0):8.2f} ${t['pnl_dollars']:+7.2f}  "
              f"{t['outcome']:12s} {sig}")
    print(f"{'='*60}\n")

    # Save JSON report
    out = pathlib.Path("state/backtest_5signals_results.json")
    out.parent.mkdir(exist_ok=True)
    with open(out, "w") as f:
        json.dump({
            "source": str(DBN_FILE),
            "trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins)/len(trades) if trades else 0,
            "total_pnl": total_pnl,
            "avg_win": win_pnl/len(wins) if wins else 0,
            "avg_loss": loss_pnl/len(losses) if losses else 0,
            "trade_log": trades
        }, f, indent=2)
    print(f"  Results saved to: {out}")


if __name__ == "__main__":
    if not DBN_FILE.exists():
        print(f"ERROR: {DBN_FILE} not found.")
        print("Usage: py -3.12 scripts/backtest_5signals.py <path/to/file.dbn>")
        sys.exit(1)

    bar_data = load_bars_from_dbn(DBN_FILE)
    trades = run_backtest(bar_data)
    print_report(trades)
