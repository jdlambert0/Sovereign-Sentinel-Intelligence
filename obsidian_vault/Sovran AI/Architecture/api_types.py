"""
TopStepX Strict API Boundaries (ZRS Pipeline)
=============================================
This file codifies the exact data structures returned by the TopStepX API.
Do NOT guess API payload shapes. Cast all incoming JSON to these TypedDicts
to ensure Mypy catches hallucinations at compile time.
"""

from typing import TypedDict, Optional

class TopStepXQuote(TypedDict, total=False):
    """WebSocket Market Data Event Payload"""
    ticker: str
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    last_price: float
    last_size: int
    volume: float
    timestamp: str

class TopStepXPosition(TypedDict, total=False):
    """REST Response Payload for Active Positions"""
    id: str
    accountId: str
    contractId: str
    size: float
    averagePrice: float

class TopStepXOrder(TypedDict, total=False):
    """REST Response Payload for Active Orders"""
    id: str
    accountId: str
    contractId: str
    side: int         # 0=BUY, 1=SELL
    type: int         # 0=LIMIT, 1=MARKET, 2=STOP
    status: int       # 0=OPEN, 1=FILLED, 2=CANCELLED
    size: float
    limitPrice: Optional[float]
    stopPrice: Optional[float]

class TopStepXBracketResponse(TypedDict, total=False):
    """REST Response Payload for place_bracket_order"""
    isSuccess: bool
    errorMessage: Optional[str]
    entry_order_id: Optional[str]
    stop_order_id: Optional[str]
    target_order_id: Optional[str]

class TopStepXInstrumentInfo(TypedDict, total=False):
    """Nested payload within TradingSuite._instruments[symbol].instrument_info"""
    id: str           # The critical execution ID (e.g. CON.F.US.MNQ.H26)
    name: str
    tickSize: float
    tickValue: float
    description: str
