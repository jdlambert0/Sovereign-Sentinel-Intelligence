# Sovran AI - Obsidian Mailbox System

## Overview
The Mailbox System allows human-AI communication via Obsidian vault folders. This is the primary way to interact with Sovran AI while it's running.

## Folder Structure
```
AI Mailbox/
├── Inbox/     <- YOU write messages here
├── Outbox/    <- AI writes responses here
└── Archive/   <- Processed messages go here
```

## How to Communicate with Sovran

### Step 1: Write a Message
1. Open Obsidian vault: `C:\KAI\obsidian_vault\Sovran AI\AI Mailbox\Inbox\`
2. Create a new `.md` file (e.g., `my_message.md`)
3. Write your message/command

### Step 2: AI Responds
- Sovran checks the Inbox every **30 seconds**
- Responses appear in `AI Mailbox\Outbox\`
- Original message moves to `Archive\`

## Supported Commands

### Status Commands
| Command | Description |
|---------|-------------|
| `status` | Get current system status |
| `stats` or `performance` | Get trade statistics |
| `help` or `commands` | List available commands |

### Control Commands
| Command | Description |
|---------|-------------|
| `pause` | Request trading pause |
| `resume` | Request trading resume |
| `stop` | Request full system stop |

### Configuration Commands
| Command | Description |
|---------|-------------|
| `adjust risk [number]` | Request risk parameter change |
| `trailing stop [number]` | Request trailing stop change |

### Information Commands
| Command | Description |
|---------|-------------|
| `recent trades` | Get last 5 trades |
| `learning` | Get recent research findings |

## Message Format Example

```markdown
# Hello Sovran

What's your current status?
```

## Response Format

AI responses include:
- **To:** Original filename
- **From:** Sovran AI
- **Timestamp**
- **Content:** Response to your message

## Code Integration

### File: `sovran_mailbox.py`
- Location: `C:\KAI\armada\sovran_mailbox.py`
- Check interval: 30 seconds
- Runs as background task in `sovran_ai.py`

### Functions
```python
get_inbox_messages()     # Get unread messages
send_response()          # Write response to Outbox
move_to_archive()        # Move processed message
check_and_respond()      # Main loop - call periodically
```

## Tips

1. **Be specific** - "What's my win rate?" gets better responses than "how am I doing?"
2. **Use keywords** - Include command words (status, stats, help) for best results
3. **Check Outbox** - Responses appear there, not in Inbox
4. **Patience** - AI checks every 30 seconds

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No response | Wait 30+ seconds, check Outbox |
| Response delayed | System may be busy with trades |
| Command not recognized | Use exact keywords from table above |

## For Future AI Agents - SESSION HANDOFF PROTOCOL

### ⚠️ CRITICAL: Always Work in Background During Session Handoff

When a new Claude Code session starts (session handoff), the AI agent **MUST**:

1. **BEGIN WORK IMMEDIATELY** - Do NOT wait for user instruction
2. **Read Obsidian FIRST** - Check session logs and status before taking any action
3. **Continue Previous Work** - Resume where last session left off unless explicitly told to stop
4. **Update Session Log** - Document progress before session ends

### Session Handoff Checklist:
- [ ] Read `Session Logs/` for recent sessions (most recent first)
- [ ] Check `Session Logs/2026-03-18-WebSocket-Fix-Applied.md` for latest fix status
- [ ] Check `Bug Reports/WEBSOCKET_FIX_REFERENCE.md` if WebSocket issues occur
- [ ] Check `Bug Reports/MASTER_BUG_SUMMARY.md` for known issues
- [ ] Read any pending tasks from previous sessions
- [ ] Continue background work without prompting user
- [ ] Update session log before session ends

### Where to Find Information:
| Need | Go To |
|------|-------|
| WebSocket fix | `Bug Reports/WEBSOCKET_FIX_REFERENCE.md` |
| Current system status | `Session Logs/` (most recent) |
| Known bugs | `Bug Reports/MASTER_BUG_SUMMARY.md` |
| Learning progress | `Learnings/` folder |
| Architecture | `Architecture/` folder |

---

## For Future AI Agents (Legacy)

When working with Sovran:
1. Check mailbox for human messages before each major action
2. Update system status via `update_system_status()` function
3. Increment trade count via `increment_trade_count()` after each trade
4. Read responses from Outbox to understand human feedback

---
*Last Updated: 2026-03-17*
*System: Sovran AI v3*
