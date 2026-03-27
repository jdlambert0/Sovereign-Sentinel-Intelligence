"""
Bulk-load all Sovran V2 knowledge into TrustGraph.

Loads:
1. All Obsidian vault files (system knowledge, handoffs, philosophy)
2. All research files (gambling theory, probability models)
3. Trading rules and philosophy

Run once after TrustGraph deployment, then incrementally.

Usage:
    cd C:\\KAI\\sovran_v2
    python scripts/trustgraph_loader.py
"""
import glob
import os
import sys
import time

# Add parent dir to path so we can import src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.trustgraph_client import TrustGraphClient


def main():
    tg = TrustGraphClient()

    if not tg.is_available():
        print("[ERROR] TrustGraph is not running!")
        print("  Start it with: docker-compose up -d")
        print(f"  Expected at: {tg.base_url}")
        sys.exit(1)

    loaded = 0
    failed = 0

    # 1. Obsidian vault -- primary knowledge
    print("=== Loading Obsidian Vault ===")
    obsidian_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "obsidian")
    for path in sorted(glob.glob(os.path.join(obsidian_dir, "*.md"))):
        name = os.path.basename(path)
        print(f"  Loading {name}...", end=" ", flush=True)
        if tg.ingest_file(path):
            print("OK")
            loaded += 1
        else:
            print("FAILED")
            failed += 1
        time.sleep(0.5)  # Rate limit

    # 2. Research files (local machine paths)
    research_dirs = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "_research"),
        r"C:\KAI\_research",
    ]
    for research_dir in research_dirs:
        if os.path.isdir(research_dir):
            print(f"\n=== Loading Research from {research_dir} ===")
            for path in sorted(glob.glob(os.path.join(research_dir, "**", "*.md"), recursive=True)):
                name = os.path.relpath(path, research_dir)
                print(f"  Loading {name}...", end=" ", flush=True)
                if tg.ingest_file(path):
                    print("OK")
                    loaded += 1
                else:
                    print("FAILED")
                    failed += 1
                time.sleep(0.5)

    # 3. Trading rules and config
    config_files = [
        "trading_rules.md",
        "ai_trading_philosophy.md",
        "probability_trading_strategy.md",
    ]
    for fname in config_files:
        path = os.path.join(obsidian_dir, fname)
        if os.path.exists(path) and path not in glob.glob(os.path.join(obsidian_dir, "*.md")):
            # Already loaded above, skip
            pass

    print(f"\n{'='*50}")
    print(f"Done: {loaded} loaded, {failed} failed")
    print(f"{'='*50}")
    print(f"\nVerify at: http://localhost:8888 (Workbench)")
    print("  -> Graph Visualizer to see entity relationships")
    print("  -> Vector Search to test queries")


if __name__ == "__main__":
    main()
