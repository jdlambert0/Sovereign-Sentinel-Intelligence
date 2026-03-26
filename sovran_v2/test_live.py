"""Quick live integration test for Layer 0 Broker Client."""
import asyncio
from src.broker import BrokerClient

async def test():
    client = BrokerClient(
        username='jessedavidlambert@gmail.com',
        api_key='REDACTED_TOPSTEPX_KEY',
        account_id=20560125
    )
    try:
        ok = await client.ping()
        print(f"Ping: {ok}")
        await client.connect()
        print(f"Account ID: {client.account_id}")
        print(f"Balance: ${client.account_balance:,.2f}")
        positions = await client.get_open_positions()
        print(f"Open positions: {len(positions)}")
        for p in positions:
            print(f"  {p}")
        pnl = await client.get_realized_pnl()
        print(f"Session PnL: ${pnl:,.2f}")
        orders = await client.get_open_orders()
        print(f"Open orders: {len(orders)}")
        contracts = await client.search_contracts("MNQ")
        for c in contracts[:3]:
            print(f"  Contract: {c['name']} id={c['id']} tick={c['tickSize']} tickVal={c['tickValue']}")
        await client.disconnect()
        print("\nSUCCESS - Layer 0 is LIVE and VERIFIED")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback; traceback.print_exc()
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test())
