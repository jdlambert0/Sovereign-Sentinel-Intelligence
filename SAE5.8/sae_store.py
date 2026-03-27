import sqlite3
import datetime
import os
import time
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
from contextlib import contextmanager
from sae_config import config

logger = logging.getLogger(__name__)

# Institutional Standard: Dynamic path resolution
def get_db_path():
    """Resolves the current database path from config."""
    return config.get_system().get('db_path', 'sae_store.db')

# Legacy Alias for backward compatibility with test suite
DB_PATH = get_db_path()

def get_connection():
    """Establishes a connection to the SQLite DB with 30s busy timeout."""
    conn = sqlite3.connect(get_db_path(), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000;")
    return conn

@contextmanager
def get_db_connection():
    """
    Context manager ensuring connection cleanup even on exceptions.
    Increased timeout to 30s for high-load multi-core scenarios.
    """
    conn = None
    try:
        conn = sqlite3.connect(get_db_path(), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 30000;")
        yield conn
    except sqlite3.Error as e:
        logger.error(f"[DB] Connection error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def init_db(wipe: bool = False):
    """
    Initializes the database schema including the immutable Events table.

    Args:
        wipe: If True, deletes existing database before initialization
    """
    db_path = get_db_path()
    if wipe and os.path.exists(db_path):
        try:
            os.remove(db_path)
            for ext in ['-wal', '-shm']:
                if os.path.exists(db_path + ext):
                    os.remove(db_path + ext)
            logger.info(f"[STORE] Database wiped: {db_path}")
        except Exception as e:
            logger.error(f"[STORE] Failed to wipe database: {e}")

    with get_db_connection() as conn:
        try:
            sys_config = config.get_system()
            if sys_config.get('wal_mode', True):
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                conn.execute("PRAGMA wal_autocheckpoint=0;")

            # Current State: Trades
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    trading_day TEXT,
                    ticker TEXT,
                    direction TEXT,
                    entry_price TEXT,
                    size INTEGER,
                    stop_loss TEXT,
                    take_profit TEXT,
                    status TEXT,
                    exit_price TEXT,
                    exit_reason TEXT,
                    pnl_realized TEXT,
                    pnl_unrealized TEXT,
                    brain TEXT,
                    meta_features TEXT
                )
            """)

            # Add columns if they don't exist (migration)
            cursor = conn.execute("PRAGMA table_info(trades)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'trading_day' not in columns:
                conn.execute("ALTER TABLE trades ADD COLUMN trading_day TEXT")
            if 'exit_reason' not in columns:
                conn.execute("ALTER TABLE trades ADD COLUMN exit_reason TEXT")
            if 'meta_features' not in columns:
                conn.execute("ALTER TABLE trades ADD COLUMN meta_features TEXT")

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

            # Optimization: Index for daily PnL and consistency checks
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_day ON trades(trading_day)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_trade ON events(trade_id)")

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
            logger.info(f"[STORE] Database initialized at {db_path}")
        except Exception as e:
            conn.rollback()
            logger.error(f"[STORE] Database initialization failed: {e}")
            raise

def log_event_sourced(trade_id, event_type, data_dict, conn=None, timestamp=None):
    """
    Adds an immutable event to the audit trail.

    Args:
        trade_id: Trade identifier
        event_type: Type of event (e.g., 'TRADE_CREATED', 'TRADE_EXITED')
        data_dict: Event data dictionary
        conn: Optional database connection for transaction sharing
        timestamp: Optional ISO timestamp override
    """
    ts = timestamp or datetime.datetime.now().isoformat()
    # Serialize Decimals to string for JSON compatibility
    clean_data = {}
    for k, v in data_dict.items():
        clean_data[k] = str(v) if isinstance(v, Decimal) else v

    # If connection provided, use it (part of larger transaction)
    if conn:
        conn.execute("INSERT INTO events (timestamp, trade_id, event_type, data) VALUES (?, ?, ?, ?)",
                     (ts, trade_id, event_type, json.dumps(clean_data)))
    else:
        # Standalone event logging with context manager
        with get_db_connection() as conn:
            conn.execute("INSERT INTO events (timestamp, trade_id, event_type, data) VALUES (?, ?, ?, ?)",
                         (ts, trade_id, event_type, json.dumps(clean_data)))
            conn.commit()

def log_trade(trade_dict):
    """
    Inserts a new trade and logs the creation event atomically.

    Args:
        trade_dict: Dictionary containing trade details

    Raises:
        Exception: If database operation fails (transaction rolled back)
    """
    with get_db_connection() as conn:
        try:
            keys = ["trade_id", "timestamp", "trading_day", "ticker", "direction", "entry_price", "size", "stop_loss", "take_profit", "status", "brain", "pnl_unrealized", "pnl_realized", "meta_features"]
            # Handle list/dict serialization for meta_features
            clean_values = []
            for k in keys:
                val = trade_dict.get(k)
                if isinstance(val, Decimal):
                    clean_values.append(str(val))
                elif k == "meta_features" and isinstance(val, (list, dict)):
                    clean_values.append(json.dumps(val))
                else:
                    clean_values.append(val)
            
            placeholders = ",".join(["?"] * len(keys))
            cols = ",".join(keys)
            conn.execute(f"INSERT INTO trades ({cols}) VALUES ({placeholders})", clean_values)

            # Log event inside same transaction for atomicity
            log_event_sourced(trade_dict['trade_id'], "TRADE_CREATED", trade_dict, conn=conn)

            # Commit both operations together
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"[STORE] Failed to log trade {trade_dict.get('trade_id')}: {e}")
            raise

def log_trades_batch(trade_dicts: list[dict]):
    """
    Inserts multiple new trades in a single batch operation.

    Args:
        trade_dicts: List of dictionaries, each containing trade details.
    """
    if not trade_dicts:
        return

    # Assuming all trade_dicts have the same keys structure
    # This should be true if they are generated by the same BacktestBroker logic
    sample_trade = trade_dicts[0]
    keys = ["trade_id", "timestamp", "trading_day", "ticker", "direction", "entry_price", "size", "stop_loss", "take_profit", "status", "brain", "pnl_unrealized", "pnl_realized", "meta_features"]
    cols = ",".join(keys)
    placeholders = ",".join(["?"] * len(keys))

    values_to_insert = []
    for trade_dict in trade_dicts:
        # Convert Decimals to string and Lists to JSON for SQLite compatibility
        row_values = []
        for k in keys:
            val = trade_dict.get(k)
            if isinstance(val, Decimal):
                row_values.append(str(val))
            elif k == "meta_features" and isinstance(val, (list, dict)):
                row_values.append(json.dumps(val))
            else:
                row_values.append(val)
        values_to_insert.append(row_values)

    with get_db_connection() as conn:
        try:
            conn.executemany(f"INSERT INTO trades ({cols}) VALUES ({placeholders})", values_to_insert)

            # Log corresponding TRADE_CREATED events in batch
            event_values = []
            for trade_dict in trade_dicts:
                ts = datetime.datetime.now().isoformat()
                clean_data = {}
                for k, v in trade_dict.items():
                    clean_data[k] = str(v) if isinstance(v, Decimal) else v
                event_values.append((ts, trade_dict['trade_id'], "TRADE_CREATED", json.dumps(clean_data)))
            
            conn.executemany("INSERT INTO events (timestamp, trade_id, event_type, data) VALUES (?, ?, ?, ?)", event_values)
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"[STORE] Failed to log trades batch: {e}")
            raise

def update_trade_exit(trade_id, exit_price, pnl, status="CLOSED", exit_reason=None, timestamp=None):
    """
    Updates trade exit details and logs the event atomically.

    Args:
        trade_id: Trade identifier
        exit_price: Exit price as Decimal
        pnl: Realized profit/loss as Decimal
        status: Trade status (default: "CLOSED")
        exit_reason: Optional exit reason string
        timestamp: Optional ISO timestamp override
    """
    with get_db_connection() as conn:
        try:
            conn.execute("UPDATE trades SET status=?, exit_price=?, pnl_realized=?, pnl_unrealized='0.00', exit_reason=? WHERE trade_id=?",
                         (status, str(exit_price), str(pnl), exit_reason, trade_id))

            # Log event inside same transaction for atomicity
            log_event_sourced(trade_id, "TRADE_EXITED",
                            {"exit_price": str(exit_price), "pnl": str(pnl), "status": status, "exit_reason": exit_reason},
                            conn=conn, timestamp=timestamp)

            # Commit both operations together
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"[STORE] Failed to update trade exit for {trade_id}: {e}")
            raise

def update_trade_exits_batch(update_dicts: list[dict]):
    """
    Updates multiple trade exit details in a single batch operation.

    Args:
        update_dicts: List of dictionaries, each containing update details
                      (trade_id, exit_price, pnl, status, exit_reason).
    """
    if not update_dicts:
        return

    values_to_update = []
    event_values = []
    for update_dict in update_dicts:
        trade_id = update_dict['trade_id']
        exit_price = str(update_dict['exit_price'])
        pnl = str(update_dict['pnl'])
        status = update_dict['status']
        exit_reason = update_dict['exit_reason']

        # Ensure correct order and number of bindings for the UPDATE statement
        # (status, exit_price, pnl_realized, exit_reason, trade_id)
        values_to_update.append((status, exit_price, pnl, exit_reason, trade_id))

        # Prepare batch events
        ts = datetime.datetime.now().isoformat()
        clean_data = {"exit_price": exit_price, "pnl": pnl, "status": status, "exit_reason": exit_reason}
        event_values.append((ts, trade_id, "TRADE_EXITED", json.dumps(clean_data)))

    with get_db_connection() as conn:
        try:
            conn.executemany("UPDATE trades SET status=?, exit_price=?, pnl_realized=?, pnl_unrealized='0.00', exit_reason=? WHERE trade_id=?", values_to_update)
            conn.executemany("INSERT INTO events (timestamp, trade_id, event_type, data) VALUES (?, ?, ?, ?)", event_values)
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"[STORE] Failed to update trades exits batch: {e}")
            raise

def update_unrealized_pnl(trade_id, unrealized_pnl):
    """
    Updates unrealized PnL for an open trade.

    Args:
        trade_id: Trade identifier
        unrealized_pnl: Current unrealized profit/loss as Decimal

    Raises:
        Exception: If database operation fails
    """
    with get_db_connection() as conn:
        try:
            conn.execute("UPDATE trades SET pnl_unrealized=? WHERE trade_id=?",
                         (str(unrealized_pnl), trade_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"[STORE] Failed to update unrealized PnL for {trade_id}: {e}")
            raise

def get_daily_pnl(market_date: str = None) -> Decimal:
    """Get daily PnL using context manager for safe connection handling."""
    with get_db_connection() as conn:
        if market_date is None:
            market_date = datetime.datetime.now().strftime("%Y-%m-%d")

        cursor = conn.execute("SELECT pnl_realized, pnl_unrealized FROM trades WHERE trading_day = ?", (market_date,))
        total = Decimal("0.00")
        for row in cursor.fetchall():
            realized = Decimal(row[0]) if row[0] else Decimal("0.00")
            unrealized = Decimal(row[1]) if row[1] else Decimal("0.00")
            total += (realized + unrealized)
        return total

def get_open_positions_count():
    """Get count of open positions using context manager."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM trades WHERE status='OPEN'")
        return cursor.fetchone()[0]

def get_control_flag(key):
    """Get control flag value using context manager."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT value FROM control WHERE key=?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None

def set_control_flag(key, value):
    """Set control flag value using context manager."""
    with get_db_connection() as conn:
        ts = datetime.datetime.now().isoformat()
        conn.execute("INSERT OR REPLACE INTO control (key, value, updated_at) VALUES (?, ?, ?)",
                     (key, value, ts))
        conn.commit()

def get_total_pnl() -> Decimal:
    """Get total PnL across all trades using context manager."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT pnl_realized, pnl_unrealized FROM trades")
        total = Decimal("0.00")
        for row in cursor.fetchall():
            realized = Decimal(row[0]) if row[0] else Decimal("0.00")
            unrealized = Decimal(row[1]) if row[1] else Decimal("0.00")
            total += (realized + unrealized)
        return total

def log_journal(level: str, component: str, message: str):
    """Logs a system message to the journal table."""
    with get_db_connection() as conn:
        ts = datetime.datetime.now().isoformat()
        conn.execute("INSERT INTO journal (timestamp, level, component, message) VALUES (?, ?, ?, ?)",
                     (ts, level, component, message))
        conn.commit()

def get_consistency_report(threshold: float = 0.4) -> Dict[str, Any]:
    """
    Calculates TopstepX Consistency Rule metrics.
    Rule: No single trading day can account for > 40% of total profit.
    """
    with get_db_connection() as conn:
        # Group realized PnL by day
        cursor = conn.execute("""
            SELECT trading_day, SUM(CAST(pnl_realized AS REAL)) as daily_sum 
            FROM trades 
            WHERE status='CLOSED'
            GROUP BY trading_day 
            HAVING daily_sum > 0
        """)
        
        daily_profits = {row[0]: row[1] for row in cursor.fetchall()}
        if not daily_profits:
            return {"status": "INSUFFICIENT_DATA", "passed": True, "details": {}}
            
        total_profit = sum(daily_profits.values())
        best_day_profit = max(daily_profits.values())
        best_day_date = max(daily_profits, key=daily_profits.get)
        
        consistency_ratio = best_day_profit / total_profit if total_profit > 0 else 0
        passed = consistency_ratio <= threshold
        
        return {
            "status": "OK",
            "passed": passed,
            "total_profit": total_profit,
            "best_day_profit": best_day_profit,
            "best_day_date": best_day_date,
            "consistency_ratio": consistency_ratio,
            "threshold": threshold,
            "required_total_for_pass": best_day_profit / threshold if threshold > 0 else 0
        }

if __name__ == "__main__":
    init_db()


