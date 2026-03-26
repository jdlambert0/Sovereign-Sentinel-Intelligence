"""
Problem Tracker — Obsidian-Compatible Issue Tracking

Discovers problems during live trading and writes them to
Obsidian-compatible markdown files in the obsidian/ directory.

Categories:
  - data_quality: Missing/stale/incorrect market data
  - execution: Order placement/fill issues
  - ai_quality: Bad AI decisions, low-quality thesis
  - risk: Risk limit breaches, unexpected position sizing
  - infrastructure: Crashes, connection drops, memory issues
  - performance: Degraded win rate, bad market selection
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any

import pytz


@dataclass
class Problem:
    """A tracked problem discovered during operation."""
    id: str
    category: str
    severity: str  # "critical", "warning", "info"
    title: str
    description: str
    timestamp: float
    context: Dict[str, Any] = field(default_factory=dict)
    resolution: str = ""
    resolved: bool = False
    recurrence_count: int = 1


class ProblemTracker:
    """
    Tracks problems encountered during trading for Obsidian integration.

    Writes problems as markdown notes, maintains a running log, and
    provides a summary dashboard that can be copied to Obsidian.
    """

    def __init__(self, state_dir: str = "state", obsidian_dir: str = "obsidian"):
        self.state_dir = state_dir
        self.obsidian_dir = obsidian_dir
        self.logger = logging.getLogger("sovran.problems")
        self._problems: List[Problem] = []
        self._problem_counts: Dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        """Load existing problems from state."""
        path = os.path.join(self.state_dir, "problems.json")
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                self._problems = [
                    Problem(**p) for p in data
                ]
            except Exception as e:
                self.logger.warning(f"Failed to load problems: {e}")

    def _save(self) -> None:
        """Persist problems to state."""
        os.makedirs(self.state_dir, exist_ok=True)
        path = os.path.join(self.state_dir, "problems.json")
        data = [
            {
                "id": p.id,
                "category": p.category,
                "severity": p.severity,
                "title": p.title,
                "description": p.description,
                "timestamp": p.timestamp,
                "context": p.context,
                "resolution": p.resolution,
                "resolved": p.resolved,
                "recurrence_count": p.recurrence_count,
            }
            for p in self._problems
        ]
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)

    def track(
        self,
        category: str,
        severity: str,
        title: str,
        description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Problem:
        """Track a new problem or increment recurrence of existing one."""
        # Check for duplicate (same category + title)
        for existing in self._problems:
            if existing.category == category and existing.title == title and not existing.resolved:
                existing.recurrence_count += 1
                existing.timestamp = time.time()  # Update to latest occurrence
                if context:
                    existing.context.update(context)
                self._save()
                self.logger.info(
                    f"Problem recurrence #{existing.recurrence_count}: [{category}] {title}"
                )
                return existing

        # New problem
        problem = Problem(
            id=f"P{int(time.time())}-{len(self._problems)}",
            category=category,
            severity=severity,
            title=title,
            description=description,
            timestamp=time.time(),
            context=context or {},
        )
        self._problems.append(problem)
        self._save()
        self.logger.warning(f"NEW PROBLEM: [{severity}] [{category}] {title}")
        return problem

    def resolve(self, problem_id: str, resolution: str) -> None:
        """Mark a problem as resolved."""
        for p in self._problems:
            if p.id == problem_id:
                p.resolved = True
                p.resolution = resolution
                self._save()
                self.logger.info(f"Problem resolved: {problem_id} — {resolution}")
                return

    def get_active_problems(self) -> List[Problem]:
        """Get all unresolved problems."""
        return [p for p in self._problems if not p.resolved]

    def get_critical_problems(self) -> List[Problem]:
        """Get unresolved critical problems."""
        return [p for p in self._problems if not p.resolved and p.severity == "critical"]

    def write_obsidian_dashboard(self) -> str:
        """Write problem dashboard as Obsidian-compatible markdown.

        Returns the file path of the written dashboard.
        """
        os.makedirs(self.obsidian_dir, exist_ok=True)
        ct = pytz.timezone("US/Central")
        now = datetime.now(ct)
        path = os.path.join(self.obsidian_dir, "problem_tracker.md")

        lines = [
            "---",
            "tags: [sovran, problems, tracker]",
            f"updated: {now.strftime('%Y-%m-%d %H:%M CT')}",
            "---",
            "",
            "# 🔴 Sovran Problem Tracker",
            "",
            f"*Last updated: {now.strftime('%Y-%m-%d %H:%M CT')}*",
            "",
        ]

        active = self.get_active_problems()
        resolved = [p for p in self._problems if p.resolved]

        # Summary
        lines.append(f"## Summary")
        lines.append(f"- **Active:** {len(active)}")
        lines.append(f"- **Resolved:** {len(resolved)}")
        lines.append(f"- **Total tracked:** {len(self._problems)}")
        lines.append("")

        # Active problems
        if active:
            lines.append("## 🔴 Active Problems")
            lines.append("")
            for p in sorted(active, key=lambda x: (
                {"critical": 0, "warning": 1, "info": 2}.get(x.severity, 3),
                -x.recurrence_count
            )):
                severity_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(
                    p.severity, "⚪"
                )
                dt = datetime.fromtimestamp(p.timestamp, tz=ct)
                lines.append(f"### {severity_icon} {p.title}")
                lines.append(f"- **Category:** `{p.category}`")
                lines.append(f"- **Severity:** {p.severity}")
                lines.append(f"- **First seen:** {dt.strftime('%Y-%m-%d %H:%M CT')}")
                lines.append(f"- **Recurrences:** {p.recurrence_count}")
                lines.append(f"- **Description:** {p.description}")
                if p.context:
                    lines.append(f"- **Context:** `{json.dumps(p.context, default=str)[:200]}`")
                lines.append("")
        else:
            lines.append("## ✅ No Active Problems")
            lines.append("")

        # Recently resolved
        if resolved:
            lines.append("## ✅ Recently Resolved")
            lines.append("")
            for p in resolved[-10:]:  # Last 10
                dt = datetime.fromtimestamp(p.timestamp, tz=ct)
                lines.append(f"- ~~{p.title}~~ — *{p.resolution}* ({dt.strftime('%m/%d')})")
            lines.append("")

        # Category breakdown
        cat_counts: Dict[str, int] = {}
        for p in active:
            cat_counts[p.category] = cat_counts.get(p.category, 0) + 1
        if cat_counts:
            lines.append("## By Category")
            for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
                lines.append(f"- `{cat}`: {count} active")
            lines.append("")

        content = "\n".join(lines)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def write_obsidian_daily_log(self, perf_summary: Optional[str] = None) -> str:
        """Write a daily trading log entry for Obsidian.

        Returns the file path of the written log.
        """
        os.makedirs(self.obsidian_dir, exist_ok=True)
        ct = pytz.timezone("US/Central")
        now = datetime.now(ct)
        date_str = now.strftime("%Y-%m-%d")
        path = os.path.join(self.obsidian_dir, f"daily_log_{date_str}.md")

        lines = [
            "---",
            f"tags: [sovran, daily-log, {date_str}]",
            f"date: {date_str}",
            "---",
            "",
            f"# 📊 Sovran Daily Log — {now.strftime('%A, %B %d, %Y')}",
            "",
        ]

        # Active problems
        active = self.get_active_problems()
        if active:
            lines.append(f"## Problems ({len(active)} active)")
            for p in active:
                icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(p.severity, "⚪")
                lines.append(f"- {icon} `{p.category}`: {p.title} (x{p.recurrence_count})")
            lines.append("")

        # Performance summary (if provided)
        if perf_summary:
            lines.append("## Performance")
            lines.append(perf_summary)
            lines.append("")

        lines.append("---")
        lines.append(f"*Generated at {now.strftime('%H:%M CT')}*")

        content = "\n".join(lines)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path
