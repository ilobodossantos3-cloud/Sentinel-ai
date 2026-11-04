"""
SentinelAI — Suricata EVE ingester.

Reads a Suricata EVE JSON log stream, converts alerts
into SentinelAI incidents and POSTs them to the API.

Usage:
    python ingest.py <eve.json> [--url http://127.0.0.1:8000] [--once]

Follow the live log continuously (default):
    python ingest.py /var/log/suricata/eve.json

Process only existing records and exit (for tests):
    python ingest.py eve.sample.json --once

Requires no third-party packages (stdlib only).
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request


# Suricata severity (1..4) -> SentinelAI severity
SEVERITY_MAP = {
    1: "CRITICAL",
    2: "HIGH",
    3: "MEDIUM",
    4: "LOW",
}

# Events that do not describe a threat are ignored
ALERT_EVENT_TYPES = {"alert"}


def map_eve_record(record: dict) -> dict | None:
    """
    Convert an EVE record to an incident payload.
    Returns None when the record is not an actionable alert.
    """
    if record.get("event_type") not in ALERT_EVENT_TYPES:
        return None

    alert = record.get("alert", {})

    src_ip = record.get("src_ip") or record.get("src_addr")
    if not src_ip:
        return None

    severity_id = alert.get("severity")

    payload = {
        "source_ip": src_ip,
        "destination_ip": record.get("dest_ip"),
        "source_port": record.get("src_port"),
        "destination_port": record.get("dest_port"),
        "protocol": record.get("proto"),
        "event_type": alert.get("signature_id") and (
            f"SID_{alert['signature_id']}"
        ) or "UNKNOWN_ALERT",
        "severity": SEVERITY_MAP.get(severity_id, "LOW"),
        "description": alert.get("signature")
        or "Suricata alert without signature",
    }

    return payload


def post_incident(api_url: str, incident: dict) -> bool:
    endpoint = f"{api_url.rstrip('/')}/incidents/"

    data = json.dumps(incident).encode("utf-8")

    request = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))
            print(
                f"[+] incident #{body.get('id')} submitted "
                f"({incident['event_type']})"
            )
            return True

    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        print(
            f"[-] API returned {error.code} for "
            f"{incident['event_type']}: {body}",
            file=sys.stderr,
        )

    except (urllib.error.URLError, OSError) as error:
        print(
            f"[-] could not reach API {api_url}: {error}",
            file=sys.stderr,
        )

    return False


def is_json_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("{")


def ingest_file(path: str, api_url: str, follow: bool):
    """Read the file line by line; if follow=True, keep reading new lines (tail -f)."""

    with open(path, "r", encoding="utf-8") as log_file:
        if follow:
            log_file.seek(0, 2)  # tail -F: only new records

        while True:
            line = log_file.readline()

            if line:
                if not is_json_line(line):
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                incident = map_eve_record(record)

                if incident:
                    post_incident(api_url, incident)

            elif follow:
                time.sleep(0.5)

            else:
                break


def main():
    parser = argparse.ArgumentParser(
        description="Streaming ingester of Suricata EVE logs for SentinelAI"
    )

    parser.add_argument(
        "eve_file",
        help="Suricata EVE JSON log file"
    )

    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
        help="SentinelAI API base URL (default: %(default)s)"
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="process the current contents of the file and exit"
    )

    args = parser.parse_args()

    try:
        ingest_file(
            args.eve_file,
            args.url,
            follow=not args.once
        )
    except KeyboardInterrupt:
        print("\ninterrupted")


if __name__ == "__main__":
    main()
