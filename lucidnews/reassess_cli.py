"""CLI: recompute the reliability labels of archived items (``lucidnews-reassess``).

After a trust registry change (new domains or accounts in the code or in
``reliability.domains`` / ``reliability.accounts``), past editions keep the labels
computed when they were published. This command recomputes them with the current
registry, without any AI call: the AI's claim status is kept as it was.

By default it only shows what would change; ``--apply`` writes the new labels.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from rich.console import Console
from rich.table import Table

from ._cli import add_data_dir_arguments
from .archive import ItemArchive
from .reliability import ReliabilityLabel
from .reliability.assess import ReliabilityPolicy, assess_item
from .storage.manager import StorageManager

_ORDER = [label.value for label in ReliabilityLabel]


def reassess(archive: ItemArchive, policy: ReliabilityPolicy) -> tuple[list, Counter, Counter]:
    """Return (changes, labels before, labels after); changes are (item, old label)."""
    before: Counter = Counter()
    after: Counter = Counter()
    changes = []
    for item in archive.all_items():
        processing = item.processing
        if processing is None or (processing.analysis is None and not processing.ai_skipped):
            continue
        old = processing.reliability
        new = assess_item(item, policy)
        before[old.label.value if old else "none"] += 1
        after[new.label.value] += 1
        if old is None or old.model_dump() != new.model_dump():
            processing.reliability = new
            changes.append((item, old.label.value if old else "none"))
    return changes, before, after


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Recompute archived reliability labels with the current trust registry (no AI call)"
    )
    parser.add_argument("--apply", action="store_true", help="Write the new labels (default: preview only)")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a table")
    add_data_dir_arguments(parser)
    args = parser.parse_args(argv)
    console = Console()

    config = StorageManager(data_dir=args.data_dir, config_path=args.config).load_config()
    archive_path = Path(config.archive.path)
    if not archive_path.is_absolute():
        archive_path = Path(args.data_dir) / archive_path
    if not archive_path.exists():
        console.print(f"[yellow]No archive at {archive_path}. Run `uv run lucidnews` first.[/yellow]")
        return 1

    archive = ItemArchive(archive_path)
    policy = ReliabilityPolicy.for_config(config)
    changes, before, after = reassess(archive, policy)
    written = archive.update_reliability(item for item, _ in changes) if args.apply else 0

    if args.json:
        print(
            json.dumps(
                {
                    "applied": args.apply,
                    "before": dict(before),
                    "after": dict(after),
                    "changed": [
                        {
                            "id": item.id,
                            "title": item.title,
                            "from": old,
                            "to": item.processing.reliability.label.value,
                        }
                        for item, old in changes
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    summary = Table(title="Labels in the archive")
    summary.add_column("Label")
    summary.add_column("Before", justify="right")
    summary.add_column("After", justify="right")
    for label in [*_ORDER, "none"]:
        if before[label] or after[label]:
            summary.add_row(label, str(before[label]), str(after[label]))
    console.print(summary)

    relabeled = [(item, old) for item, old in changes if old != item.processing.reliability.label.value]
    if relabeled:
        table = Table(title=f"{len(relabeled)} item(s) change label")
        table.add_column("Item")
        table.add_column("Before")
        table.add_column("After")
        for item, old in relabeled:
            table.add_row(item.title[:80], old, item.processing.reliability.label.value)
        console.print(table)
    detail_only = len(changes) - len(relabeled)
    if detail_only:
        console.print(f"[dim]{detail_only} other item(s) keep their label; only the tier or reasons change.[/dim]")

    if not changes:
        console.print("[green]Every archived label already matches the current registry.[/green]")
    elif args.apply:
        console.print(f"[green]Updated {written} item(s) in the archive.[/green]")
    else:
        console.print("[yellow]Preview only. Run again with --apply to write these labels.[/yellow]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
