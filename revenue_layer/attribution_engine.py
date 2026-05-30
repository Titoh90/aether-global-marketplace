#!/usr/bin/env python3
"""
attribution_engine.py — Deterministic click → conversion matching.

Model: LAST-CLICK attribution (v1, only supported model)

Rules:
  1. For each ConversionEvent (product_id + timestamp):
     - Find all ClickEvents for the same product_id
     - Restrict to clicks that occurred BEFORE the conversion timestamp
     - Restrict to clicks within window_days of the conversion (per-product policy)
     - Select the MOST RECENT qualifying click (last-click)
     - Tie-breaker (FIX 6): (1) closest timestamp, (2) same platform, (3) oldest click_id α
  2. If no matching click → explicit UnattributedRecord with reason_code (FIX 4)
  3. No probabilistic matching, no partial credit, no AI inference

Attribution window: per-product via attribution_policy (default 7 days). (FIX 3)

ZERO AI calls. ZERO mutation of source data.
Writes AttributionRecords to logs/revenue/attributions/YYYY-MM-DD.jsonl.
Writes UnattributedRecords to logs/revenue/unattributed/YYYY-MM-DD.jsonl. (FIX 4)
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys
import threading
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from revenue_layer.schemas import AttributionRecord, ClickEvent, ConversionEvent, ReasonCode, UnattributedRecord
from revenue_layer.click_tracker import get_clicks_for_product
from revenue_layer.conversion_ingestor import get_all_conversions, get_conversions_for_product
from revenue_layer.attribution_policy import get_policy

_ATTRIBUTIONS_DIR   = _IMPERIO_ROOT / "logs" / "revenue" / "attributions"
_UNATTRIBUTED_DIR   = _IMPERIO_ROOT / "logs" / "revenue" / "unattributed"
_ATTRIBUTIONS_DIR.mkdir(parents=True, exist_ok=True)
_UNATTRIBUTED_DIR.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()

# Env override still supported — but per-product policy takes precedence (FIX 3)
_DEFAULT_WINDOW_DAYS: int = int(os.environ.get("ATTRIBUTION_WINDOW_DAYS", "7"))


# ── attribution_id ────────────────────────────────────────────────────────────

def make_attribution_id(click_id: str, conversion_id: str) -> str:
    raw = f"{click_id}|{conversion_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def make_unattributed_id(conversion_id: str, reason_code: str) -> str:
    """Unique per (conversion_id, reason_code) — same failure type for same conversion → same ID."""
    raw = f"unattributed|{conversion_id}|{reason_code}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── Core attribution ──────────────────────────────────────────────────────────

def attribute_conversion(
    conversion:   ConversionEvent,
    clicks:       list[ClickEvent],
    window_days:  int | None = None,
) -> tuple[AttributionRecord, UnattributedRecord | None]:
    """
    Pure function: match one ConversionEvent to the best ClickEvent.

    Args:
        conversion:  the conversion to attribute
        clicks:      candidate clicks for the same product (pre-filtered by product_id)
        window_days: override window; None → use per-product policy (FIX 3)

    Returns:
        (AttributionRecord, None) on success
        (AttributionRecord[unattributed=True], UnattributedRecord) on failure (FIX 4)
    """
    ts_now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # FIX 3 — per-product policy window
    if window_days is None:
        window_days = get_policy(conversion.product_id).window_days

    try:
        conv_dt = _parse_iso(conversion.timestamp)
    except ValueError:
        ua_rec = _make_unattributed(conversion, ts_now, ReasonCode.UNPARSEABLE_TS, clicks)
        return _unattributed(conversion, ts_now), ua_rec

    window_start = conv_dt - datetime.timedelta(days=window_days)

    # Classify clicks: all_exist, within_window, before_conversion
    click_attempted = bool(clicks)
    candidates = []
    has_outside_window = False

    for click in clicks:
        try:
            click_dt = _parse_iso(click.timestamp)
        except ValueError:
            continue
        if click_dt >= conv_dt:
            # Future click — skip (FUTURE_CLICK tracked but no candidate)
            continue
        if click_dt < window_start:
            has_outside_window = True
            continue
        candidates.append((click_dt, click))

    if not candidates:
        # FIX 4 — specific reason code
        if not click_attempted:
            reason = ReasonCode.NO_MATCH_CLICK
        elif has_outside_window and not candidates:
            reason = ReasonCode.OUTSIDE_WINDOW
        else:
            reason = ReasonCode.NO_MATCH_CLICK
        ua_rec = _make_unattributed(conversion, ts_now, reason, clicks)
        return _unattributed(conversion, ts_now), ua_rec

    # FIX 6 — deterministic tie-breaker when multiple clicks have same timestamp
    # Sort key: (1) most recent timestamp DESC, (2) same platform as conversion preferred,
    # (3) oldest click_id alphabetically (deterministic tiebreak)
    def _sort_key(item: tuple[datetime.datetime, ClickEvent]):
        dt, click = item
        platform_match = 0 if click.platform == getattr(conversion, "platform", "") else 1
        return (-dt.timestamp(), platform_match, click.click_id)

    candidates.sort(key=_sort_key)
    _best_dt, best_click = candidates[0]

    return AttributionRecord(
        attribution_id=make_attribution_id(best_click.click_id, conversion.conversion_id),
        click_id=best_click.click_id,
        conversion_id=conversion.conversion_id,
        product_id=conversion.product_id,
        revenue_amount=conversion.revenue_amount,
        currency=conversion.currency,
        model="last_click",
        confidence=1.0,
        unattributed=False,
        timestamp=ts_now,
    ), None


def run(
    product_id:    str = "",       # empty = run for all products
    since:         str = "",       # ISO date "YYYY-MM-DD"
    window_days:   int | None = None,  # None → per-product policy (FIX 3)
    skip_existing: bool = True,    # skip conversions already attributed
) -> list[AttributionRecord]:
    """
    Run attribution for all conversions (or a specific product).

    Args:
        product_id:    filter to specific product, empty = all
        since:         only process conversions from this date onward
        window_days:   override window; None → per-product policy
        skip_existing: if True, skip conversion_ids already in attribution logs

    Returns:
        List of AttributionRecords written this run (attributed + unattributed)
    """
    if product_id:
        conversions = get_conversions_for_product(product_id, since=since)
    else:
        conversions = get_all_conversions(since=since)

    if not conversions:
        return []

    existing_conv_ids = _load_existing_attributed_conversion_ids() if skip_existing else set()

    # Group by product_id to batch click lookups
    products: dict[str, list[ConversionEvent]] = {}
    for conv in conversions:
        if conv.conversion_id in existing_conv_ids:
            continue
        products.setdefault(conv.product_id, []).append(conv)

    results: list[AttributionRecord] = []

    for pid, convs in products.items():
        clicks = get_clicks_for_product(pid, since=since)
        for conv in convs:
            record, ua_rec = attribute_conversion(conv, clicks, window_days=window_days)
            _append(record)
            if ua_rec is not None:
                _append_unattributed(ua_rec)
            results.append(record)

    return results


def get_attributions(
    product_id: str = "",
    since:      str = "",
) -> list[AttributionRecord]:
    """Read all attribution records from JSONL logs."""
    records: list[AttributionRecord] = []
    for jsonl_file in sorted(_ATTRIBUTIONS_DIR.glob("*.jsonl")):
        if since and jsonl_file.stem < since[:10]:
            continue
        try:
            for line in jsonl_file.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                if product_id and d.get("product_id") != product_id:
                    continue
                records.append(AttributionRecord.from_dict(d))
        except Exception:
            continue
    return records


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_iso(ts: str) -> datetime.datetime:
    """Parse ISO 8601 timestamp → datetime (UTC)."""
    ts = ts.rstrip("Z").replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(ts, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse timestamp: {ts!r}")


def _unattributed(
    conversion: ConversionEvent,
    ts_now:     str,
) -> AttributionRecord:
    """Return AttributionRecord shell for unattributed conversions."""
    return AttributionRecord(
        attribution_id=make_unattributed_id(conversion.conversion_id, ReasonCode.NO_MATCH_CLICK),
        click_id="",
        conversion_id=conversion.conversion_id,
        product_id=conversion.product_id,
        revenue_amount=conversion.revenue_amount,
        currency=conversion.currency,
        model="last_click",
        confidence=0.0,
        unattributed=True,
        timestamp=ts_now,
    )


def _make_unattributed(
    conversion:      ConversionEvent,
    ts_now:          str,
    reason_code:     str,
    all_clicks:      list[ClickEvent],
) -> UnattributedRecord:
    """Build explicit UnattributedRecord for FIX 4 logging."""
    return UnattributedRecord(
        unattributed_id=make_unattributed_id(conversion.conversion_id, reason_code),
        conversion_id=conversion.conversion_id,
        click_id="",
        product_id=conversion.product_id,
        reason_code=reason_code,
        revenue_amount=0.0,
        currency=conversion.currency,
        click_attempted=bool(all_clicks),
        timestamp=ts_now,
    )


def _load_existing_attributed_conversion_ids() -> set[str]:
    ids: set[str] = set()
    for jsonl_file in _ATTRIBUTIONS_DIR.glob("*.jsonl"):
        try:
            for line in jsonl_file.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                cid = d.get("conversion_id")
                if cid:
                    ids.add(cid)
        except Exception:
            continue
    return ids


def _append(record: AttributionRecord) -> None:
    date_str = datetime.date.today().isoformat()
    log_file = _ATTRIBUTIONS_DIR / f"{date_str}.jsonl"
    line     = json.dumps(record.to_dict(), ensure_ascii=False)
    with _lock:
        with open(log_file, "a") as f:
            f.write(line + "\n")


def _append_unattributed(record: UnattributedRecord) -> None:
    """Write explicit unattributed event record (FIX 4)."""
    date_str = datetime.date.today().isoformat()
    log_file = _UNATTRIBUTED_DIR / f"{date_str}.jsonl"
    line     = json.dumps(record.to_dict(), ensure_ascii=False)
    with _lock:
        with open(log_file, "a") as f:
            f.write(line + "\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="Run attribution for all pending conversions")
    parser.add_argument("--product", default="", help="Filter to product_id")
    parser.add_argument("--since", default="", help="Since date YYYY-MM-DD")
    parser.add_argument("--window", type=int, default=_DEFAULT_WINDOW_DAYS)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.run:
        records = run(product_id=args.product, since=args.since, window_days=args.window)
        attributed   = sum(1 for r in records if not r.unattributed)
        unattributed = sum(1 for r in records if r.unattributed)
        total_rev    = sum(r.revenue_amount for r in records if not r.unattributed)
        print(f"✅ Attributed: {attributed}  Unattributed: {unattributed}  Revenue: ${total_rev:.2f}")
    elif args.list:
        for rec in get_attributions(product_id=args.product, since=args.since):
            print(json.dumps(rec.to_dict()))
