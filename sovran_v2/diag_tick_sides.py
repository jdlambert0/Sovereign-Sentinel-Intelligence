"""Diagnostic: check raw tick side values from the API."""
import asyncio, json, websocket, threading, time
from src.broker import BrokerClient
from collections import Counter

RECORD_SEP = "\x1e"
side_counter = Counter()
sample_trades = []

def on_message(ws, message):
    global side_counter, sample_trades
    for frame in message.split(RECORD_SEP):
        frame = frame.strip()
        if not frame:
            continue
        try:
            data = json.loads(frame)
            if data.get("type") == 6:
                ws.send('{"type":6}' + RECORD_SEP)
            elif data.get("type") == 1 and data.get("target") == "GatewayTrade":
                args = data.get("arguments", [])
                trades = args[1] if len(args) > 1 else args[0]
                if isinstance(trades, list):
                    for t in trades:
                        side = t.get("side")
                        side_counter[side] += 1
                        if len(sample_trades) < 20:
                            sample_trades.append(t)
        except:
            pass

def on_open(ws):
    ws.send('{"protocol":"json","version":1}' + RECORD_SEP)
    def sub():
        time.sleep(0.5)
        ws.send(json.dumps({"type":1,"target":"SubscribeContractTrades","arguments":["CON.F.US.MNQ.M26"],"invocationId":"t1"}) + RECORD_SEP)
    threading.Thread(target=sub, daemon=True).start()

async def main():
    c = BrokerClient(username='jessedavidlambert@gmail.com', api_key='REDACTED_TOPSTEPX_KEY', account_id=20560125)
    await c.connect()
    url = f"wss://rtc.topstepx.com/hubs/market?access_token={c.token}"
    ws = websocket.WebSocketApp(url, on_open=on_open, on_message=on_message, on_close=lambda *a: None, on_error=lambda *a: None)
    threading.Thread(target=ws.run_forever, kwargs={"ping_interval":10}, daemon=True).start()
    
    await asyncio.sleep(15)
    ws.close()
    await c.disconnect()
    
    print(f"Side distribution: {dict(side_counter)}")
    print(f"Total ticks: {sum(side_counter.values())}")
    print(f"\nSample trades:")
    for t in sample_trades[:10]:
        print(f"  side={t.get('side')} price={t.get('price')} vol={t.get('volume')} aggressor={t.get('aggressor')} aggressorSide={t.get('aggressorSide')}")

if __name__ == "__main__":
    asyncio.run(main())
