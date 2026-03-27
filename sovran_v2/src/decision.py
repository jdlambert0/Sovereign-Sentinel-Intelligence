"""
Layer 3 — The Mind (AI Decision Engine)

Replaces hardcoded rule-based frameworks with an LLM-driven decision engine.
Supports three AI backends:
  A) Local LLM via Ollama
  B) Cloud API via OpenRouter (or any OpenAI-compatible API)
  C) File-based IPC — writes a request file, waits for an external AI agent to
     write a response file. This is the primary mode for running alongside
     Gemini CLI, Accio, Antigravity, or any coding-agent AI.

The file-based IPC mode (Option C) is designed so that ANY AI system can
read the market analysis request, reason about it, and write back a structured
trading decision — making this a universal AI trading brain interface.
"""

import asyncio
import json
import logging
import math
import os
import time
import glob as glob_module
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from src.market_data import MarketSnapshot, MarketRegime
from src.risk import TradeSide


# ---------------------------------------------------------------------------
#  Data structures
# ---------------------------------------------------------------------------

@dataclass
class TradeIntent:
    """Final output of the Mind. Passed to Guardian for risk evaluation."""
    side: TradeSide
    conviction: float                  # 0-100
    thesis: str                        # Natural language reasoning
    suggested_stop_points: float       # Stop distance in points
    suggested_target_points: float     # Target distance in points
    frameworks_consulted: List[str]    # Which frameworks / analysis cited
    frameworks_agreeing: List[str]     # Alias kept for backward compat
    regime: MarketRegime
    snapshot_timestamp: float
    time_horizon: str = "scalp"        # "scalp", "swing", "position"


@dataclass
class DecisionConfig:
    """Configuration for the AI decision engine."""
    # AI backend: "ollama" | "openrouter" | "file_ipc"
    ai_provider: str = "file_ipc"
    ai_model: str = "llama3.1:70b"
    ai_api_key: str = ""
    ai_endpoint: str = "http://localhost:11434"
    ai_ipc_dir: str = "ipc"
    ai_timeout_seconds: float = 10.0
    ai_max_retries: int = 2
    ai_ipc_poll_interval: float = 0.5        # seconds between polls
    ai_ipc_max_wait_seconds: float = 120.0   # max wait for IPC response

    # Trading thresholds
    min_conviction_to_trade: float = 70.0     # Spec says Guardian blocks < 70
    min_seconds_between_trades: int = 120
    max_trades_per_session: int = 50

    # Context depth
    recent_trades_in_prompt: int = 10


class AIProvider(Enum):
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    FILE_IPC = "file_ipc"


# ---------------------------------------------------------------------------
#  Prompt builder
# ---------------------------------------------------------------------------

class PromptBuilder:
    """Constructs the analysis prompt that is sent to the AI brain."""

    SYSTEM_PREAMBLE = """You are a quantitative futures trader operating the Sovran autonomous trading system.
You analyze real-time market data and decide whether to trade. You must be disciplined:
- Only trade when you see a clear, evidence-backed setup
- Respect the math: Kelly sizing, ATR-based stops, VPIN toxicity
- NO_TRADE is always a valid (and often the best) decision
- When you do trade, have a crisp thesis and defined risk

Respond ONLY with valid JSON matching the schema below. No markdown, no explanation outside the JSON."""

    RESPONSE_SCHEMA = """{
  "signal": "long" | "short" | "no_trade",
  "conviction": <0-100>,
  "thesis": "<1-3 sentence reasoning>",
  "stop_distance_points": <float>,
  "target_distance_points": <float>,
  "frameworks_cited": ["<list of analysis approaches used>"],
  "time_horizon": "scalp" | "swing" | "position"
}"""

    @staticmethod
    def _format_cross_market(cross_market_summary: Optional[Dict[str, Any]] = None) -> str:
        """Format cross-market context for the prompt."""
        if not cross_market_summary:
            return "(No cross-market data available — single market mode)"

        lines = []
        for ac, data in cross_market_summary.items():
            sentiment = data.get("sentiment", "unknown")
            change = data.get("avg_change_pct", 0)
            regime = data.get("dominant_regime", "unknown")
            members = data.get("members", 0)
            avg_ofi = data.get("avg_ofi", 0)
            emoji = "📈" if sentiment == "bullish" else ("📉" if sentiment == "bearish" else "➡️")
            lines.append(
                f"  {emoji} *{ac}* ({members} mkt): {sentiment} | "
                f"chg {change:+.3f}% | OFI avg {avg_ofi:+.1f} | regime: {regime}"
            )
        return "\n".join(lines) if lines else "(No cross-market data)"

    @staticmethod
    def build(
        snapshot: MarketSnapshot,
        account_balance: float,
        daily_pnl: float,
        distance_to_drawdown: float,
        recent_trades: List[Dict[str, Any]],
        performance_summary: Dict[str, Any],
        contract_meta: Optional[Dict[str, Any]] = None,
        cross_market_summary: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build the full prompt for the AI brain."""
        contract_info = ""
        if contract_meta:
            contract_info = f"""
### Contract Info
- Symbol: {contract_meta.get('name', snapshot.contract_id)}
- Tick Size: {contract_meta.get('tick_size', 0.25)} points
- Tick Value: ${contract_meta.get('tick_value', 0.50)}
- Point Value: ${contract_meta.get('point_value', 2.00)}
"""

        # Format recent trades (with richer data when available from PositionManager)
        trade_lines = []
        for i, t in enumerate(recent_trades[-10:], 1):
            pnl_str = f"${t.get('net_pnl', 0):.2f}"
            exit_reason = t.get("exit_reason", "")
            hold_str = ""
            if t.get("hold_seconds"):
                hold_str = f" | Hold: {int(t['hold_seconds'])}s"
            excursion_str = ""
            if t.get("max_favorable_excursion") or t.get("max_adverse_excursion"):
                excursion_str = (
                    f" | MFE: ${t.get('max_favorable_excursion', 0):.2f}"
                    f" MAE: ${t.get('max_adverse_excursion', 0):.2f}"
                )
            exit_str = f" | Exit: {exit_reason}" if exit_reason else ""
            trade_lines.append(
                f"  {i}. {t.get('side','?').upper()} {t.get('contract_id','?')} | "
                f"PnL: {pnl_str} | Conv: {t.get('conviction', 0):.0f}"
                f"{hold_str}{excursion_str}{exit_str}"
                f"\n     Thesis: {t.get('thesis', 'N/A')[:100]}"
            )
        trades_block = "\n".join(trade_lines) if trade_lines else "  (no recent trades)"

        # Time of day context
        ct_now = datetime.now()
        try:
            import pytz
            ct_now = datetime.now(pytz.timezone("US/Central"))
        except Exception:
            pass
        hour_ct = ct_now.hour
        if 8 <= hour_ct < 10:
            session_context = "Early session — pre-market / opening volatility. Wider stops advisable."
        elif 10 <= hour_ct < 12:
            session_context = "US morning session — typically high volume, good setups."
        elif 12 <= hour_ct < 14:
            session_context = "Midday lull — lower volume, choppy price action common."
        elif 14 <= hour_ct < 16:
            session_context = "Power hour / late session — institutional positioning, strong moves possible."
        elif 17 <= hour_ct < 19:
            session_context = "Globex evening open — initial repositioning after reset."
        else:
            session_context = "Overnight / off-peak session — thinner liquidity, wider spreads."

        # L2 Depth summary
        l2_block = ""
        if hasattr(snapshot, 'l2_bid_levels') and (snapshot.l2_bid_levels or snapshot.l2_ask_levels):
            bid_lines = []
            for lvl in snapshot.l2_bid_levels[:5]:
                bid_lines.append(f"  BID {lvl.price:.2f} x {lvl.volume}")
            ask_lines = []
            for lvl in snapshot.l2_ask_levels[:5]:
                ask_lines.append(f"  ASK {lvl.price:.2f} x {lvl.volume}")
            l2_block = f"""
### L2 Order Book (Top 5)
**Bids (descending):**
{chr(10).join(bid_lines) if bid_lines else '  (no bids)'}
**Asks (ascending):**
{chr(10).join(ask_lines) if ask_lines else '  (no asks)'}
- Total Bid Volume: {snapshot.l2_bid_total_volume}
- Total Ask Volume: {snapshot.l2_ask_total_volume}
- Book Imbalance: {snapshot.bid_ask_imbalance:+.4f} (bid-weighted if positive)
"""

        prompt = f"""{PromptBuilder.SYSTEM_PREAMBLE}

---

## CURRENT MARKET SNAPSHOT — {snapshot.contract_id}
| Field | Value |
|-------|-------|
| Last Price | {snapshot.last_price:.2f} |
| Best Bid / Ask | {snapshot.best_bid:.2f} / {snapshot.best_ask:.2f} |
| Spread | {snapshot.spread:.4f} |
| ATR (14-bar) | {snapshot.atr_points:.4f} points |
| VPIN | {snapshot.vpin:.4f} (>0.7 = toxic, <0.3 = clean) |
| OFI Z-score | {snapshot.ofi_zscore:.4f} (>+2 = buy pressure, <-2 = sell pressure) |
| Bid/Ask Imbalance | {snapshot.bid_ask_imbalance:.4f} (-1 to +1) |
| Volume Rate | {snapshot.volume_rate:.2f}x average |
| Regime | {snapshot.regime.value} |
| Trend Strength (ADX) | {snapshot.trend_strength:.1f} |
| Session High / Low | {snapshot.high_of_session:.2f} / {snapshot.low_of_session:.2f} |
| Price Change % (buffer) | {snapshot.price_change_pct:.4f}% |
| Bars in buffer | {snapshot.bar_count} |
| Ticks in buffer | {snapshot.tick_count} |
{contract_info}{l2_block}
## ACCOUNT STATE
- Balance: ${account_balance:,.2f}
- Daily PnL (this session): ${daily_pnl:,.2f}
- Distance to trailing drawdown limit: ${distance_to_drawdown:,.2f}
- Win Rate: {performance_summary.get('win_rate', 0.5):.1%}
- Avg Win/Loss Ratio: {performance_summary.get('avg_win_loss_ratio', 1.8):.2f}
- Profit Factor: {performance_summary.get('profit_factor', 0):.2f}
- Total Trades: {performance_summary.get('total_trades', 0)}

## RECENT TRADE HISTORY
{trades_block}

## TIME-OF-DAY CONTEXT
- Current time (CT): {ct_now.strftime('%H:%M')}
- {session_context}

## CROSS-MARKET CONTEXT
{PromptBuilder._format_cross_market(cross_market_summary)}

## MATHEMATICAL REFERENCE
- Kelly criterion: f* = (bp - q) / b. Always use half-Kelly.
- ATR stop: minimum 1.5x ATR for stop distance
- ATR target: 2.0-3.0x ATR for positive expectancy
- VPIN > 0.7: step aside, toxic flow. VPIN < 0.3: clean.
- OFI Z > +2.0: strong buy pressure. OFI Z < -2.0: strong sell.

## YOUR TASK
Analyze the data above. Decide: LONG, SHORT, or NO_TRADE.
- Only trade if you see a clear edge.
- Provide a conviction score 0-100 (system requires >= 70 to execute).
- Suggest stop and target distances in POINTS (not ticks).
- Explain your reasoning in 1-3 sentences.

Respond with this JSON schema ONLY:
{PromptBuilder.RESPONSE_SCHEMA}
"""
        return prompt


# ---------------------------------------------------------------------------
#  AI Backend Implementations
# ---------------------------------------------------------------------------

class _OllamaBackend:
    """Option A: Local LLM via Ollama."""

    def __init__(self, config: DecisionConfig):
        self.endpoint = config.ai_endpoint.rstrip("/")
        self.model = config.ai_model
        self.timeout = config.ai_timeout_seconds

    async def call(self, prompt: str) -> Dict[str, Any]:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.endpoint}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "format": "json",
                    "stream": False,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.loads(data.get("response", "{}"))


class _OpenRouterBackend:
    """Option B: Cloud API via OpenRouter (OpenAI-compatible)."""

    def __init__(self, config: DecisionConfig):
        self.endpoint = config.ai_endpoint if "openrouter" in config.ai_endpoint else "https://openrouter.ai/api/v1/chat/completions"
        self.model = config.ai_model
        self.api_key = config.ai_api_key
        self.timeout = config.ai_timeout_seconds

    async def call(self, prompt: str) -> Dict[str, Any]:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return json.loads(content)


class _AnthropicBackend:
    """Anthropic Claude direct API backend."""

    def __init__(self, config: "DecisionConfig"):
        self.model = config.ai_model if not config.ai_model.startswith("anthropic/") else config.ai_model.split("/", 1)[1]
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", config.ai_api_key)
        self.timeout = config.ai_timeout_seconds
        self.endpoint = "https://api.anthropic.com/v1/messages"

    async def call(self, prompt: str) -> Dict[str, Any]:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.endpoint,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 512,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            text = resp.json()["content"][0]["text"].strip()
            # Extract JSON from response (may be wrapped in markdown)
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)


class _FileIPCBackend:
    """Option C: File-based IPC for external AI agents.

    Flow:
      1. System writes  <ipc_dir>/request_<ts>.json   (the prompt + metadata)
      2. External AI agent reads it, reasons, writes  <ipc_dir>/response_<ts>.json
      3. System polls for the response file and reads it.

    The request file contains both the raw prompt AND a structured data section
    so the external AI can use whichever is more convenient.

    This design works with Gemini CLI, Accio, Antigravity, Cursor, Claude Code,
    or any agent that can read/write JSON files.
    """

    def __init__(self, config: DecisionConfig):
        self.ipc_dir = config.ai_ipc_dir
        self.poll_interval = config.ai_ipc_poll_interval
        self.max_wait = config.ai_ipc_max_wait_seconds
        self.logger = logging.getLogger("sovran.decision.ipc")
        os.makedirs(self.ipc_dir, exist_ok=True)

    async def call(self, prompt: str, snapshot_data: Optional[Dict] = None) -> Dict[str, Any]:
        ts = int(time.time() * 1000)
        request_path = os.path.join(self.ipc_dir, f"request_{ts}.json")
        response_path = os.path.join(self.ipc_dir, f"response_{ts}.json")

        # Write request
        request_payload = {
            "request_id": ts,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prompt": prompt,
            "expected_response_path": response_path,
            "response_schema": {
                "signal": "long | short | no_trade",
                "conviction": "0-100",
                "thesis": "string",
                "stop_distance_points": "float",
                "target_distance_points": "float",
                "frameworks_cited": ["list of strings"],
                "time_horizon": "scalp | swing | position",
            },
            "snapshot_data": snapshot_data or {},
        }

        with open(request_path, "w") as f:
            json.dump(request_payload, f, indent=2)

        self.logger.info(f"IPC request written: {request_path}")
        self.logger.info(f"Waiting for response: {response_path}")

        # Poll for response
        start = time.time()
        while (time.time() - start) < self.max_wait:
            if os.path.exists(response_path):
                # Small delay to ensure write is complete
                await asyncio.sleep(0.1)
                try:
                    with open(response_path, "r") as f:
                        response = json.load(f)
                    self.logger.info(f"IPC response received after {time.time() - start:.1f}s")
                    # Clean up
                    try:
                        os.remove(request_path)
                        os.remove(response_path)
                    except OSError:
                        pass
                    return response
                except (json.JSONDecodeError, IOError) as e:
                    self.logger.warning(f"Error reading IPC response: {e}, retrying...")
            await asyncio.sleep(self.poll_interval)

        # Timeout — clean up request file
        self.logger.warning(f"IPC timeout after {self.max_wait}s. No response received.")
        try:
            os.remove(request_path)
        except OSError:
            pass
        raise TimeoutError(f"No IPC response within {self.max_wait}s")


# ---------------------------------------------------------------------------
#  Decision Engine
# ---------------------------------------------------------------------------

class DecisionEngine:
    """
    AI-driven decision engine. Replaces the rule-based framework system.

    Each cycle:
      1. Receives a MarketSnapshot (+ account context)
      2. Builds a rich prompt with all market data, history, and math
      3. Sends it to the AI backend (Ollama / OpenRouter / File IPC)
      4. Parses the structured response into a TradeIntent
      5. Returns the TradeIntent for the Guardian to evaluate
    """

    def __init__(self, config: Optional[DecisionConfig] = None):
        self.config = config or DecisionConfig()
        self.logger = logging.getLogger("sovran.decision")
        self.last_intent_time = 0.0
        self._trade_count_session = 0

        # Select backend
        provider = self.config.ai_provider.lower()
        if provider == "ollama":
            self._backend = _OllamaBackend(self.config)
        elif provider == "openrouter":
            self._backend = _OpenRouterBackend(self.config)
        elif provider == "anthropic":
            self._backend = _AnthropicBackend(self.config)
        else:
            self._backend = _FileIPCBackend(self.config)

        self.logger.info(f"Decision engine initialized with AI provider: {provider}")

    def load_config(self, path: str) -> None:
        """Load config from JSON file, merging with defaults."""
        try:
            with open(path, "r") as f:
                data = json.load(f)
            for k, v in data.items():
                if hasattr(self.config, k):
                    setattr(self.config, k, v)
            # Reinitialize backend if provider changed
            provider = self.config.ai_provider.lower()
            if provider == "ollama":
                self._backend = _OllamaBackend(self.config)
            elif provider == "openrouter":
                self._backend = _OpenRouterBackend(self.config)
            else:
                self._backend = _FileIPCBackend(self.config)
        except Exception as e:
            self.logger.error(f"Failed to load decision config: {e}")

    def load_config_from_env(self) -> None:
        """Load AI config from environment variables (config/.env)."""
        mappings = {
            "AI_PROVIDER": "ai_provider",
            "AI_MODEL": "ai_model",
            "AI_API_KEY": "ai_api_key",
            "AI_ENDPOINT": "ai_endpoint",
            "AI_IPC_DIR": "ai_ipc_dir",
            "AI_TIMEOUT_SECONDS": "ai_timeout_seconds",
            "AI_MAX_RETRIES": "ai_max_retries",
        }
        for env_key, attr in mappings.items():
            val = os.environ.get(env_key)
            if val is not None:
                # Type coerce
                current = getattr(self.config, attr)
                if isinstance(current, float):
                    setattr(self.config, attr, float(val))
                elif isinstance(current, int):
                    setattr(self.config, attr, int(val))
                else:
                    setattr(self.config, attr, val)

    async def analyze(
        self,
        snapshot: MarketSnapshot,
        account_balance: float = 150000.0,
        daily_pnl: float = 0.0,
        distance_to_drawdown: float = 4500.0,
        recent_trades: Optional[List[Dict[str, Any]]] = None,
        performance_summary: Optional[Dict[str, Any]] = None,
        contract_meta: Optional[Dict[str, Any]] = None,
        cross_market_summary: Optional[Dict[str, Any]] = None,
    ) -> Optional[TradeIntent]:
        """
        Analyze a market snapshot and return a TradeIntent (or None).

        This is now an async method because it calls the AI backend.
        """
        # Cooldown check
        now = time.time()
        if now - self.last_intent_time < self.config.min_seconds_between_trades:
            return None

        # Session trade limit
        if self._trade_count_session >= self.config.max_trades_per_session:
            self.logger.info("Session trade limit reached, skipping analysis")
            return None

        recent_trades = recent_trades or []
        performance_summary = performance_summary or {
            "win_rate": 0.50,
            "avg_win_loss_ratio": 1.8,
            "profit_factor": 0.0,
            "total_trades": 0,
        }

        # Build prompt
        prompt = PromptBuilder.build(
            snapshot=snapshot,
            account_balance=account_balance,
            daily_pnl=daily_pnl,
            distance_to_drawdown=distance_to_drawdown,
            recent_trades=recent_trades,
            performance_summary=performance_summary,
            contract_meta=contract_meta,
            cross_market_summary=cross_market_summary,
        )

        # Call AI backend (with retries)
        raw_response = None
        for attempt in range(self.config.ai_max_retries + 1):
            try:
                if isinstance(self._backend, _FileIPCBackend):
                    # Pass structured snapshot data for IPC
                    # Infer asset class from contract_id for priority weighting
                    _cid = snapshot.contract_id.upper()
                    if 'MCL' in _cid or '.CL.' in _cid:
                        _asset_class = 'energy'
                    elif 'MGC' in _cid or '.GC.' in _cid:
                        _asset_class = 'metals'
                    elif any(x in _cid for x in ['MES', 'MNQ', 'MYM', 'M2K']):
                        _asset_class = 'equity_index'
                    else:
                        _asset_class = 'other'

                    snapshot_data = {
                        "contract_id": snapshot.contract_id,
                        "asset_class": _asset_class,
                        "last_price": snapshot.last_price,
                        "best_bid": snapshot.best_bid,
                        "best_ask": snapshot.best_ask,
                        "spread": snapshot.spread,
                        "atr_points": snapshot.atr_points,
                        "vpin": snapshot.vpin,
                        "ofi_zscore": snapshot.ofi_zscore,
                        "bid_ask_imbalance": snapshot.bid_ask_imbalance,
                        "volume_rate": snapshot.volume_rate,
                        "regime": snapshot.regime.value,
                        "trend_strength": snapshot.trend_strength,
                        "high_of_session": snapshot.high_of_session,
                        "low_of_session": snapshot.low_of_session,
                        "price_change_pct": snapshot.price_change_pct,
                        "bar_count": snapshot.bar_count,
                        "tick_count": snapshot.tick_count,
                        "account_balance": account_balance,
                        "daily_pnl": daily_pnl,
                        "distance_to_drawdown": distance_to_drawdown,
                    }
                    raw_response = await self._backend.call(prompt, snapshot_data=snapshot_data)
                else:
                    raw_response = await self._backend.call(prompt)
                break
            except TimeoutError:
                self.logger.warning(f"AI call timeout (attempt {attempt + 1})")
            except Exception as e:
                self.logger.error(f"AI call error (attempt {attempt + 1}): {e}")
                if attempt < self.config.ai_max_retries:
                    await asyncio.sleep(1.0)

        if raw_response is None:
            self.logger.warning("All AI attempts failed — returning NO_TRADE")
            return None

        # Parse response into TradeIntent
        intent = self._parse_response(raw_response, snapshot)
        if intent is None:
            return None

        # Apply conviction threshold
        if intent.conviction < self.config.min_conviction_to_trade:
            self.logger.info(
                f"AI decision below threshold: {intent.conviction:.1f} < "
                f"{self.config.min_conviction_to_trade} — skipping"
            )
            return None

        self.last_intent_time = now
        self._trade_count_session += 1
        return intent

    def _parse_response(self, raw: Dict[str, Any], snapshot: MarketSnapshot) -> Optional[TradeIntent]:
        """Parse the AI's JSON response into a TradeIntent."""
        try:
            signal_str = str(raw.get("signal", "no_trade")).lower().strip()
            if signal_str not in ("long", "short", "no_trade"):
                self.logger.warning(f"Invalid signal from AI: {signal_str}")
                return None

            if signal_str == "no_trade":
                self.logger.info(f"AI decided NO_TRADE: {raw.get('thesis', 'no reason given')}")
                return None

            conviction = float(raw.get("conviction", 0))
            thesis = str(raw.get("thesis", ""))
            stop_pts = float(raw.get("stop_distance_points", snapshot.atr_points * 1.5))
            target_pts = float(raw.get("target_distance_points", snapshot.atr_points * 2.5))
            frameworks = raw.get("frameworks_cited", [])
            if isinstance(frameworks, str):
                frameworks = [frameworks]
            time_horizon = str(raw.get("time_horizon", "scalp"))

            # Sanity clamps
            conviction = max(0.0, min(100.0, conviction))
            stop_pts = max(snapshot.atr_points * 0.5, stop_pts)  # At least 0.5 ATR
            target_pts = max(stop_pts * 1.0, target_pts)         # At least 1:1

            side = TradeSide.LONG if signal_str == "long" else TradeSide.SHORT

            self.logger.info(
                f"AI Decision: {signal_str.upper()} conviction={conviction:.0f} "
                f"stop={stop_pts:.2f}pts target={target_pts:.2f}pts "
                f"horizon={time_horizon} thesis={thesis[:100]}"
            )

            return TradeIntent(
                side=side,
                conviction=conviction,
                thesis=thesis,
                suggested_stop_points=stop_pts,
                suggested_target_points=target_pts,
                frameworks_consulted=frameworks,
                frameworks_agreeing=frameworks,
                regime=snapshot.regime,
                snapshot_timestamp=snapshot.timestamp,
                time_horizon=time_horizon,
            )

        except (KeyError, ValueError, TypeError) as e:
            self.logger.error(f"Failed to parse AI response: {e} — raw: {raw}")
            return None

    def update_weights(self, weights: Dict[str, float]) -> None:
        """Backward compatibility stub. AI-driven engine doesn't use static weights."""
        pass

    def reset_session_count(self) -> None:
        """Reset the per-session trade counter (call at session boundary)."""
        self._trade_count_session = 0
