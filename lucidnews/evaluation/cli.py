"""CLI: measure AI quality against hand annotations (``lucidnews-eval``).

Default: compare the analyses already stored in the archive (free, no AI call).
``--rerun``: re-analyze the annotated items with the current prompts and model
first (costs one AI call per item, more with retries), to measure a prompt change.
Each run saves a JSON report under ``<data_dir>/eval/reports/`` and shows the
change since the previous report of the same mode.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from .._cli import add_data_dir_arguments
from ..archive import ItemArchive
from ..storage.manager import StorageManager
from .service import EvaluationService
from .store import AnnotationStore

# (label, path in the report, higher is better)
HEADLINE = [
    ("Selection F1", ("selection", "f1"), True),
    ("Selection precision", ("selection", "precision"), True),
    ("Selection recall", ("selection", "recall"), True),
    ("Importance exact", ("importance", "exact"), True),
    ("Importance within one band", ("importance", "within_one"), True),
    ("Categories F1", ("categories", "f1"), True),
    ("Claim accuracy", ("claim", "accuracy"), True),
    ("Overconfident claims", ("claim", "overconfident"), False),
    ("Reliability agreement", ("reliability", "agreement"), True),
    ("False reliable", ("reliability", "false_reliable"), False),
]


def _get(report: Dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = report
    for key in path:
        value = value.get(key) if isinstance(value, dict) else None
    return value


def _fmt(value: Any, rate: bool) -> str:
    if value is None:
        return "–"
    return f"{value:.0%}" if rate else str(value)


def _model_name(config) -> str:
    provider = getattr(config.ai.provider, "value", config.ai.provider)
    return f"{provider}/{config.ai.model}"


def _previous_report(reports_dir: Path, mode: str) -> Optional[Dict[str, Any]]:
    candidates = sorted(reports_dir.glob(f"*-{mode}.json"))
    if not candidates:
        return None
    return json.loads(candidates[-1].read_text(encoding="utf-8"))


async def _rerun(service: EvaluationService, config, console: Console) -> Dict[str, Any]:
    from ..ai.analyzer import ContentAnalyzer
    from ..ai.client import create_ai_client
    from ..processing import ProfileRegistry

    annotations = service.store.load()
    items = service.archive.get_items(list(annotations))
    copies = []
    for item in items.values():
        copy = item.model_copy(deep=True)
        if copy.processing:
            # Keep the profile; drop what the analysis and reliability stages produce.
            copy.processing.analysis = None
            copy.processing.reliability = None
        copies.append(copy)
    console.print(f"Re-analyzing {len(copies)} annotated item(s) with {_model_name(config)}…")
    profiles = ProfileRegistry.load(Path(config.processing.profiles_dir), config.processing.default_profile)
    analyzer = ContentAnalyzer(create_ai_client(config.ai), profiles, console=console, reliability_policy=service.policy, sector=config.sector)
    await analyzer.analyze_batch(copies)
    return service.report({copy.id: copy for copy in copies})


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="LucidNews quality evaluation against hand annotations")
    parser.add_argument("--rerun", action="store_true", help="Re-analyze annotated items with the current prompts (AI calls)")
    parser.add_argument("--json", action="store_true", help="Print the full JSON report")
    parser.add_argument("--no-save", action="store_true", help="Do not write the report file")
    add_data_dir_arguments(parser)
    args = parser.parse_args(argv)
    console = Console(stderr=args.json)
    load_dotenv()

    storage = StorageManager(data_dir=args.data_dir, config_path=args.config)
    config = storage.load_config()
    archive_path = Path(config.archive.path)
    if not archive_path.is_absolute():
        archive_path = Path(args.data_dir) / archive_path
    if not archive_path.exists():
        console.print(f"[yellow]No archive at {archive_path}. Run `uv run lucidnews` first.[/yellow]")
        return 1
    eval_dir = Path(args.data_dir) / "eval"
    store = AnnotationStore(eval_dir / "annotations.json")
    if not store.load():
        console.print(
            "[yellow]No annotation yet. Annotate items in the web app (Quality screen) "
            f"or in {store.path}.[/yellow]"
        )
        return 1
    service = EvaluationService.from_config(config, ItemArchive(archive_path), store)

    mode = "rerun" if args.rerun else "stored"
    report = asyncio.run(_rerun(service, config, console)) if args.rerun else service.report()
    report["mode"] = mode
    report["model"] = _model_name(config)
    report["created_at"] = datetime.now(timezone.utc).isoformat()

    reports_dir = eval_dir / "reports"
    previous = _previous_report(reports_dir, mode)
    if not args.no_save:
        reports_dir.mkdir(parents=True, exist_ok=True)
        path = reports_dir / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{mode}.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    table = Table(title=f"Quality — {report['compared']} item(s) compared ({mode}, {report['model']})")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_column("Previous", justify="right")
    table.add_column("Change", justify="right")
    for label, path_keys, higher_better in HEADLINE:
        rate = path_keys[-1] not in ("overconfident", "false_reliable")
        value, before = _get(report, path_keys), _get(previous, path_keys) if previous else None
        change = ""
        if isinstance(value, (int, float)) and isinstance(before, (int, float)) and value != before:
            better = (value > before) == higher_better
            delta = f"{value - before:+.0%}" if rate else f"{value - before:+d}"
            change = f"[{'green' if better else 'red'}]{delta}[/]"
        table.add_row(label, _fmt(value, rate), _fmt(before, rate), change)
    console.print(table)

    if report["reliability"]["false_reliable"]:
        console.print("[bold red]False reliable[/] (shown as confirmed/reliable, human says unverified/rumor):")
        for item in report["items"]:
            if "false_reliable" in item["issues"]:
                console.print(f"  - {item['title']} [dim]({item['item_id']})[/dim]")
    if report["missing"]:
        console.print(f"[yellow]{len(report['missing'])} annotated item(s) not in this archive or not analyzed.[/yellow]")
    if report["small_sample"]:
        console.print(f"[dim]Fewer than 30 items compared: read these rates as indicative only.[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
