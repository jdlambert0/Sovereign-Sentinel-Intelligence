#!/usr/bin/env python3
"""Quick account status check."""
import httpx

BASE_URL = "https://api.topstepx.com"
API_KEY = "9Vlu2G+cyZJ2IKJOIbI8YdEB1tmUOReiHIzlDk36EwE="
USERNAME = "jessedavidlambert@gmail.com"
ACCOUNT_ID = 20560125

r = httpx.post(f"{BASE_URL}/api/Auth/loginKey", json={
    "userName": USERNAME, "apiKey": API_KEY
})
data = r.json()
print(f"Auth: {'OK' if data.get('success') else 'FAILED'}")
if not data.get("success"):
    print(f"Error: {data.get('errorCode')} {data.get('errorMessage')}")
    exit(1)

token = data["token"]
headers = {"Authorization": f"Bearer {token}"}

# Account
r2 = httpx.post(f"{BASE_URL}/api/Account/search",
    json={"onlyActiveAccounts": True}, headers=headers)
accts = r2.json().get("accounts", [])
for a in accts:
    aid = a["id"]
    bal = a["balance"]
    can_trade = a.get("canTrade")
    print(f"  Account {aid}: Balance ${bal:,.2f} canTrade={can_trade}")

# Positions
r3 = httpx.post(f"{BASE_URL}/api/Position/searchOpen",
    json={"accountId": ACCOUNT_ID}, headers=headers)
positions = r3.json().get("positions", [])
print(f"Open positions: {len(positions)}")
for p in positions:
    print(f"  {p['contractId']} side={p.get('type')} size={p.get('size')} avg={p.get('averagePrice')}")

# Orders
r4 = httpx.post(f"{BASE_URL}/api/Order/searchOpen",
    json={"accountId": ACCOUNT_ID}, headers=headers)
orders = r4.json().get("orders", [])
print(f"Open orders: {len(orders)}")
for o in orders:
    print(f"  orderId={o.get('id')} contract={o.get('contractId')} type={o.get('type')} side={o.get('side')} stop={o.get('stopPrice')} limit={o.get('limitPrice')}")
