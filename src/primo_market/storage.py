from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any


def write_jsonl_gzip(rows: list[dict[str, Any]], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(target, "wt", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), default=str))
            stream.write("\n")
    return target


def save_execution(bundle: dict[str, Any], output_dir: str | Path) -> Path:
    root = Path(output_dir) / f"execution_date={bundle['started_at'][:10]}" / f"execution_id={bundle['execution_id']}"
    write_jsonl_gzip(bundle["events"], root / "raw_api_responses.jsonl.gz")
    write_jsonl_gzip(bundle["item_execution"], root / "item_execution.jsonl.gz")
    manifest = {
        "execution_id": bundle["execution_id"],
        "started_at": bundle["started_at"],
        "finished_at": bundle["finished_at"],
        "status": bundle["status"],
        "response_count": len(bundle["events"]),
        "item_count": len(bundle["item_execution"]),
        "order_response_count": sum(1 for e in bundle["events"] if e["event_type"] == "orders"),
        "total_orders": sum(x["order_count"] or 0 for x in bundle["item_execution"]),
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return root
