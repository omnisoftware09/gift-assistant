"""Background scheduler for proactive calendar alerts."""

import os
import threading
import time


def start_proactive_worker(client, interval_hours: float | None = None) -> None:
    """Start a daemon thread that checks for approaching events."""
    from src.workers.event_monitor_job import run_proactive_check

    if os.getenv("PROACTIVE_ALERTS_ENABLED", "true").lower() != "true":
        print("Proactive alerts disabled (PROACTIVE_ALERTS_ENABLED=false)")
        return

    hours = interval_hours or float(os.getenv("PROACTIVE_CHECK_INTERVAL_HOURS", "6"))

    def _loop():
        time.sleep(10)
        while True:
            try:
                result = run_proactive_check(client)
                if result.get("message"):
                    print(f"PROACTIVE: {result['message']}")
            except Exception as exc:
                print(f"PROACTIVE worker error: {exc}")
            time.sleep(hours * 3600)

    thread = threading.Thread(target=_loop, daemon=True, name="proactive-alerts")
    thread.start()
    print(f"Proactive alert worker started (every {hours}h)")
