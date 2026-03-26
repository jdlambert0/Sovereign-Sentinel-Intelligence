"""Quick debug: inspect raw GatewayTrade events to understand side classification."""
import json, time, sys, threading
sys.path.insert(0, "/tmp/pylibs")
import httpx, websocket

API_KEY = "9Vlu2G+cyZJ2IKJOIbI8YdEB1tmUOReiHIzlDk36EwE="
USERNAME = "jessedavidlambert@gmail.com"
RECORD_SEP = "\x1e"

# Auth
client = httpx.Client(base_url="https://api.topstepx.com", timeout=20.0)
r = client.post("/api/Auth/loginKey", json={"userName": USERNAME, "apiKey": API_KEY})
token = r.json()["token"]
print(f"Auth OK, token={token[:30]}...")

trade_samples = []
quote_data = {}

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
                if target == "GatewayTrade" and len(args) >= 2:
                    cid = args[0]
                    trades = args[1]
                    if isinstance(trades, list):
                        for t in trades[:3]:
                            print(f"[TRADE] {cid[-8:]}: {json.dumps(t)}")
                            trade_samples.append(t)
                    else:
                        print(f"[TRADE] {cid[-8:]}: {json.dumps(trades)}")
                        trade_samples.append(trades)
                elif target == "GatewayQuote" and len(args) >= 2:
                    q = args[1]
                    cid = args[0]
                    if "bestBid" in q or "bestAsk" in q:
                        quote_data[cid] = q
        except:
            pass

def on_open(ws):
    print("Connected, subscribing...")
    ws.send('{"protocol":"json","version":1}' + RECORD_SEP)
    def _sub():
        time.sleep(0.5)
        for cid in ["CON.F.US.MNQ.M26", "CON.F.US.MES.M26", "CON.F.US.MCLE.K26"]:
            for target in ["SubscribeContractQuotes", "SubscribeContractTrades"]:
                ws.send(json.dumps({
                    "type": 1, "target": target,
                    "arguments": [cid], "invocationId": f"{target[:5]}-{cid[-8:]}"
                }) + RECORD_SEP)
    threading.Thread(target=_sub, daemon=True).start()

def on_error(ws, error):
    print(f"ERROR: {error}")

def on_close(ws, code, msg):
    print(f"CLOSED: {code} {msg}")

url = f"wss://rtc.topstepx.com/hubs/market?access_token={token}"
ws = websocket.WebSocketApp(url, on_open=on_open, on_message=on_message,
                            on_error=on_error, on_close=on_close)
thread = threading.Thread(target=ws.run_forever, daemon=True)
thread.start()

# Collect for 15 seconds
time.sleep(15)
ws.close()

print(f"\n=== COLLECTED {len(trade_samples)} TRADE SAMPLES ===")
if trade_samples:
    # Show all unique keys
    all_keys = set()
    for t in trade_samples:
        if isinstance(t, dict):
            all_keys.update(t.keys())
    print(f"All keys seen: {sorted(all_keys)}")
    
    # Show side distribution
    sides = {}
    for t in trade_samples:
        if isinstance(t, dict):
            s = t.get("side", t.get("aggressor", "MISSING"))
            sides[s] = sides.get(s, 0) + 1
    print(f"Side distribution: {sides}")
    
    # Show first 10
    for i, t in enumerate(trade_samples[:10]):
        print(f"  #{i}: {json.dumps(t)}")
