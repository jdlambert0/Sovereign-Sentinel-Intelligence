#!/usr/bin/env python3
"""Monitor open position PnL in real-time."""
import json, time, sys, threading
sys.path.insert(0, "/tmp/pylibs")
import httpx, websocket

API_KEY = "9Vlu2G+cyZJ2IKJOIbI8YdEB1tmUOReiHIzlDk36EwE="
USERNAME = "jessedavidlambert@gmail.com"
ACCOUNT_ID = 20560125
SEP = "\x1e"

# Auth
client = httpx.Client(base_url="https://api.topstepx.com", timeout=20.0)
r = client.post("/api/Auth/loginKey", json={"userName": USERNAME, "apiKey": API_KEY})
token = r.json()["token"]
headers = {"Authorization": f"Bearer {token}"}

# Get current position
r = client.post("/api/Position/searchOpen", json={"accountId": ACCOUNT_ID}, headers=headers)
positions = r.json().get("positions", [])
if not positions:
    print("No open positions")
    sys.exit(0)

pos = positions[0]
entry = pos["averagePrice"]
contract = pos["contractId"]
size = pos["size"]
side = "LONG" if pos["type"] == 1 else "SHORT"
print(f"Position: {side} {size}x {pos['contractDisplayName']} @ {entry}")

# Track via WebSocket
last_price = [entry]
updates = [0]

def on_message(ws, message):
    for frame in message.split(SEP):
        frame = frame.strip()
        if not frame: continue
        try:
            data = json.loads(frame)
            if data.get("type") == 6:
                ws.send(json.dumps({"type": 6}) + SEP)
            elif data.get("type") == 1:
                target = data.get("target", "")
                args = data.get("arguments", [])
                if target == "GatewayQuote" and len(args) >= 2:
                    q = args[1]
                    if "lastPrice" in q:
                        lp = float(q["lastPrice"])
                        last_price[0] = lp
                        updates[0] += 1
                        if side == "LONG":
                            pnl = (lp - entry) * 0.50  # MYM tick_value
                            ticks = (lp - entry) / 1.0  # MYM tick_size = 1.0
                        else:
                            pnl = (entry - lp) * 0.50
                            ticks = (entry - lp) / 1.0
                        if updates[0] % 5 == 0:  # Print every 5th update
                            emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
                            print(f"  {emoji} {pos['contractDisplayName']} @ {lp:,.0f} | PnL: ${pnl:+.2f} ({ticks:+.0f} ticks) | Updates: {updates[0]}")
        except: pass

def on_open(ws):
    ws.send('{"protocol":"json","version":1}' + SEP)
    def _sub():
        time.sleep(0.5)
        ws.send(json.dumps({
            "type": 1, "target": "SubscribeContractQuotes",
            "arguments": [contract], "invocationId": "q-monitor"
        }) + SEP)
    threading.Thread(target=_sub, daemon=True).start()

url = f"wss://rtc.topstepx.com/hubs/market?access_token={token}"
ws = websocket.WebSocketApp(url, on_open=on_open, on_message=on_message,
                           on_error=lambda ws,e: print(f"WS Error: {e}"),
                           on_close=lambda ws,c,m: print(f"WS Closed: {c} {m}"))
threading.Thread(target=ws.run_forever, daemon=True).start()

# Monitor for up to 5 minutes, checking position every 15s
for i in range(20):
    time.sleep(15)
    # Check if position still open
    try:
        r = client.post("/api/Position/searchOpen", json={"accountId": ACCOUNT_ID}, headers=headers)
        pos_now = r.json().get("positions", [])
        if not pos_now:
            lp = last_price[0]
            if side == "LONG":
                final_pnl = (lp - entry) * 0.50
            else:
                final_pnl = (entry - lp) * 0.50
            print(f"\n🏁 POSITION CLOSED! Last seen @ {lp:,.0f} | Approx PnL: ${final_pnl:+.2f}")
            
            # Get account balance
            r = client.post("/api/Account/search", json={"onlyActiveAccounts": True}, headers=headers)
            accts = r.json().get("accounts", [])
            if accts:
                print(f"   Balance: ${accts[0]['balance']:,.2f}")
            
            # Get recent trades for actual fill
            r = client.post("/api/Trade/search", json={"accountId": ACCOUNT_ID}, headers=headers)
            trades = r.json().get("trades", [])
            for t in trades[-3:]:
                print(f"   Trade: {t.get('contractId')} side={t.get('side')} price={t.get('price')} size={t.get('size')} tag={t.get('customTag','')}")
            break
    except Exception as e:
        print(f"Error checking position: {e}")

ws.close()
print(f"\nTotal price updates: {updates[0]}")
