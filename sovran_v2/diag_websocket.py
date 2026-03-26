"""Diagnostic: test raw WebSocket connection to TopStepX Market Hub."""
import asyncio
import json
import websocket
import threading
import time
from src.broker import BrokerClient

RECORD_SEP = "\x1e"
CONTRACT_IDS = ["CON.F.US.MNQ.M26", "CON.F.US.MNQM26"]  # Test both formats

def on_message(ws, message):
    frames = message.split(RECORD_SEP)
    for frame in frames:
        frame = frame.strip()
        if not frame:
            continue
        try:
            data = json.loads(frame)
            msg_type = data.get("type")
            if msg_type == 6:
                ws.send(json.dumps({"type": 6}) + RECORD_SEP)
            elif msg_type == 3:
                inv_id = data.get("invocationId", "")
                err = data.get("error")
                result = data.get("result")
                print(f"[COMPLETION] id={inv_id} result={result} error={err}")
            elif msg_type == 1:
                target = data.get("target", "")
                args = data.get("arguments", [])
                if target == "GatewayQuote":
                    q = args[1] if len(args) > 1 else args[0]
                    print(f"[QUOTE] last={q.get('lastPrice')} bid={q.get('bestBid')} ask={q.get('bestAsk')} vol={q.get('volume')}")
                elif target == "GatewayTrade":
                    trades = args[1] if len(args) > 1 else args[0]
                    if isinstance(trades, list):
                        for t in trades[:3]:
                            print(f"[TRADE] price={t.get('price')} vol={t.get('volume')} side={t.get('side')}")
                    else:
                        print(f"[TRADE] {trades}")
                elif target == "GatewayLogout":
                    print(f"[LOGOUT] Server forced logout! args={args}")
                else:
                    print(f"[EVENT] target={target}: {json.dumps(data)[:200]}")
            elif msg_type == 7:
                print(f"[CLOSE MSG] Server closing: {data}")
            elif msg_type is None:
                print(f"[HANDSHAKE OK] {data}")
            else:
                print(f"[TYPE {msg_type}] {json.dumps(data)[:200]}")
        except json.JSONDecodeError:
            print(f"[RAW] {repr(frame[:100])}")

def on_error(ws, error):
    print(f"[ERROR] {error}")

def on_close(ws, code, msg):
    print(f"[CLOSED] code={code}, msg={msg}")

def on_open(ws):
    print("[CONNECTED] Sending handshake...")
    ws.send('{"protocol":"json","version":1}' + RECORD_SEP)
    
    # Delayed subscriptions — proven to work in v1
    def _subscribe():
        time.sleep(0.5)
        for cid in CONTRACT_IDS:
            print(f"\n[SUBSCRIBING] Quotes+Trades for {cid}")
            ws.send(json.dumps({
                "type": 1,
                "target": "SubscribeContractQuotes",
                "arguments": [cid],
                "invocationId": f"q-{cid}"
            }) + RECORD_SEP)
            ws.send(json.dumps({
                "type": 1,
                "target": "SubscribeContractTrades",
                "arguments": [cid],
                "invocationId": f"t-{cid}"
            }) + RECORD_SEP)
            time.sleep(0.5)
        print("[SUBSCRIBED] Waiting for data...")
    
    threading.Thread(target=_subscribe, daemon=True).start()

async def main():
    client = BrokerClient(
        username='jessedavidlambert@gmail.com',
        api_key='REDACTED_TOPSTEPX_KEY',
        account_id=20560125
    )
    await client.connect()
    token = client.token
    print(f"Token: {token[:30]}...")
    print(f"Account: {client.account_id}, Balance: ${client.account_balance:,.2f}")
    
    url = f"wss://rtc.topstepx.com/hubs/market?access_token={token}"
    
    ws = websocket.WebSocketApp(
        url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    thread = threading.Thread(target=ws.run_forever, kwargs={"ping_interval": 10, "ping_timeout": 5}, daemon=True)
    thread.start()
    
    for i in range(45):
        await asyncio.sleep(1)
        if i % 10 == 0:
            print(f"--- {i}s elapsed ---")
    
    ws.close()
    await client.disconnect()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
