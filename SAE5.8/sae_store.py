import sqlite3
import datetime
import os
import time
import json
from decimal import Decimal
from sae_config import config

# Configuration from central store
sys_config = config.get_system()
DB_PATH = sys_config['db_path']

def get_connection():
    """Establishes a connection to the SQLite DB with 5s timeout."""
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema including the immutable Events table."""
    conn = get_connection()
    try:
        if sys_config.get('wal_mode', True):
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;") 
            conn.execute("PRAGMA wal_autocheckpoint=0;")
        
        # Current State: Trades
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                timestamp TEXT,
                ticker TEXT,
                direction TEXT,
                entry_price TEXT,
                size INTEGER,
                stop_loss TEXT,
                take_profit TEXT,
                status TEXT,
                exit_price TEXT,
                pnl_realized TEXT,
                pnl_unrealized TEXT,
                brain TEXT
            )
        """)
        
        # Immutable Audit Trail: Events (Event Sourcing)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                trade_id TEXT,
                event_type TEXT, -- 'SIGNAL', 'ORDER_SENT', 'FILL', 'REJECT', 'EXIT'
                data TEXT        -- JSON blob of event details
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT, level TEXT, component TEXT, message TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS control (
                key TEXT PRIMARY KEY, value TEXT, updated_at TEXT
            )
        """)
        
        cursor = conn.execute("SELECT value FROM control WHERE key='system_status'")
        if not cursor.fetchone():
            conn.execute("INSERT INTO control (key, value, updated_at) VALUES (?, ?, ?)", 
                         ("system_status", "RUNNING", datetime.datetime.now().isoformat()))

        conn.commit()
        print(f"[STORE] Database initialized at {DB_PATH} (Event Sourcing Enabled)")
    finally:
        conn.close()

def log_event_sourced(trade_id, event_type, data_dict):
    """Adds an immutable event to the audit trail."""
    conn = get_connection()
    try:
        ts = datetime.datetime.now().isoformat()
        # Serialize Decimals to string for JSON compatibility
        clean_data = {}
        for k, v in data_dict.items():
            clean_data[k] = str(v) if isinstance(v, Decimal) else v
            
        conn.execute("INSERT INTO events (timestamp, trade_id, event_type, data) VALUES (?, ?, ?, ?)",
                     (ts, trade_id, event_type, json.dumps(clean_data)))
        conn.commit()
    except Exception as e:
        print(f"[STORE] Event logging failed: {e}")
    finally:
        conn.close()

def perform_checkpoint():
    conn = get_connection()
    try:
        print("[STORE] Performing PASSIVE WAL Checkpoint...")
        conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
    except Exception as e:
        print(f"[STORE] Checkpoint failed: {e}")
    finally:
        conn.close()

def log_trade(trade_dict):
    """Inserts a new trade and logs the creation event."""
    conn = get_connection()
    try:
        conn.execute("BEGIN TRANSACTION;")
        keys = ["trade_id", "timestamp", "ticker", "direction", "entry_price", "size", "stop_loss", "take_profit", "status", "brain", "pnl_unrealized", "pnl_realized"]
        values = [str(trade_dict.get(k)) if isinstance(trade_dict.get(k), Decimal) else trade_dict.get(k) for k in keys]
        placeholders = ",".join(["?"] * len(keys))
        cols = ",".join(keys)
        conn.execute(f"INSERT INTO trades ({cols}) VALUES ({placeholders})", values)
        conn.commit()
        # Also log as event
        log_event_sourced(trade_dict['trade_id'], "TRADE_CREATED", trade_dict)
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def update_trade_exit(trade_id, exit_price, pnl, status="CLOSED"):
    conn = get_connection()
    try:
        conn.execute("UPDATE trades SET status=?, exit_price=?, pnl_realized=?, pnl_unrealized='0.00' WHERE trade_id=?",
                     (status, str(exit_price), str(pnl), trade_id))
        conn.commit()
        log_event_sourced(trade_id, "TRADE_EXITED", {"exit_price": str(exit_price), "pnl": str(pnl), "status": status})
    finally:
        conn.close()

def update_unrealized_pnl(trade_id, unrealized_pnl):
    """
    METASCOUTER FIX (Phase 4): Update unrealized PnL for open position

    Called on every tick to reflect current P&L before position closes.
    Critical for daily loss limit enforcement (must include unrealized).

    Invariants:
    - Only updates pnl_unrealized column (doesn't touch realized)
    - Uses Decimal string conversion for precision
    - Fast operation (single UPDATE, no transaction needed)
    """
    conn = get_connection()
    try:
        conn.execute("UPDATE trades SET pnl_unrealized=? WHERE trade_id=?",
                     (str(unrealized_pnl), trade_id))
        conn.commit()
    except Exception as e:
        print(f"[STORE] Failed to update unrealized PnL for {trade_id}: {e}")
    finally:
        conn.close()

def get_daily_pnl(market_date: str = None) -> Decimal:
    """
    PHASE 3: Get daily PnL for a specific market date (Daily Limits Fix)

    Args:
        market_date: Market date in YYYY-MM-DD format. If None, uses system date (live trading).

    Returns:
        Total realized + unrealized PnL for the specified date
    """
    conn = get_connection()
    try:
        if market_date is None:
            market_date = datetime.datetime.now().strftime("%Y-%m-%d")

        cursor = conn.execute("SELECT pnl_realized, pnl_unrealized FROM trades WHERE date(timestamp) LIKE ? || '%'", (market_date,))
        total = Decimal("0.00")
        for row in cursor.fetchall():
            realized = Decimal(row[0]) if row[0] else Decimal("0.00")
            unrealized = Decimal(row[1]) if row[1] else Decimal("0.00")
            total += (realized + unrealized)
        return total
    finally:
        conn.close()

def get_open_positions_count():
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM trades WHERE status='OPEN'")
        return cursor.fetchone()[0]
    finally:
        conn.close()

def get_control_flag(key):
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT value FROM control WHERE key=?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()

def set_control_flag(key, value):
    conn = get_connection()
    try:
        ts = datetime.datetime.now().isoformat()
        conn.execute("INSERT OR REPLACE INTO control (key, value, updated_at) VALUES (?, ?, ?)",
                     (key, value, ts))
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()


def get_total_pnl() -> Decimal:
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT pnl_realized, pnl_unrealized FROM trades")
        total = Decimal("0.00")
        for row in cursor.fetchall():
            realized = Decimal(row[0]) if row[0] else Decimal("0.00")
            unrealized = Decimal(row[1]) if row[1] else Decimal("0.00")
            total += (realized + unrealized)
        return total
    finally:
        conn.close()
