#!/usr/bin/env python3
"""Patch src/decision.py: add asset_class to IPC snapshot_data."""

DECISION_FILE = 'C:/KAI/sovran_v2/src/decision.py'

with open(DECISION_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the snapshot_data dict and add asset_class
old_str = '                        "distance_to_drawdown": distance_to_drawdown,\n                    }'
new_str = ('                        "distance_to_drawdown": distance_to_drawdown,\n'
           '                        "asset_class": (\n'
           '                            "metals" if any(k in snapshot.contract_id for k in ["MGC", "GC"]) else\n'
           '                            "energy" if any(k in snapshot.contract_id for k in ["MCL", "CL"]) else\n'
           '                            "equity_index" if any(k in snapshot.contract_id for k in ["MNQ", "MES", "MYM", "M2K", "NQ", "ES", "YM", "RTY"]) else\n'
           '                            "other"\n'
           '                        ),  # For AI engine asset priority weighting\n'
           '                    }')

if old_str in content:
    content = content.replace(old_str, new_str, 1)
    print('PATCH: asset_class added to snapshot_data OK')
else:
    print('ERROR: target string not found')
    idx = content.find('distance_to_drawdown')
    print('Context:', repr(content[idx:idx+100]))

with open(DECISION_FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'Written: {len(content)} chars')
