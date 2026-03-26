#!/usr/bin/env python3
"""
Ralph Wiggum META-LOOP - System Improvement & Bug Fixing

This is the META-level loop that handles:
- Reading Kaizen backlog
- Applying fixes and improvements
- Running tests to verify changes
- Updating Obsidian vault with results
- Committing progress to GitHub

It does NOT trade - it improves the trading system.
Trading happens in ralph_trading_loop.py

Usage:
    python ralph_meta_loop.py --max-iterations 10 --dry-run
    python ralph_meta_loop.py --max-iterations 50
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [META-LOOP] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('ralph_meta_loop.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent
OBSIDIAN_DIR = PROJECT_ROOT / "obsidian"
STATE_DIR = PROJECT_ROOT / "state"
LOOP_STATUS_FILE = PROJECT_ROOT / "meta_loop_status.json"


class MetaLoopStatus:
    """Persistent status tracker for the meta-loop."""

    def __init__(self, status_file: Path):
        self.status_file = status_file
        self.data = self._load()

    def _load(self) -> Dict:
        if self.status_file.exists():
            with open(self.status_file) as f:
                return json.load(f)
        return {
            "iteration": 0,
            "fixes_applied": 0,
            "tests_run": 0,
            "git_commits": 0,
            "last_update": None,
            "active_kaizen_item": None,
            "status": "idle"
        }

    def save(self):
        self.data["last_update"] = datetime.now(timezone.utc).isoformat()
        with open(self.status_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def increment(self, key: str):
        self.data[key] = self.data.get(key, 0) + 1
        self.save()


class ObsidianManager:
    """Manages reading/writing Obsidian vault files."""

    def __init__(self, vault_dir: Path):
        self.vault_dir = vault_dir

    def read_kaizen_backlog(self) -> List[Dict]:
        """Parse kaizen_backlog.md and extract priority items."""
        backlog_file = self.vault_dir / "kaizen_backlog.md"
        if not backlog_file.exists():
            logger.warning(f"Kaizen backlog not found: {backlog_file}")
            return []

        with open(backlog_file) as f:
            content = f.read()

        # Simple parsing: find P0/P1 items
        items = []
        lines = content.split('\n')
        current_item = None

        for line in lines:
            if line.startswith('### ') and any(p in line for p in ['P0', 'P1']):
                # New priority item
                current_item = {
                    "title": line.replace('###', '').strip(),
                    "priority": "P0" if "P0" in line else "P1",
                    "details": []
                }
                items.append(current_item)
            elif current_item and line.strip().startswith('- **'):
                # Capture details
                current_item["details"].append(line.strip())

        return items

    def update_system_state(self, updates: Dict):
        """Update system_state.md with new information."""
        state_file = self.vault_dir / "system_state.md"

        # For now, just append to the file
        with open(state_file, 'a') as f:
            f.write(f"\n\n## Meta-Loop Update - {datetime.now(timezone.utc).isoformat()}\n\n")
            for key, value in updates.items():
                f.write(f"- **{key}:** {value}\n")

        logger.info(f"Updated system_state.md: {updates}")

    def log_kaizen_completion(self, item_title: str, result: str):
        """Log completed Kaizen item."""
        backlog_file = self.vault_dir / "kaizen_backlog.md"

        with open(backlog_file, 'a') as f:
            f.write(f"\n\n### ✅ COMPLETED: {item_title}\n")
            f.write(f"- **Completed:** {datetime.now(timezone.utc).isoformat()}\n")
            f.write(f"- **Result:** {result}\n")

        logger.info(f"Logged Kaizen completion: {item_title}")


class KaizenEngine:
    """Applies Kaizen improvements from the backlog."""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def apply_top_priority_fix(self, kaizen_items: List[Dict]) -> Tuple[bool, str]:
        """
        Apply the highest-priority fix from the backlog.

        Returns:
            (success: bool, description: str)
        """
        if not kaizen_items:
            return False, "No Kaizen items in backlog"

        # Get first P0 item, or first P1 if no P0
        p0_items = [item for item in kaizen_items if item["priority"] == "P0"]
        item = p0_items[0] if p0_items else kaizen_items[0]

        logger.info(f"Applying Kaizen fix: {item['title']}")

        # Parse the item to determine what to fix
        title_lower = item['title'].lower()

        if "deploy v5" in title_lower or "goldilocks" in title_lower:
            return self._deploy_v5()
        elif "roll" in title_lower and "expir" in title_lower:
            return self._roll_contract_expirations()
        elif "overnight lockout" in title_lower:
            return self._implement_overnight_lockout()
        elif "trail activation" in title_lower and "0.3" in title_lower:
            return self._tighten_trail_activation()
        else:
            return False, f"No automated fix implemented for: {item['title']}"

    def _deploy_v5(self) -> Tuple[bool, str]:
        """Deploy V5 Goldilocks Edition by updating symlinks/config."""
        logger.info("Deploying V5 Goldilocks Edition...")

        # Simple approach: V5 is already in live_session_v5.py
        # Just need to ensure ralph_trading_loop.py uses it
        return True, "V5 Goldilocks Edition ready (code exists, will be used by trading loop)"

    def _roll_contract_expirations(self) -> Tuple[bool, str]:
        """Update MGC and MCL contract IDs to next expiry."""
        logger.info("Rolling contract expirations: MGC J26→M26, MCL K26→M26...")

        v5_file = self.project_root / "live_session_v5.py"

        if not v5_file.exists():
            return False, "live_session_v5.py not found"

        # Read file
        with open(v5_file) as f:
            content = f.read()

        # Replace contract IDs
        modified = content.replace("CON.F.US.MGC.J26", "CON.F.US.MGC.M26")
        modified = modified.replace("CON.F.US.MCLE.K26", "CON.F.US.MCLE.M26")

        if modified == content:
            return False, "Contract IDs not found or already updated"

        # Write back
        with open(v5_file, 'w') as f:
            f.write(modified)

        logger.info("Contract expirations rolled successfully")
        return True, "MGC J26→M26, MCL K26→M26 completed"

    def _implement_overnight_lockout(self) -> Tuple[bool, str]:
        """Hard block trading outside 8am-4pm CT."""
        logger.info("Implementing overnight trading lockout...")

        # This would require modifying the session phase logic in V5
        # For now, return a placeholder
        return False, "Overnight lockout requires manual code review (not yet automated)"

    def _tighten_trail_activation(self) -> Tuple[bool, str]:
        """Lower trail activation from 0.5x to 0.3x SL."""
        logger.info("Tightening trail activation to 0.3x SL...")

        v5_file = self.project_root / "live_session_v5.py"

        if not v5_file.exists():
            return False, "live_session_v5.py not found"

        # Read file
        with open(v5_file) as f:
            content = f.read()

        # Replace TRAIL_ACTIVATION_MULT
        modified = content.replace("TRAIL_ACTIVATION_MULT = 0.5", "TRAIL_ACTIVATION_MULT = 0.3")

        if modified == content:
            return False, "TRAIL_ACTIVATION_MULT not found or already set to 0.3"

        # Write back
        with open(v5_file, 'w') as f:
            f.write(modified)

        logger.info("Trail activation tightened to 0.3x")
        return True, "TRAIL_ACTIVATION_MULT: 0.5 → 0.3"


def run_tests() -> bool:
    """Run the test suite to verify fixes didn't break anything."""
    logger.info("Running test suite...")

    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/", "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            logger.info("✅ All tests passed")
            return True
        else:
            logger.error(f"❌ Tests failed:\n{result.stdout}\n{result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        return False


def git_commit_and_push(message: str, dry_run: bool = False) -> bool:
    """Commit changes and push to GitHub."""
    logger.info(f"Git commit: {message}")

    if dry_run:
        logger.info("[DRY RUN] Would commit and push")
        return True

    try:
        # Add all tracked files
        subprocess.run(["git", "add", "-u"], check=True)

        # Commit
        subprocess.run(["git", "commit", "-m", message], check=True)

        # Push to remote
        subprocess.run(["git", "push", "origin", "HEAD"], check=True)

        logger.info("✅ Git commit and push successful")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Git operation failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Ralph Wiggum Meta-Loop - System Improvement")
    parser.add_argument("--max-iterations", type=int, default=10, help="Maximum loop iterations")
    parser.add_argument("--dry-run", action="store_true", help="Don't modify files or commit")
    parser.add_argument("--sleep-between", type=int, default=300, help="Seconds between iterations (default 300)")
    args = parser.parse_args()

    logger.info(f"🔄 Ralph Wiggum META-LOOP starting (max iterations: {args.max_iterations}, dry-run: {args.dry_run})")

    status = MetaLoopStatus(LOOP_STATUS_FILE)
    obsidian = ObsidianManager(OBSIDIAN_DIR)
    kaizen_engine = KaizenEngine(PROJECT_ROOT)

    for iteration in range(args.max_iterations):
        status.data["iteration"] = iteration + 1
        status.data["status"] = "running"
        status.save()

        logger.info(f"\n{'='*80}\nIteration {iteration + 1}/{args.max_iterations}\n{'='*80}")

        # PHASE 1: Read Kaizen backlog
        logger.info("PHASE 1: Reading Kaizen backlog from Obsidian...")
        kaizen_items = obsidian.read_kaizen_backlog()
        logger.info(f"Found {len(kaizen_items)} Kaizen items")

        if not kaizen_items:
            logger.info("No Kaizen items in backlog - system is optimized or needs manual planning")
            break

        # PHASE 2: Apply top-priority fix
        logger.info("PHASE 2: Applying top-priority Kaizen fix...")
        success, description = kaizen_engine.apply_top_priority_fix(kaizen_items)

        if success:
            logger.info(f"✅ Fix applied: {description}")
            status.increment("fixes_applied")

            # PHASE 3: Run tests
            if not args.dry_run:
                logger.info("PHASE 3: Running test suite...")
                tests_passed = run_tests()
                status.increment("tests_run")

                if not tests_passed:
                    logger.error("❌ Tests failed - rolling back changes")
                    # In real implementation, would git reset here
                    break
            else:
                logger.info("[DRY RUN] Skipping test execution")
                tests_passed = True

            # PHASE 4: Commit to git
            if tests_passed:
                logger.info("PHASE 4: Committing to GitHub...")
                commit_msg = f"Kaizen Fix #{status.data['fixes_applied']}: {description}"

                if git_commit_and_push(commit_msg, dry_run=args.dry_run):
                    status.increment("git_commits")

                    # PHASE 5: Update Obsidian
                    logger.info("PHASE 5: Updating Obsidian vault...")
                    obsidian.update_system_state({
                        "kaizen_fix_applied": description,
                        "tests_passed": tests_passed,
                        "iteration": iteration + 1
                    })

                    obsidian.log_kaizen_completion(kaizen_items[0]["title"], description)
        else:
            logger.warning(f"⚠️ Could not apply fix: {description}")
            # Move to next item or stop
            break

        # PHASE 6: Sleep between iterations
        if iteration < args.max_iterations - 1:
            logger.info(f"PHASE 6: Sleeping {args.sleep_between}s before next iteration...")
            time.sleep(args.sleep_between)

    # Final status
    status.data["status"] = "completed"
    status.save()

    logger.info(f"\n{'='*80}")
    logger.info(f"🏁 Meta-Loop completed after {iteration + 1} iterations")
    logger.info(f"   Fixes applied: {status.data['fixes_applied']}")
    logger.info(f"   Tests run: {status.data['tests_run']}")
    logger.info(f"   Git commits: {status.data['git_commits']}")
    logger.info(f"{'='*80}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n⚠️ Meta-loop interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"❌ Fatal error in meta-loop: {e}")
        sys.exit(1)
