#!/usr/bin/env python3
"""Debug: check if WebSocket is actually receiving trade data."""
import json
import time
import threading
import websocket
import httpx

BASE_URL = "https://api.topstepx.com"
API_KEY = "9Vlu2G+cyZJ2IKJOIbI8YdEB1tmUOReiHIzlDk36EwE="
USERNAME = "jessedavidlambert@gmail.com"
WS_URL = "wss://rtc.topstepx.com/hubs/market"
RECORD_SEP = "\x1e"

CONTRACTS = [
    "CON.F.US.MNQ.M26",
    "CON.F.US.MES.M26",
    "CON.F.US.MCLE.K26",
]

# Auth
r = httpx.post(f"{BASE_URL}/api/Auth/loginKey", json={"userName": USERNAME, "apiKey": API_KEY})
token = r.json()["token"]
print(f"Auth OK, token length: {len(token)}")

# Track messages
stats = {"quotes": 0, "trades": 0, "other": 0, "buy_vol": 0, "sell_vol": 0}

def on_open(ws):
    ws.send('{"protocol":"json","version":1}' + RECORD_SEP)
    time.sleep(0.5)
    for cid in CONTRACTS:
        for target in ["SubscribeContractQuotes", "SubscribeContractTrades"]:
            ws.send(json.dumps({
                "type": 1, "target": target,
                "arguments": [cid],
                "invocationId": f"{target[:5]}-{cid[-8:]}"
            }) + RECORD_SEP)
    print(f"Subscribed to {len(CONTRACTS)} contracts")

def on_message(ws, message):
    for frame in message.split(RECORD_SEP):
        frame = frame.strip()
        if not frame:
            continue
        try:
            data = json.loads(frame)
            if data.get("type") == 6:
                ws.send(json.dumps({"type": 6}) + RECORD_SEP)
            elif data.get("type") == 1:
                target = data.get("target", "")
                args = data.get("arguments", [])
                if target == "GatewayQuote":
                    stats["quotes"] += 1
                elif target == "GatewayTrade":
                    stats["trades"] += 1
                    if len(args) >= 2:
                        trades = args[1] if isinstance(args[1], list) else [args[1]]
                        for t in trades:
                            if isinstance(t, dict):
                                tt = t.get("type", -1)
                                vol = int(t.get("volume", 1))
                                if tt == 0:
                                    stats["buy_vol"] += vol
                                elif tt == 1:
                                    stats["sell_vol"] += vol
                    # Print first few trade events for debugging
                    if stats["trades"] <= 5:
                        print(f"  TRADE EVENT: contract={args[0] if args else '?'} data={args[1] if len(args)>1 else '?'}")
                else:
                    stats["other"] += 1
        except json.JSONDecodeError:
            pass

def on_error(ws, error):
    print(f"WS error: {error}")

url = f"{WS_URL}?access_token={token}"
ws = websocket.WebSocketApp(url, on_open=on_open, on_message=on_message, on_error=on_error)
threading.Thread(target=ws.run_forever, daemon=True).start()

# Print stats every 5 seconds for 30 seconds
for i in range(6):
    time.sleep(5)
    print(f"[{(i+1)*5}s] quotes={stats['quotes']} trades={stats['trades']} B:{stats['buy_vol']} S:{stats['sell_vol']} other={stats['other']}")

ws.close()
print("Done")
