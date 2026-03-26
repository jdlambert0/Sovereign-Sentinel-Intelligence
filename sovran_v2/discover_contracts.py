"""Discover available contracts on the broker."""
import asyncio
from src.broker import BrokerClient

async def main():
    c = BrokerClient(
        username='jessedavidlambert@gmail.com',
        api_key='REDACTED_TOPSTEPX_KEY',
        account_id=20560125
    )
    await c.connect()
    print(f"Account: {c.account_id}, Balance: ${c.account_balance:,.2f}")
    
    # Search for MNQ contracts
    contracts = await c.search_contracts('MNQ')
    print(f"\nMNQ search: {len(contracts)} results")
    for ct in contracts:
        print(f"  {ct}")
    
    # Try available contracts
    avail = await c.get_available_contracts()
    print(f"\nAll available contracts: {len(avail)}")
    for ct in avail:
        print(f"  {ct['id']} - {ct.get('name','')} - active={ct.get('activeContract')}")
    
    # Also try specific IDs that might work
    for cid in ["CON.F.US.MNQM26", "CON.F.US.MNQ.M26", "CON.F.US.MNQM6"]:
        try:
            ct = await c.get_contract_by_id(cid)
            print(f"\nFound by ID '{cid}': {ct}")
        except Exception as e:
            print(f"\n'{cid}' not found: {e}")
    
    await c.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
