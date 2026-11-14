"""
SentinelAI — Suricata EVE ingester (v2).

Reads a Suricata EVE JSON log stream and feeds the API:
- `alert` records  -> POST /incidents/      (detections, AI-analysed)
- flow/dns/http/tls/ssh records -> POST /ingest/observations
  (traffic context: feeds the asset inventory, never creates incidents)

Usage:
    python ingest.py <eve.json> [--url http://127.0.0.1:8000] [--once]

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

ALERT_EVENT_TYPES = {"alert"}

# Event types that represent traffic context, not threats.
OBSERVATION_EVENT_TYPES = {"flow", "dns", "http", "tls", "ssh"}

OBSERVATION_BATCH = 25


class Stats:
    def __init__(self):
        self.alerts = 0
        self.observations = 0
        self.ignored = 0
        self.errors = 0

    def summary(self):
        return (
            f"sessão: {self.alerts} alertas submetidos, "
            f"{self.observations} observações de tráfego, "
            f"{self.ignored} registos ignorados, {self.errors} erros"
        )


def map_eve_record(record: dict) -> dict | None:
    """
    Convert an EVE alert record to an incident payload.
    Returns None when the record is not an actionable alert.
    """
    if record.get("event_type") not in ALERT_EVENT_TYPES:
        return None

    alert = record.get("alert", {})

    src_ip = record.get("src_ip") or record.get("src_addr")
    if not src_ip:
        return None

    payload = {
        "source_ip": src_ip,
        "destination_ip": record.get("dest_ip"),
        "source_port": record.get("src_port"),
        "destination_port": record.get("dest_port"),
        "protocol": record.get("proto"),
        "event_type": alert.get("signature_id") and (
            f"SID_{alert['signature_id']}"
        ) or "UNKNOWN_ALERT",
        "severity": SEVERITY_MAP.get(alert.get("severity"), "LOW"),
        "description": alert.get("signature")
        or "Suricata alert without signature",
    }

    return payload


def extract_observations(record: dict) -> list[dict]:
    """Traffic context records -> asset observations (no incidents)."""
    if record.get("event_type") not in OBSERVATION_EVENT_TYPES:
        return []

    seen = []
    for key in ("src_ip", "dest_ip"):
        ip = record.get(key)
        if ip:
            seen.append({"ip": ip})

    return seen


def post_json(api_url: str, path: str, payload) -> dict | None:
    request = urllib.request.Request(
        f"{api_url.rstrip('/')}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        print(
            f"[-] API devolveu {error.code} para {path}: {body}",
            file=sys.stderr,
        )

    except (urllib.error.URLError, OSError) as error:
        print(
            f"[-] não foi possível contactar a API {api_url}: {error}",
            file=sys.stderr,
        )

    return None


def submit_incident(api_url: str, incident: dict, stats: Stats) -> None:
    body = post_json(api_url, "/incidents/", incident)

    if body:
        stats.alerts += 1
        print(
            f"[+] incidente #{body.get('id')} submetido "
            f"({incident['event_type']})"
        )
    else:
        stats.errors += 1


def flush_observations(api_url: str, buffer: list, stats: Stats) -> None:
    if not buffer:
        return

    body = post_json(
        api_url,
        "/ingest/observations",
        [{"ip": item["ip"]} for item in buffer],
    )

    if body:
        stats.observations += body.get("observed", len(buffer))

    buffer.clear()


def ingest_file(path: str, api_url: str, follow: bool):
    """Read the file line by line; if follow=True, keep reading new lines (tail -F)."""
    stats = Stats()
    observation_buffer: list[dict] = []

    def flush():
        flush_observations(api_url, observation_buffer, stats)

    with open(path, "r", encoding="utf-8") as log_file:
        if follow:
            log_file.seek(0, 2)  # tail -F: only new records

        try:
            while True:
                line = log_file.readline()

                if not line:
                    if follow:
                        flush()
                        time.sleep(0.5)
                        continue
                    break

                if not line.strip().startswith("{"):
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                event_type = record.get("event_type")

                incident = map_eve_record(record)
                if incident:
                    submit_incident(api_url, incident, stats)
                    continue

                if event_type in OBSERVATION_EVENT_TYPES:
                    observation_buffer.extend(extract_observations(record))
                    if len(observation_buffer) >= OBSERVATION_BATCH:
                        flush()
                    continue

                stats.ignored += 1

        except KeyboardInterrupt:
            print("\ninterrompido")

    flush()

    print(stats.summary())


def main():
    parser = argparse.ArgumentParser(
        description="Ingester de logs EVE do Suricata para a SentinelAI"
    )

    parser.add_argument(
        "eve_file",
        help="ficheiro de log EVE JSON do Suricata"
    )

    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
        help="URL base da API SentinelAI (default: %(default)s)"
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="processar os registos existentes no ficheiro e sair"
    )

    args = parser.parse_args()

    ingest_file(
        args.eve_file,
        args.url,
        follow=not args.once
    )


if __name__ == "__main__":
    main()
