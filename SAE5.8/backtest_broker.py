
"""
BacktestBroker - Simulation Engine for SAE 5.8
Refactored for TopstepX Micro Contract Specifications.
"""

from decimal import Decimal
from sae_types import TradeEvent, L2State, Order
from friction_model import FrictionModel
import datetime

class BacktestBroker:
    # GD: Defaulted to TopstepX settings for a 50k Account.[17]
    # Initial Capital: $50,000.
    # Tick Size/Value: Defaulted to MNQ settings (0.25 / $0.50).
    def __init__(self, initial_capital=50000.00, tick_size=0.25, tick_value=0.50):
        self.balance = Decimal(str(initial_capital))
        self.equity = Decimal(str(initial_capital))
        self.max_drawdown = Decimal("0")
        self.peak_equity = Decimal(str(initial_capital))
        
        self.position = 0 
        self.position_size = 1
        self.avg_entry_price = Decimal("0")
        self.unrealized_pnl = Decimal("0")
        self.realized_pnl = Decimal("0")
        
        self.stop_price = None
        self.target_price = None
        
        self.tick_size = Decimal(str(tick_size))
        self.tick_value = Decimal(str(tick_value))
        
        # Costs (TopstepX Micros: ~$0.74 RT).
        # GD: Using FrictionModel for dynamic pricing/slippage instead of static defaults
        self.friction = FrictionModel(self.tick_size)
        
        self.trade_count = 0
        self.win_count = 0
        self.loss_count = 0
        
        # Risk Management (Strict $350 Limit -> Internal $250 Stop)
        # Metascouter: Soft Circuit Breaker (90% of firm limit)
        self.daily_loss_limit = Decimal("-350.00") # Hard Firm Limit
        self.personal_daily_loss_limit = Decimal("-325.00") # Soft Limit ($25 buffer)

        self.daily_profit_target = Decimal("1000.00")
        self.daily_profit_lock_trigger = Decimal("1000.00") # Shell logic: trigger at 1000
        self.daily_profit_lock_exit = Decimal("900.00")    # Shell logic: exit if drops to 900
        
        # Hard-coded Fee (Compliance with fi.txt)
        # $0.74 RT = $0.37 per leg
        self.commission_per_leg = Decimal("0.37")
        
        self.daily_realized_pnl = Decimal("0")
        self.daily_stop_hit = False
        self.daily_target_hit = False
        self.profit_lock_hit = False
        
        self.pending_orders = []; self.pending_fills = []
        self.trades_history = [] # Added for debugging

        # PHASE 7: Market time tracking (Daily Limits Fix)
        self.current_market_date = None
        self.previous_market_date = None
        
    def _calculate_unrealized_pnl(self, current_price: Decimal):
        if self.position == 0: return Decimal("0")
        
        # FI.TXT FIX: Explicit PnL Logic
        # Long: (Exit - Entry)
        # Short: (Entry - Exit)
        
        entry = self.avg_entry_price
        exit_p = current_price
        
        if self.position == 1:
            diff = exit_p - entry
        else: # -1
            diff = entry - exit_p
            
        ticks = diff / self.tick_size
        pnl = ticks * self.tick_value * Decimal(self.position_size)
        return pnl

    def update(self, l2_state: L2State, trade: TradeEvent):
        current_price = Decimal(str(trade.price))
        timestamp = trade.timestamp

        # PHASE 7: Track market time and detect day boundaries
        if hasattr(trade, 'timestamp') and trade.timestamp:
            market_time = datetime.datetime.fromtimestamp(trade.timestamp, tz=datetime.timezone.utc)
            self.current_market_date = market_time.strftime("%Y-%m-%d")

            # Detect day change
            if self.previous_market_date and self.current_market_date != self.previous_market_date:
                self._reset_daily_limits()

            self.previous_market_date = self.current_market_date

        # 1. Process Pending Fills (Market Physics: Exponential Latency)
        still_pending_fills = []
        for pf in self.pending_fills:
            if timestamp >= pf['fill_timestamp']:
                order = pf['order']
                self._open_position(1 if order.side == "BUY" else -1, pf['fill_price'], order.stop_ticks, order.target_ticks, order.quantity, order.ticker)
            else:
                still_pending_fills.append(pf)
        self.pending_fills = still_pending_fills

        self.unrealized_pnl = self._calculate_unrealized_pnl(current_price)     
        self.equity = self.balance + self.unrealized_pnl

        daily_total = self.daily_realized_pnl + self.unrealized_pnl

        # Auto-Liquidation Check
        if daily_total <= self.daily_loss_limit:
            self.daily_stop_hit = True
            if self.position != 0: self._close_position(current_price, "HARD_LOSS_LIMIT", trade.ticker)
            return

        # Soft Circuit Breaker
        if daily_total <= self.personal_daily_loss_limit:
            self.daily_stop_hit = True
            if self.position != 0: self._close_position(current_price, "SOFT_LOSS_LIMIT", trade.ticker)
            return

        if daily_total >= self.daily_profit_target:
            self.daily_target_hit = True
            if self.position != 0: self._close_position(current_price, "DAILY_PROFIT_TARGET", trade.ticker)
            return

        if daily_total >= self.daily_profit_lock_trigger:
            self.profit_lock_hit = True
            pass

        if self.profit_lock_hit and daily_total < self.daily_profit_lock_exit:  
            if self.position != 0: self._close_position(current_price, "PROFIT_LOCK_BANK", trade.ticker)
            self.daily_target_hit = True # Mark as done
            return

        # --- Metascouter: Trade-Through Order Processing ---
        remaining_orders = []
        for order in self.pending_orders:
            if order.ticker != trade.ticker:
                remaining_orders.append(order)
                continue

            filled = False
            if order.order_type == "MARKET":
                # Market orders: Physics-modeled Latency & Poisson Slippage
                fill_price = current_price
                if order.side == "BUY":
                    if l2_state.asks: fill_price = self.friction.apply_slippage(l2_state.asks[0].price, "BUY")
                else:
                    if l2_state.bids: fill_price = self.friction.apply_slippage(l2_state.bids[0].price, "SELL")
                
                latency = self.friction.get_fill_time()
                self.pending_fills.append({
                    'order': order,
                    'fill_price': fill_price,
                    'fill_timestamp': timestamp + latency
                })
                filled = True
            else: # LIMIT Order
                # Metascouter Rule: Fill 1 tick PAST level with 50+ volume      
                if order.side == "BUY":
                    if current_price <= order.price - self.tick_size:
                        order.trade_through_volume += trade.size
                        if order.trade_through_volume > 0: print(f" [DEBUG] Trade-through BUY accumulation: {order.trade_through_volume}/{order.trade_through_target} at {current_price}")
                        if order.trade_through_volume >= order.trade_through_target:
                            latency = self.friction.get_fill_time()
                            self.pending_fills.append({
                                'order': order,
                                'fill_price': order.price,
                                'fill_timestamp': timestamp + latency
                            })
                            filled = True
                else: # SELL
                    if current_price >= order.price + self.tick_size:
                        order.trade_through_volume += trade.size
                        if order.trade_through_volume > 0: print(f" [DEBUG] Trade-through SELL accumulation: {order.trade_through_volume}/{order.trade_through_target} at {current_price}")
                        if order.trade_through_volume >= order.trade_through_target:
                            latency = self.friction.get_fill_time()
                            self.pending_fills.append({
                                'order': order,
                                'fill_price': order.price,
                                'fill_timestamp': timestamp + latency
                            })
                            filled = True

            if not filled:
                remaining_orders.append(order)
        self.pending_orders = remaining_orders

        # Drawdown Tracking
        if self.equity > self.peak_equity: self.peak_equity = self.equity
        drawdown = self.peak_equity - self.equity
        if drawdown > self.max_drawdown: self.max_drawdown = drawdown

        # Stop/Target Check
        if self.position != 0:
            if self.stop_price:
                if (self.position == 1 and current_price <= self.stop_price) or \
                   (self.position == -1 and current_price >= self.stop_price):
                    self._close_position(current_price, "STOP_LOSS")
                    return

            if self.target_price:
                # Metascouter: Ghost Buffer Logic
                is_ghost_buffer_active = False
                try:
                    dt = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
                    ct_hour = (dt.hour - 6) % 24
                    if ct_hour < 15 or (ct_hour == 15 and dt.minute < 10):
                        if self.unrealized_pnl > 0:
                            is_ghost_buffer_active = True
                except: pass

                if not is_ghost_buffer_active:
                    if (self.position == 1 and current_price >= self.target_price) or \
                       (self.position == -1 and current_price <= self.target_price):
                        self._close_position(current_price, "PROFIT_TARGET")
                        return
    def reset_daily_pnl(self):
        self.daily_realized_pnl = Decimal("0")
        self.daily_stop_hit = False
        self.daily_target_hit = False
        self.profit_lock_hit = False

    def execute_signal(self, signal: dict, l2_state: L2State, trade: TradeEvent):
        # PHASE 7: Enhanced pre-execution limit checks (Daily Limits Fix)
        if self.daily_stop_hit or self.daily_target_hit or self.profit_lock_hit:
            return

        # PHASE 7: Check daily limits before execution (defense-in-depth)
        daily_total = self.daily_realized_pnl + self.unrealized_pnl

        if daily_total >= self.daily_profit_target:
            if not self.daily_target_hit:
                print(f"[BROKER] Order rejected. Profit target ${self.daily_profit_target} reached. Current: ${daily_total:.2f}")
                self.daily_target_hit = True
            return

        if daily_total <= self.daily_loss_limit:
            if not self.daily_stop_hit:
                print(f"[BROKER] Order rejected. Loss limit ${self.daily_loss_limit} hit. Current: ${daily_total:.2f}")
                self.daily_stop_hit = True
            return

        if not signal: return
        print(f" [DEBUG] execute_signal received: {signal.get('brain')} {signal.get('direction')} conviction:{signal.get('conviction')}")
            
        direction = signal.get('direction')
        size = signal.get('size') or signal.get('contract_size', 1)
        
        # Normalization
        if direction == "Long" or direction == 1: side = "BUY"
        elif direction == "Short" or direction == -1: side = "SELL"
        elif direction == "EXIT":
             # Immediate Exit (Market)
             exit_price = trade.price 
             if self.position == 1: 
                 if l2_state.bids: exit_price = l2_state.bids[0].price
                 self._close_position(exit_price, signal.get('reason', 'Signal Exit'), l2_state.ticker)
             elif self.position == -1: 
                 if l2_state.asks: exit_price = l2_state.asks[0].price
                 self._close_position(exit_price, signal.get('reason', 'Signal Exit'), l2_state.ticker)
             return
        else: return

        # Metascouter: All new entries use MARKET orders by default to align with shell behavior
        # unless explicitly overridden by the brain for trade-through compliance.
        order_type = signal.get('order_type', 'MARKET')
        price = Decimal(str(trade.price))
        
        from sae_config import config as sae_cfg_obj
        ms_cfg = sae_cfg_obj.get_metascouter()
        tt_target = ms_cfg.get('trade_through_target_contracts', 50)

        if order_type == "LIMIT":
            if side == "BUY" and l2_state.bids: price = l2_state.bids[0].price
            if side == "SELL" and l2_state.asks: price = l2_state.asks[0].price

        new_order = Order(
            order_id=f"ORD-{int(trade.timestamp*1000)}",
            ticker=l2_state.ticker,
            side=side,
            order_type=order_type,
            price=price,
            quantity=size,
            stop_ticks=signal.get('stop_ticks', 10),
            target_ticks=signal.get('target_ticks', 20),
            timestamp=trade.timestamp,
            trade_through_target=tt_target
        )
        
        # Avoid duplicate pending orders for same side
        if not any(o.side == side for o in self.pending_orders):
            self.pending_orders.append(new_order)

    def _open_position(self, direction, price, stop_ticks, target_ticks, size, ticker="MNQ"):
        # VALIDATION: Enforce max position size (TopstepX compliance)
        from sae_config import config as sae_cfg
        max_size = sae_cfg.get_risk().get('max_contracts', 50)
        if size > max_size:
            print(f"[WARN] Position size {size} exceeds max {max_size}, capping to max")
            size = max_size
        
        self.position = direction
        self.position_size = size
        self.avg_entry_price = price
        
        # Determine Fees via FrictionModel
        # RT Fee / 2 = Leg Fee
        rt_fee = self.friction.calculate_cost(ticker)
        leg_fee = rt_fee / 2
        
        self.balance -= leg_fee
        self.realized_pnl -= leg_fee
        self.daily_realized_pnl -= leg_fee
        self.trade_count += 1
        
        tick_val = self.tick_size
        if direction == 1:
            self.stop_price = price - (Decimal(stop_ticks) * tick_val)
            self.target_price = price + (Decimal(target_ticks) * tick_val)
        else:
            self.stop_price = price + (Decimal(stop_ticks) * tick_val)
            self.target_price = price - (Decimal(target_ticks) * tick_val)

    def _close_position(self, price, reason, ticker="MNQ"):
        # Apply Slippage on Exit if it's a STOP
        exec_price = price
        if "STOP" in reason or "DAILY" in reason:
             # Stops slip. Targets limit fill (mostly).
             side = "SELL" if self.position == 1 else "BUY"
             exec_price = self.friction.apply_slippage(price, side)
             
        closed_pnl = self._calculate_unrealized_pnl(exec_price)
        
        # Fees
        rt_fee = self.friction.calculate_cost(ticker)
        leg_fee = (rt_fee / 2) * Decimal(self.position_size)
        
        self.balance += closed_pnl
        self.balance -= leg_fee
        self.realized_pnl += (closed_pnl - leg_fee)
        
        self.daily_realized_pnl += (closed_pnl - leg_fee)
        
        if closed_pnl > 0: self.win_count += 1
        else: self.loss_count += 1
        
        self.trades_history.append({
            "strategy": "Unknown", # Can be passed in execution logic
            "direction": "Long" if self.position == 1 else "Short",
            "entry_price": float(self.avg_entry_price),
            "exit_price": float(exec_price),
            "pnl": float(closed_pnl),
            "reason": reason,
            "timestamp": "N/A" # Ideally pass timestamp
        })
        
        # CRITICAL FIX: Clear pending orders to prevent unwanted re-entry
        self.pending_orders = []
        self.pending_fills = []
           
        self.position = 0
        self.avg_entry_price = Decimal("0")
        self.stop_price = None
        self.target_price = None
        self.unrealized_pnl = Decimal("0")

    def _reset_daily_limits(self):
        """
        PHASE 7: Reset daily PnL tracking on new market day (Daily Limits Fix)

        Called when day boundary detected during backtest replay.
        """
        print(f"[BROKER] Day boundary detected. Resetting daily PnL. Previous: ${self.daily_realized_pnl:.2f}")
        self.daily_realized_pnl = Decimal("0")
        self.daily_stop_hit = False
        self.daily_target_hit = False
        self.profit_lock_hit = False
