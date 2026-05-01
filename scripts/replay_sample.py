from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    api_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    sample_path = Path(__file__).resolve().parents[1] / "data" / "sample_signals.json"
    signals = json.loads(sample_path.read_text(encoding="utf-8"))
    observed_at = datetime.now(timezone.utc).isoformat()
    expanded = []
    for signal in signals:
        repeats = 100 if signal["component_id"] == "RDBMS_PRIMARY" else 10
        for index in range(repeats):
            item = dict(signal)
            item["observed_at"] = observed_at
            item["payload"] = {**signal.get("payload", {}), "sample_index": index}
            expanded.append(item)

    request = urllib.request.Request(
        f"{api_url}/signals/batch",
        data=json.dumps(expanded).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        print(response.read().decode("utf-8"))


if __name__ == "__main__":
    main()
