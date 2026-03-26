#!/usr/bin/env python3
"""Diagnostic: check if GatewayTrade events actually arrive from WebSocket."""
import httpx
import websocket
import json
import time
import threading

# Auth
r = httpx.post('https://api.topstepx.com/api/Auth/loginKey', json={
    'userName': 'jessedavidlambert@gmail.com',
    'apiKey': '9Vlu2G+cyZJ2IKJOIbI8YdEB1tmUOReiHIzlDk36EwE='
})
token = r.json()['token']
print(f"Authenticated")

SEP = '\x1e'
CONTRACTS = [
    'CON.F.US.ENQ.M26', 'CON.F.US.EP.M26', 'CON.F.US.MYM.M26',
    'CON.F.US.M2K.M26', 'CON.F.US.MGC.J26', 'CON.F.US.MCL.K26'
]

trade_count = {'total': 0, 'by_type': {}, 'by_contract': {}, 'quote_count': 0}

def on_message(ws, msg):
    for frame in msg.split(SEP):
        frame = frame.strip()
        if not frame:
            continue
        try:
            d = json.loads(frame)
            if d.get('type') == 6:
                ws.send(json.dumps({'type': 6}) + SEP)
            elif d.get('type') == 1:
                target = d.get('target', '')
                args = d.get('arguments', [])
                if target == 'GatewayTrade' and len(args) >= 2:
                    cid = args[0]
                    trades = args[1] if isinstance(args[1], list) else [args[1]]
                    for t in trades:
                        tt = t.get('type', -1)
                        vol = t.get('volume', 0)
                        trade_count['total'] += 1
                        trade_count['by_type'][tt] = trade_count['by_type'].get(tt, 0) + 1
                        trade_count['by_contract'][cid] = trade_count['by_contract'].get(cid, 0) + 1
                        if trade_count['total'] <= 5:
                            print(f"  Trade #{trade_count['total']}: {cid[-8:]} type={tt} vol={vol} price={t.get('price')}")
                elif target == 'GatewayQuote':
                    trade_count['quote_count'] += 1
        except json.JSONDecodeError:
            pass

def on_open(ws):
    ws.send('{"protocol":"json","version":1}' + SEP)
    time.sleep(0.5)
    for cid in CONTRACTS:
        ws.send(json.dumps({
            'type': 1, 'target': 'SubscribeContractTrades',
            'arguments': [cid], 'invocationId': f't-{cid[-8:]}'
        }) + SEP)
    print(f"Subscribed to {len(CONTRACTS)} contracts, waiting 20s...")

def on_error(ws, err):
    print(f"WS Error: {err}")

ws = websocket.WebSocketApp(
    f'wss://rtc.topstepx.com/hubs/market?access_token={token}',
    on_open=on_open, on_message=on_message, on_error=on_error
)
threading.Thread(target=ws.run_forever, daemon=True).start()

time.sleep(25)
ws.close()

print(f"\n=== TRADE FEED DIAGNOSTIC ===")
print(f"Total trade events: {trade_count['total']}")
print(f"Total quote events: {trade_count['quote_count']}")
print(f"By type: {trade_count['by_type']}")
print(f"By contract:")
for cid, cnt in sorted(trade_count['by_contract'].items()):
    print(f"  {cid}: {cnt}")
