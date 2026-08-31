"""Trigger Commercia's authenticated scheduler endpoint from Render Cron."""

import json
import os
import sys
import urllib.error
import urllib.request


def main():
    base_url = os.environ["SCHEDULER_URL"].rstrip("/")
    token = os.environ["SCHEDULER_TOKEN"]
    request = urllib.request.Request(
        f"{base_url}/internal/scheduler/run",
        method="POST",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=55) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        print(f"Scheduler trigger failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
