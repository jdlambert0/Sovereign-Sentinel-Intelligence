# 🔍 MECE FAULT AUDIT — Sovran AI Live Code

**Method:** Shoshin (Beginner's Mind) + MECE (Mutually Exclusive, Collectively Exhaustive)  
**Scope:** `sovran_ai.py` (927 lines), `llm_client.py` (145 lines), `openrouter.py` (73 lines)  
**Date:** 2026-03-14 | **Auditor:** Antigravity

---

## 📁 SYSTEM MAP — Where Everything Lives

```
C:\KAI\armada\                    ← EVERYTHING IS HERE
├── sovran_ai.py                  ← THE live trading engine (927 lines)
├── battle_arena.py               ← V1 simulation
├── battle_arena_v2.py            ← V2 (too cautious)
├── battle_arena_v3.py            ← V3 (Goldilocks, +$717)
├── battle_arena_v4.py            ← V4 (stress test, +$71)
├── tests/test_sovran_core.py     ← 20 unit tests
├── _data_db/                     ← All state + memory JSON (18 files)
├── _logs/                        ← All diagnostic logs
├── launch_armada.py              ← Background launcher
├── sovran_watchdog.py            ← Process monitor
└── sovran_fleet.py               ← Multi-symbol orchestrator

C:\KAI\vortex\                    ← SHARED LLM INFRASTRUCTURE
├── llm_client.py                 ← Ensemble LLM caller (145 lines)
├── providers/openrouter.py       ← OpenRouter HTTP client (73 lines)
└── .env                          ← Credentials
```

---

## 🐛 BUGS FOUND — By MECE Failure Category

### Category 1: CONNECTION (WebSocket + Network)

#### BUG 1.1: No Daily PnL Reset ⚠️ SEVERITY: HIGH

[sovran_ai.py:L157-160](file:///C:/KAI/armada/sovran_ai.py#L157-L160)

```python
# GamblerState stores daily_pnl but NOTHING resets it at session start
daily_pnl: float = 0.0
```
**Impact:** If you run Monday morning, `daily_pnl` will carry over from any previous session. If you made $500 yesterday, the `daily_profit_cap` ($2000) starts at $500, not $0.  
**Fix:** Reset `daily_pnl = 0.0` at session start in `monitor_loop` or `run()`.

#### BUG 1.2: Infinite Restart Loop Has No Backoff ⚠️ SEVERITY: MEDIUM

[sovran_ai.py:L920-927](file:///C:/KAI/armada/sovran_ai.py#L920-L927)

```python
while True:
    try:
        asyncio.run(run())
    except Exception as e:
        logger.error(f"Outer process crashed: {e}. Restarting in 15 seconds...")
        time.sleep(15)
```
**Impact:** If TopStepX is down for maintenance, this loops every 15 seconds forever, generating thousands of log lines and API auth attempts. Could get your API key rate-limited.  
**Fix:** Add exponential backoff and max retry count (e.g., max 20 restarts, then sleep 5 minutes).

---

### Category 2: DATA (Market Data Processing)

#### BUG 2.1: Session Range NaN on First Boot 🟡 SEVERITY: LOW

[sovran_ai.py:L277-278](file:///C:/KAI/armada/sovran_ai.py#L277-L278)

```python
self.high = float("-inf")
self.low = float("inf")
```
**Impact:** Before the first quote arrives, `high - low` = `-inf - inf` = `-inf`. The `build_prompt` has a guard at L415 (`if self.high == float("inf")`) but it checks `float("inf")` not `float("-inf")` — **the guard is checking the wrong sentinel value**.  
**Fix:** Change L415 to check `self.high == float("-inf")`.

#### BUG 2.2: OFI History Never Cleans Stale Entries 🟡 SEVERITY: LOW

[sovran_ai.py:L321-323](file:///C:/KAI/armada/sovran_ai.py#L321-L323)

```python
self.ofi_history.append((time.time(), delta))
if len(self.ofi_history) > self.ofi_window_trades:
    self.ofi_history.pop(0)
```
**Impact:** OFI history is length-capped (200 entries) but not time-capped. If the market goes quiet for 30 minutes, old entries from before the pause still count. OFI_Z score will reflect stale data.  
**Fix:** Add a time filter: remove entries older than 5 minutes.

---

### Category 3: LLM (AI Decision Pipeline)

#### BUG 3.1: JSON Parser Only Matches Single-Line JSON ⚠️ SEVERITY: HIGH

[sovran_ai.py:L524-531](file:///C:/KAI/armada/sovran_ai.py#L524-L531)

```python
for line in reversed(lines):
    line = line.strip()
    if line.startswith("{") and line.endswith("}"):
        try:
            decisions.append(json.loads(line))
```
**Impact:** This ONLY matches JSON on a single line. If Llama returns formatted JSON across multiple lines (common with 70B models), it will be missed. This is the **#1 most likely Monday failure**.  
**Fix:** Use `rfind("{")` / `rfind("}")` approach (already proven in battle arena code).

#### BUG 3.2: Ensemble Voting Case Sensitivity ⚠️ SEVERITY: MEDIUM

[sovran_ai.py:L554-562](file:///C:/KAI/armada/sovran_ai.py#L554-L562)

```python
if buy_votes > sell_votes and buy_votes >= wait_votes:
    consensus_dec = [d for d in decisions if d['action']=="BUY"][0]
```
**Impact:** Line 542 does `.upper()` on actions for counting, but line 555 filters for `"BUY"` (uppercase). If the model returns `"Buy"`, voting counts it as a BUY vote, but the filter on L555 won't find it → **crash with empty list**.  
**Fix:** Use `.upper()` in the filter too: `d['action'].upper()=="BUY"`.

#### BUG 3.3: Semaphore Limits Concurrency to 2 ⚠️ SEVERITY: MEDIUM

[llm_client.py:L12](file:///C:/KAI/vortex/llm_client.py#L12)

```python
_request_semaphore = asyncio.Semaphore(2)
```
**Impact:** Both ensemble models run concurrently. But the semaphore is **2**, and each model call acquires it. If `complete_ensemble` is called again before the first finishes (e.g., from a race condition), the second call queues behind the first — adding 30+ seconds of latency.  
**Not a bug per se, but capacity is tight.** OK for now.

---

### Category 4: EXECUTION (Trade Logic)

#### BUG 4.1: Confidence Gate is 0.3, Not 0.5 ⚠️ SEVERITY: MEDIUM

[sovran_ai.py:L586](file:///C:/KAI/armada/sovran_ai.py#L586)

```python
if confidence < 0.3:
```
**Impact:** The prompt says "Minimum confidence to trade: 0.50" but the code gate is 0.3. This means trades with 0.35 confidence pass the code gate even though the prompt says they shouldn't.  
**Fix:** Change to `0.50` to match the prompt.

#### BUG 4.2: Hardcoded "MNQ" in Live Order Log 🟡 SEVERITY: LOW

[sovran_ai.py:L633](file:///C:/KAI/armada/sovran_ai.py#L633)

```python
logger.info(f"Executing Live Bracket Order -> {direction} {contracts} MNQ")
```
**Impact:** If you run MES or M2K, the log says "MNQ" regardless. Misleading but not functional.  
**Fix:** Replace `MNQ` with `{self.config.symbol}`.

#### BUG 4.3: Kelly Sizing With Zero History Yields Wrong Size 🟡 SEVERITY: LOW

[sovran_ai.py:L591-594](file:///C:/KAI/armada/sovran_ai.py#L591-L594)

```python
p = self.state.rolling_win_rate * confidence  # 0.50 * 0.85 = 0.425
q = 1.0 - p                                    # 0.575
b = self.state.rolling_rr                       # 2.0 (default)
kelly = max((b * p - q) / b, 0)                 # (0.85 - 0.575) / 2.0 = 0.1375
```
**Impact:** With default state (0 trades), `rolling_win_rate` returns 0.50 and `rolling_rr` returns 2.0. This produces a Kelly fraction of 0.1375, giving ~0.034 * $4500 = $155 risk → 1 contract. **Actually reasonable.** Not a bug, just worth knowing.

---

### Category 5: STATE (Persistence + Recovery)

#### BUG 5.1: State File Corruption on Crash 🟡 SEVERITY: LOW

[sovran_ai.py:L185-188](file:///C:/KAI/armada/sovran_ai.py#L185-L188)

```python
def save(self, path: str):
    with open(path, 'w') as f:
        json.dump(asdict(self), f, indent=2, default=str)
```
**Impact:** `open('w')` truncates the file before writing. If the process crashes mid-write (e.g., power loss), the state file is empty/corrupt. Next boot loads default state, losing all history.  
**Fix:** Write to `.tmp` then `os.replace()` (atomic swap).

---

## 📊 SEVERITY SUMMARY

| Severity | Count | Bugs |
|----------|-------|------|
| 🔴 HIGH | 2 | No daily PnL reset, JSON parser single-line only |
| ⚠️ MEDIUM | 3 | Infinite restart, ensemble case sensitivity, confidence gate mismatch |
| 🟡 LOW | 5 | Session range NaN, stale OFI, hardcoded MNQ, Kelly defaults, state corruption |

---

## 🎯 CAN YOU TRUST THIS 10/10 ON MONDAY?

**Honest answer: 6/10 in current state.**

**What WILL work:**
- ✅ TopStepX connection and authentication
- ✅ MessagePack transport (battle-tested fix)
- ✅ Session phase gating (EARLY AFTERNOON + MIDDAY CHOP banned)
- ✅ Stale data guard, spread gate, force flatten
- ✅ OpenRouter with retries and rate limit handling
- ✅ Background execution (zero windows, proven)

**What WILL likely break:**
- ❌ Llama 70B returning multi-line JSON → **decision dropped → all WAITs all day**
- ❌ daily_pnl carrying over from old state → premature profit cap or wrong loss limit
- ❌ Confidence gate at 0.3 letting through low-quality trades the prompt rejected

**After fixing the 2 HIGH + 3 MEDIUM bugs: 9/10.**

The remaining 1/10 risk is inherent: free OpenRouter models can go down, TopStepX WebSocket can hiccup, and we have no historical backtest proving edge. But the code infrastructure would be solid.

---

## 📈 MARKET EXPANSION — Should You Add More Symbols?

**Recommendation: NO expansion yet. Stay with MNQ only for Week 1.**

| Symbol | V3 Arena WR | V3 PnL | Tick Value | Verdict |
|--------|-------------|--------|------------|---------|
| **MNQ** | **75%** | **+$564** | $0.50/tick | 🏆 **Run this ONLY** |
| MYM | 71% | +$329 | $0.50/tick | ✅ Week 2 candidate |
| MES | 33% | -$87 | $1.25/tick | ❌ Too expensive per tick for learning |
| M2K | 25% | -$90 | $0.50/tick | ❌ Poor performance |

**Why MNQ only:**
1. Cheapest tick ($0.50) = most forgiving for mistakes
2. Highest arena WR (75%) = best signal alignment
3. Single symbol = single state file = easier debugging
4. TopStepX trailing drawdown is $4,500 — one bad MES trade ($1.25/tick × 4 contracts) can eat $50+ in slippage alone

**Week 2 plan:** If MNQ is profitable Mon-Fri, add MYM (71% WR, same $0.50/tick cost).
