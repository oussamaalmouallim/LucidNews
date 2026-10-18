"""First start of a server (``lucidnews-init``): the data directory a service can start from.

Run before every start by the compose file, so a blank server needs one command. It only ever
*creates*: an existing configuration, archive or account is never touched.

- ``config.json``: copied from ``data/config.example.json`` with accounts on and sign-up closed
  (a server is never open without them), and the reverse proxy named in ``server.trusted_proxies``
  from ``LUCIDNEWS_TRUSTED_PROXIES`` (comma-separated IP addresses).
- ``archive.sqlite3``: empty, so the API starts before the first run.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from ._cli import add_data_dir_arguments
from .archive import ItemArchive
from .models import ServerConfig

EXAMPLE = Path(__file__).resolve().parent.parent / "data" / "config.example.json"


def initialise(data_dir: Path, config_path: Optional[Path] = None, trusted_proxies: Optional[List[str]] = None) -> List[str]:
    """Create what is missing; return what was created."""
    created: List[str] = []
    data_dir.mkdir(parents=True, exist_ok=True)
    config = config_path or data_dir / "config.json"
    if not config.exists():
        values = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        values["auth"] = {"enabled": True, "allow_signup": False}
        values["server"] = ServerConfig(trusted_proxies=trusted_proxies or []).model_dump()  # a bad address stops here
        config.write_text(json.dumps(values, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        created.append(config.name)
    archive = data_dir / "archive.sqlite3"
    if not archive.exists():
        ItemArchive(archive)
        created.append(archive.name)
    return created


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Create the configuration and the empty archive of a new server")
    add_data_dir_arguments(parser)
    args = parser.parse_args(argv)
    proxies = [entry.strip() for entry in os.environ.get("LUCIDNEWS_TRUSTED_PROXIES", "").split(",") if entry.strip()]
    config = Path(args.config) if args.config else None
    try:
        created = initialise(Path(args.data_dir), config, proxies)
    except ValueError as exc:  # a malformed proxy address
        print(f"Cannot initialise: {exc}", file=sys.stderr)
        return 1
    print(f"LucidNews data directory ready ({'created ' + ', '.join(created) if created else 'nothing to create'}).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
