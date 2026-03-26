"""
Sovran AI - Obsidian Mailbox System
Allows human-AI communication via Obsidian vault folders.

Structure:
- Inbox/     -> Human writes messages here
- Outbox/    -> AI writes responses here
- Archive/   -> Processed messages go here
"""

import os
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional
import re

# Configuration
VAULT_PATH = Path(r"C:\KAI\obsidian_vault\Sovran AI")
INBOX_PATH = VAULT_PATH / "AI Mailbox" / "Inbox"
OUTBOX_PATH = VAULT_PATH / "AI Mailbox" / "Outbox"
ARCHIVE_PATH = VAULT_PATH / "AI Mailbox" / "Archive"

# Ensure directories exist
for path in [INBOX_PATH, OUTBOX_PATH, ARCHIVE_PATH]:
    path.mkdir(parents=True, exist_ok=True)


def get_inbox_messages() -> list[dict]:
    """Get all unread messages from inbox"""
    messages = []
    for f in INBOX_PATH.glob("*.md"):
        if f.name == "README.md":
            continue
        try:
            content = f.read_text(encoding="utf-8")
            messages.append(
                {
                    "filename": f.name,
                    "path": f,
                    "content": content,
                    "created": datetime.fromtimestamp(f.stat().st_ctime),
                    "modified": datetime.fromtimestamp(f.stat().st_mtime),
                }
            )
        except Exception as e:
            print(f"[MAILBOX] Error reading {f.name}: {e}")
    return sorted(messages, key=lambda x: x["created"])


def move_to_archive(message: dict):
    """Move processed message to archive"""
    archive_file = ARCHIVE_PATH / message["filename"]
    content = message["content"]
    content += f"\n\n---\n*Processed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
    archive_file.write_text(content, encoding="utf-8")
    message["path"].unlink()


def send_response(to_filename: str, response: str):
    """Write AI response to outbox"""
    base_name = Path(to_filename).stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    response_file = OUTBOX_PATH / f"RE_{base_name}_{timestamp}.md"

    content = f"""# AI Response

**To:** {to_filename}
**From:** Sovran AI
**Time:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

{response}

---

*This is an automated response from Sovran AI trading system.*
"""
    response_file.write_text(content, encoding="utf-8")
    return response_file


async def process_message(message: dict) -> str:
    """Process a message and generate AI response using LLM"""
    content = message["content"]

    # Import Sovran's core for context
    try:
        from sovran_ai import get_system_status, get_recent_trades

        system_info = await get_system_status()
    except ImportError:
        system_info = {"status": "running", "trades_today": 0}

    # Try to use LLM for intelligent response
    try:
        import os
        import sys

        sys.path.insert(0, r"C:\KAI\vortex")

        # Load env
        with open(r"C:\KAI\vortex\.env") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

        from llm_client import complete_prompt

        # Build context prompt
        system_context = f"""You are Sovran, an AI trading system. You are in LEARNING MODE.
Current system status: {system_info.get("status", "running")}
Trades today: {system_info.get("trades_today", 0)}

Your job is to:
1. TRADE to learn (not maximize profit)
2. LOG every trade in Obsidian
3. Provide PROOF of training and learning
4. Be intelligent and curious

Respond to the human's message with a thoughtful response about trading and learning."""

        full_prompt = f"{system_context}\n\nHuman: {content}\n\nSovran:"

        # Call LLM
        llm_response = await complete_prompt(full_prompt)

        # Format response
        response_lines = []
        response_lines.append(f"## Received: {message['filename']}")
        response_lines.append("")
        response_lines.append("### Intelligent Response")
        response_lines.append(llm_response)
        response_lines.append("")
        response_lines.append("### System Status")
        response_lines.append(f"- Status: {system_info.get('status', 'running')}")
        response_lines.append(
            f"- Trades Today: {system_info.get('trades_today', 'N/A')}"
        )

        return "\n".join(response_lines)

    except Exception as e:
        # Fallback to keyword matching if LLM fails
        print(f"[MAILBOX] LLM failed: {e}, using keyword fallback")

    # Keyword matching fallback
    content_lower = content.lower()
    response_lines = [f"## Received: {message['filename']}", ""]

    if "status" in content_lower or "how are you" in content_lower:
        response_lines.append("### System Status")
        response_lines.append(f"- Status: {system_info.get('status', 'running')}")
        response_lines.append(
            f"- Trades Today: {system_info.get('trades_today', 'N/A')}"
        )
        response_lines.append("")

    if "help" in content_lower or "commands" in content_lower:
        response_lines.append("### Available Commands")
        response_lines.append("- Ask about system status")
        response_lines.append("- Ask for performance stats")
        response_lines.append("- Ask to adjust risk parameters")
        response_lines.append("- Ask to pause/resume trading")
        response_lines.append("- Ask for recent trades")
        response_lines.append("")

    if "stats" in content_lower or "performance" in content_lower:
        try:
            import learning_system as learning

            stats = learning.get_performance_stats()
            response_lines.append("### Performance Stats")
            response_lines.append(f"- Total Trades: {stats.get('total_trades', 0)}")
            response_lines.append(f"- Win Rate: {stats.get('win_rate', 0) * 100:.1f}%")
            response_lines.append(f"- Total P&L: ${stats.get('total_pnl', 0):.2f}")
        except Exception as e:
            response_lines.append(f"Could not fetch stats: {e}")
        response_lines.append("")

    if "risk" in content_lower or "adjust" in content_lower:
        # Extract numeric values
        numbers = re.findall(r"\d+", content)
        if numbers:
            new_risk = int(numbers[0])
            response_lines.append(f"### Risk Adjustment")
            response_lines.append(f"Requested risk change: {new_risk} ticks")
            response_lines.append("")
            response_lines.append(
                "*Note: Risk parameter changes are noted. Manual review required for safety.*"
            )

    if "pause" in content_lower or "stop" in content_lower:
        response_lines.append("### Trading Control")
        response_lines.append("*Pause request noted. Use watchdog to pause/resume.*")

    if "resume" in content_lower or "start" in content_lower:
        response_lines.append("### Trading Control")
        response_lines.append("*Resume request noted. Use watchdog to pause/resume.*")

    # Default response if nothing matched
    if len(response_lines) <= 2:
        response_lines.append("### Message Received")
        response_lines.append(f"Your message has been received: {content[:200]}...")
        response_lines.append("")
        response_lines.append(
            "*I can respond to commands like: status, stats, help, pause, resume, or adjust risk.*"
        )

    return "\n".join(response_lines)


async def check_and_respond():
    """Main mailbox loop - check inbox and respond to messages"""
    messages = get_inbox_messages()

    if not messages:
        return None

    processed = []
    for msg in messages:
        print(f"[MAILBOX] Processing: {msg['filename']}")
        response = await process_message(msg)
        send_response(msg["filename"], response)
        move_to_archive(msg)
        processed.append(msg["filename"])

    return processed


def read_outbox_messages() -> list[dict]:
    """Get all messages from outbox"""
    messages = []
    for f in OUTBOX_PATH.glob("*.md"):
        if f.name == "README.md":
            continue
        try:
            content = f.read_text(encoding="utf-8")
            messages.append(
                {
                    "filename": f.name,
                    "path": f,
                    "content": content,
                    "created": datetime.fromtimestamp(f.stat().st_ctime),
                }
            )
        except Exception as e:
            print(f"[MAILBOX] Error reading outbox {f.name}: {e}")
    return sorted(messages, key=lambda x: x["created"], reverse=True)


# Create README files
def setup_mailbox():
    """Initialize mailbox folders with README"""
    readme_content = """# AI Mailbox - Inbox

Write your messages to Sovran AI here.

## How it works:
1. Create a new .md file with your message
2. Sovran checks this folder periodically
3. Responses appear in the Outbox folder

## Tips:
- Use clear commands (status, stats, help, pause, resume)
- Be specific about what you want
- Check Outbox for responses
"""

    for path, readme_name in [
        (INBOX_PATH, "README.md"),
        (OUTBOX_PATH, "README.md"),
        (ARCHIVE_PATH, "README.md"),
    ]:
        readme_file = path / readme_name
        if not readme_file.exists():
            readme_file.write_text(readme_content, encoding="utf-8")


if __name__ == "__main__":
    setup_mailbox()
    print("Mailbox initialized!")
    print(f"Inbox: {INBOX_PATH}")
    print(f"Outbox: {OUTBOX_PATH}")
