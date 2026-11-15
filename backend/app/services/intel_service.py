"""
Real threat-intelligence feeds — free public sources, stdlib only.

All data comes from actual downloads. A feed that fails to fetch
is reported as failed; nothing is guessed or synthesized.

Feeds (all free, no API key):
- firehol_level1 : https://github.com/firehol/blocklist-ipsets
  (FireHOL level 1 — highly reputable aggregated blocklist, CIDRs)
- feodo_c2       : https://feodotracker.abuse.ch (botnet C2 IPs)
- tor_exit       : https://check.torproject.org (Tor exit nodes)
- ipsum          : https://github.com/stamparm/ipsum (aggregated;
                   only IPs reported by >= 3 sources to reduce noise)
"""
import ipaddress
import json
import time
import urllib.request
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.threat_intel import ThreatIntelEntry


FEEDS: dict[str, dict] = {
    "firehol_level1": {
        "url": "https://raw.githubusercontent.com/firehol/blocklist-ipsets/master/firehol_level1.netset",
        "category": "malicious",
        "kind": "netset",
    },
    "feodo_c2": {
        "url": "https://feodotracker.abuse.ch/downloads/ipblocklist.json",
        "category": "botnet_c2",
        "kind": "feodo_json",
    },
    "tor_exit": {
        "url": "https://check.torproject.org/torbulkexitlist",
        "category": "anonymity",
        "kind": "plain_list",
    },
    "ipsum": {
        "url": "https://raw.githubusercontent.com/stamparm/ipsum/master/ipsum.txt",
        "category": "suspicious",
        "kind": "ipsum",
    },
}

IPSUM_MIN_REPORTS = 3

FETCH_TIMEOUT = 30


def _is_ip(value: str) -> bool:
    parts = value.split(".")
    if len(parts) != 4:
        return False
    return all(
        part.isdigit() and 0 <= int(part) <= 255 for part in parts
    )


def _is_ip_or_cidr(value: str) -> bool:
    if "/" in value:
        try:
            ipaddress.ip_network(value, strict=False)
            return True
        except ValueError:
            return False
    return _is_ip(value)


def fetch_url(url: str) -> str:
    """Plain GET (stdlib). Kept module-level so tests can stub it."""
    with urllib.request.urlopen(url, timeout=FETCH_TIMEOUT) as response:
        return response.read(2_000_000).decode("utf-8", errors="replace")


def parse_feed(kind: str, content: str) -> list[str]:
    """Extract IPs from a feed body (format-specific parser)."""
    ips: list[str] = []

    if kind == "netset" or kind == "plain_list":
        for line in content.splitlines():
            token = line.strip().split()[0] if line.strip() else ""
            if not token or token[0] in "#;!/":
                continue
            if _is_ip_or_cidr(token):
                ips.append(token)

    elif kind == "feodo_json":
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return []
        if isinstance(data, list):
            ips = [
                item["ip_address"]
                for item in data
                if isinstance(item, dict) and item.get("ip_address")
            ]

    elif kind == "ipsum":
        for line in content.splitlines():
            parts = line.split()
            if len(parts) != 2:
                continue
            ip, reports = parts
            if _is_ip(ip) and reports.isdigit() and int(reports) >= IPSUM_MIN_REPORTS:
                ips.append(ip)

    # dedupe, keep order
    return list(dict.fromkeys(ips))


def refresh_feed(db: Session, source: str) -> dict:
    """Download one feed and replace its entries atomically."""
    feed = FEEDS[source]
    started = time.time()

    try:
        content = fetch_url(feed["url"])
    except Exception as exc:
        return {"source": source, "error": str(exc), "entries": 0}

    ips = parse_feed(feed["kind"], content)

    now = datetime.now(timezone.utc)

    # honest bookkeeping: replace this source's rows completely
    (
        db.query(ThreatIntelEntry)
        .filter(ThreatIntelEntry.source == source)
        .delete()
    )

    seen: set[str] = set()
    for ip in ips:
        if ip in seen:
            continue
        seen.add(ip)
        db.add(ThreatIntelEntry(
            ip=ip, source=source, category=feed["category"],
            first_seen=now, last_seen=now,
        ))

    db.commit()

    return {
        "source": source,
        "entries": len(seen),
        "seconds": round(time.time() - started, 2),
    }


def refresh_all_feeds(db: Session) -> list[dict]:
    return [refresh_feed(db, source) for source in FEEDS]


def run_intel_refresh(job_id: int):
    """Background worker with Job lifecycle (like audits/AI)."""
    from app.core.database import SessionLocal
    from app.models.job import Job
    from app.services import job_service

    db: Session = SessionLocal()

    try:
        job = db.get(Job, job_id)
        if not job:
            return

        job_service.mark_running(job)
        db.commit()

        results = refresh_all_feeds(db)

        failed = [r for r in results if r.get("error")]
        total = sum(r["entries"] for r in results)

        result_payload = {"feeds": results, "total_entries": total}

        if not failed:
            job_service.mark_completed(job, result=result_payload)
        elif total > 0:
            job_service.mark_partial(job, result=result_payload)
        else:
            job_service.mark_failed(
                job,
                error="; ".join(
                    f"{r['source']}: {r['error']}" for r in failed
                ),
            )

        db.commit()

    except Exception as exc:
        db.rollback()
        from app.models.job import Job
        job = db.get(Job, job_id)
        if job:
            job_service.mark_failed(job, error=str(exc))
            db.commit()
    finally:
        db.close()


def feeds_status(db: Session) -> list[dict]:
    entries = (
        db.query(
            ThreatIntelEntry.source,
            ThreatIntelEntry.category,
        )
        .distinct()
        .all()
    )
    from sqlalchemy import func

    counts = dict(
        db.query(
            ThreatIntelEntry.source,
            func.count(ThreatIntelEntry.id),
        )
        .group_by(ThreatIntelEntry.source)
        .all()
    )
    latest = dict(
        db.query(
            ThreatIntelEntry.source,
            func.max(ThreatIntelEntry.last_seen),
        )
        .group_by(ThreatIntelEntry.source)
        .all()
    )

    status = []
    for source, feed in FEEDS.items():
        row = next(
            (e for e in entries if e[0] == source), None
        )
        status.append({
            "source": source,
            "url": feed["url"],
            "category": feed["category"],
            "entries": counts.get(source, 0),
            "last_refresh": (
                latest.get(source).isoformat()
                if latest.get(source) is not None else None
            ),
            "empty": row is None,
        })

    return status


def match_ips(db: Session, ips: list[str]) -> list[ThreatIntelEntry]:
    """Match a list of IPs against all stored feeds.

    Exact IPs match via SQL; CIDR entries match by network
    containment (ipaddress module).
    """
    clean = [ip for ip in ips if ip]

    if not clean:
        return []

    exact = (
        db.query(ThreatIntelEntry)
        .filter(ThreatIntelEntry.ip.in_(clean))
        .all()
    )

    matched_values = {e.ip for e in exact}

    # candidate IPs (v4 only supported by the v4 feeds)
    candidate_addrs = []
    for ip in clean:
        try:
            candidate_addrs.append(ipaddress.ip_address(ip))
        except ValueError:
            continue

    cidr_rows = (
        db.query(ThreatIntelEntry)
        .filter(ThreatIntelEntry.ip.contains("/"))
        .all()
    )

    cidr_matches = []
    for row in cidr_rows:
        if row.ip in matched_values:
            continue
        try:
            network = ipaddress.ip_network(row.ip, strict=False)
        except ValueError:
            continue
        if any(candidate in network for candidate in candidate_addrs):
            cidr_matches.append(row)

    return exact + cidr_matches


def incident_intel(db: Session, incident) -> list[dict]:
    """Derived on read: feed entries matching this incident's IPs."""
    entries = match_ips(
        db,
        [incident.source_ip, incident.destination_ip],
    )

    return [
        {
            "ip": entry.ip,
            "source": entry.source,
            "category": entry.category,
            "last_seen": entry.last_seen.isoformat(),
        }
        for entry in entries
    ]
