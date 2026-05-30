#!/usr/bin/env python3
"""
test_revenue_layer.py — Integration + unit tests for the Revenue Layer.

Tests full flow: click → conversion → attribution → ledger.
Uses temp directories — no production data touched.
"""

from __future__ import annotations

import csv
import datetime
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    """Bridge pytest's tmp_path to the tmp_dir parameter expected by standalone test functions."""
    return tmp_path

_PASS = 0
_FAIL = 0


def _check(name: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  ✅ {name}")
    else:
        _FAIL += 1
        print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))


# ── schemas ───────────────────────────────────────────────────────────────────

def test_schemas_frozen() -> None:
    print("\n[1] Schemas are frozen dataclasses")
    from revenue_layer.schemas import ClickEvent, ConversionEvent

    ev = ClickEvent(
        click_id="abc123", post_id="p1", product_id="B085DTZQNZ",
        platform="instagram", timestamp="2026-05-26T10:00:00Z",
    )
    try:
        ev.click_id = "hacked"  # type: ignore
        _check("ClickEvent is frozen", False)
    except Exception:
        _check("ClickEvent is frozen", True)

    _check("ClickEvent.to_dict() works", isinstance(ev.to_dict(), dict))
    _check("ClickEvent.from_dict(to_dict()) round-trips",
           ClickEvent.from_dict(ev.to_dict()) == ev)


# ── click_tracker ─────────────────────────────────────────────────────────────

def test_click_id_deterministic() -> None:
    print("\n[2] click_id is deterministic")
    from revenue_layer.click_tracker import make_click_id
    id1 = make_click_id("post_1", "B085DTZQNZ", "instagram", "2026-05-26T10:00:00")
    id2 = make_click_id("post_1", "B085DTZQNZ", "instagram", "2026-05-26T10:00:00")
    _check("Same inputs → same click_id", id1 == id2)
    _check("click_id length 16", len(id1) == 16)
    _check("click_id is hex", all(c in "0123456789abcdef" for c in id1))


def test_click_different_platforms_differ() -> None:
    print("\n[3] Different platforms → different click_id")
    from revenue_layer.click_tracker import make_click_id
    ts = "2026-05-26T10:00:00"
    id_ig  = make_click_id("post_1", "B085DTZQNZ", "instagram", ts)
    id_tt  = make_click_id("post_1", "B085DTZQNZ", "tiktok",    ts)
    _check("instagram ≠ tiktok click_id", id_ig != id_tt)


def test_click_record_and_read(tmp_dir: Path) -> None:
    print("\n[4] click_tracker.record() writes and reads back")
    import revenue_layer.click_tracker as ct
    tmp_dir.mkdir(parents=True, exist_ok=True)
    with patch.object(ct, "_CLICKS_DIR", tmp_dir):
        ev = ct.record("post_001", "B085DTZQNZ", "instagram")
        _check("ClickEvent returned", ev.click_id != "")
        _check("product_id correct", ev.product_id == "B085DTZQNZ")

        clicks = ct.get_clicks_for_product("B085DTZQNZ")
        _check("Click readable from log", len(clicks) >= 1)
        _check("click_id matches", any(c.click_id == ev.click_id for c in clicks))


# ── affiliate_link_builder ────────────────────────────────────────────────────

def test_affiliate_link_deterministic() -> None:
    print("\n[5] affiliate_link_builder produces deterministic URLs")
    from revenue_layer.affiliate_link_builder import build
    url1 = build("B085DTZQNZ", "post_001", "instagram")
    url2 = build("B085DTZQNZ", "post_001", "instagram")
    _check("Same inputs → same URL", url1 == url2)
    _check("Contains affiliate tag", "aetherglobal-20" in url1)
    _check("Contains amazon.com",    "amazon.com" in url1)
    _check("Contains UTM source",    "utm_source=instagram" in url1)
    _check("Contains utm_content",   "utm_content=" in url1)


def test_affiliate_link_platform_varies() -> None:
    print("\n[6] Different platforms → different utm_source")
    from revenue_layer.affiliate_link_builder import build
    url_ig = build("B085DTZQNZ", "post_001", "instagram")
    url_tt = build("B085DTZQNZ", "post_001", "tiktok")
    _check("instagram URL has instagram source", "utm_source=instagram" in url_ig)
    _check("tiktok URL has tiktok source",       "utm_source=tiktok" in url_tt)
    _check("URLs differ by platform",             url_ig != url_tt)


def test_asin_detection() -> None:
    print("\n[7] ASIN detection")
    from revenue_layer.affiliate_link_builder import _is_asin
    _check("B085DTZQNZ is ASIN",  _is_asin("B085DTZQNZ"))
    _check("B09V7Z4TJG is ASIN",  _is_asin("B09V7Z4TJG"))
    _check("random string is not ASIN", not _is_asin("not_an_asin"))
    _check("short string is not ASIN",  not _is_asin("B085"))


# ── conversion_ingestor ───────────────────────────────────────────────────────

def _write_amazon_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = ["ASIN", "Order ID", "Commission", "Date", "Currency"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def test_ingest_amazon_csv(tmp_dir: Path) -> None:
    print("\n[8] conversion_ingestor.ingest_amazon_csv()")
    import revenue_layer.conversion_ingestor as ci
    tmp_dir.mkdir(parents=True, exist_ok=True)
    with patch.object(ci, "_CONVERSIONS_DIR", tmp_dir):
        csv_file = tmp_dir / "report.csv"
        _write_amazon_csv(csv_file, [
            {"ASIN": "B085DTZQNZ", "Order ID": "ORD001", "Commission": "$1.32",
             "Date": "2026-05-20", "Currency": "USD"},
            {"ASIN": "B09V7Z4TJG", "Order ID": "ORD002", "Commission": "0.75",
             "Date": "2026-05-21", "Currency": "USD"},
        ])
        ingested, skipped = ci.ingest_amazon_csv(csv_file)
        _check("2 conversions ingested", ingested == 2, f"got {ingested}")
        _check("0 skipped",              skipped == 0,  f"got {skipped}")

        # Idempotency: ingest same file again
        ingested2, skipped2 = ci.ingest_amazon_csv(csv_file)
        _check("Re-ingest → 0 new", ingested2 == 0, f"got {ingested2}")
        _check("Re-ingest → 2 skipped", skipped2 == 2, f"got {skipped2}")

        convs = ci.get_conversions_for_product("B085DTZQNZ")
        _check("Conversion readable", len(convs) >= 1)
        _check("Revenue amount correct", convs[0].revenue_amount == 1.32)


# ── attribution_engine ────────────────────────────────────────────────────────

def test_last_click_attribution() -> None:
    print("\n[9] attribution_engine — last-click model")
    from revenue_layer.attribution_engine import attribute_conversion
    from revenue_layer.schemas import ClickEvent, ConversionEvent

    conv = ConversionEvent(
        conversion_id="conv001",
        product_id="B085DTZQNZ",
        revenue_amount=1.32,
        currency="USD",
        timestamp="2026-05-25T12:00:00Z",
        source="amazon_associates",
        order_id="ORD001",
    )

    # Three clicks: two in window, one outside (too old)
    clicks = [
        ClickEvent(click_id="c1", post_id="p1", product_id="B085DTZQNZ",
                   platform="instagram", timestamp="2026-05-10T10:00:00Z"),  # outside 7d window
        ClickEvent(click_id="c2", post_id="p2", product_id="B085DTZQNZ",
                   platform="tiktok",   timestamp="2026-05-20T08:00:00Z"),  # in window, earlier
        ClickEvent(click_id="c3", post_id="p3", product_id="B085DTZQNZ",
                   platform="instagram", timestamp="2026-05-24T09:00:00Z"),  # in window, latest
    ]

    result, ua_rec = attribute_conversion(conv, clicks, window_days=7)
    _check("Attribution matched",       not result.unattributed)
    _check("No UnattributedRecord",     ua_rec is None)
    _check("Last-click selected (c3)",  result.click_id == "c3",  f"got {result.click_id}")
    _check("Model is last_click",       result.model == "last_click")
    _check("Confidence 1.0",            result.confidence == 1.0)
    _check("Revenue carried over",      result.revenue_amount == 1.32)


def test_unattributed_no_clicks() -> None:
    print("\n[10] attribution_engine — unattributed when no clicks")
    from revenue_layer.attribution_engine import attribute_conversion
    from revenue_layer.schemas import ConversionEvent

    conv = ConversionEvent(
        conversion_id="conv_orphan",
        product_id="B085DTZQNZ",
        revenue_amount=0.50,
        currency="USD",
        timestamp="2026-05-25T12:00:00Z",
        source="amazon_associates",
        order_id="ORPHAN001",
    )
    result, ua_rec = attribute_conversion(conv, clicks=[], window_days=7)
    _check("Unattributed=True",            result.unattributed)
    _check("click_id empty",               result.click_id == "")
    _check("Confidence 0.0",               result.confidence == 0.0)
    _check("UnattributedRecord emitted",   ua_rec is not None)
    _check("UA reason code set",           ua_rec is not None and ua_rec.reason_code != "")
    _check("UA revenue = 0.0",             ua_rec is not None and ua_rec.revenue_amount == 0.0)
    _check("click_attempted False",        ua_rec is not None and ua_rec.click_attempted is False)


def test_click_after_conversion_not_matched() -> None:
    print("\n[11] attribution_engine — click AFTER conversion not matched")
    from revenue_layer.attribution_engine import attribute_conversion
    from revenue_layer.schemas import ClickEvent, ConversionEvent

    conv = ConversionEvent(
        conversion_id="conv_early",
        product_id="B085DTZQNZ",
        revenue_amount=1.00,
        currency="USD",
        timestamp="2026-05-20T10:00:00Z",
        source="amazon_associates",
        order_id="EARLY001",
    )
    # Click AFTER conversion — must not be matched
    clicks = [
        ClickEvent(click_id="future_click", post_id="p1", product_id="B085DTZQNZ",
                   platform="instagram", timestamp="2026-05-21T10:00:00Z"),
    ]
    result, ua_rec = attribute_conversion(conv, clicks, window_days=7)
    _check("Future click not matched", result.unattributed)
    _check("UnattributedRecord emitted", ua_rec is not None)


# ── revenue_ledger ────────────────────────────────────────────────────────────

def test_ledger_append_only(tmp_dir: Path) -> None:
    print("\n[12] revenue_ledger — append-only (pending → confirmed)")
    import revenue_layer.revenue_ledger as rl
    from revenue_layer.schemas import AttributionRecord, ClickEvent

    tmp_dir.mkdir(parents=True, exist_ok=True)
    with patch.object(rl, "_LEDGER_DIR",   tmp_dir), \
         patch.object(rl, "_LEGACY_LEDGER_FILE", tmp_dir / "records_legacy.jsonl"), \
         patch.object(rl, "_SUMMARY_FILE", tmp_dir / "summary.json"):

        attr = AttributionRecord(
            attribution_id="attr001",
            click_id="c3",
            conversion_id="conv001",
            product_id="B085DTZQNZ",
            revenue_amount=1.32,
            currency="USD",
            model="last_click",
            confidence=1.0,
            unattributed=False,
            timestamp="2026-05-26T10:00:00Z",
        )
        click = ClickEvent(
            click_id="c3", post_id="p3", product_id="B085DTZQNZ",
            platform="instagram", timestamp="2026-05-24T09:00:00Z",
        )

        # Post pending entry
        pending = rl.post_attribution(attr, click, product_price=33.13)
        _check("Pending entry written",     pending.payout_status == "pending")
        _check("Estimated revenue > 0",     pending.estimated_revenue > 0)
        _check("Platform from click",       pending.platform == "instagram")

        # Confirm payout
        confirmed = rl.confirm_payout("attr001", confirmed_amount=1.32, payout_date="2026-06-01")
        _check("Confirmed entry written",   confirmed.payout_status == "confirmed")
        _check("Confirmed amount correct",  confirmed.confirmed_revenue == 1.32)

        # Both entries in ledger (append-only)
        all_entries = rl.get_all_entries()
        _check("Both entries in ledger",    len(all_entries) == 2)
        _check("Original pending preserved", any(e.payout_status == "pending"   for e in all_entries))
        _check("Confirmed entry present",    any(e.payout_status == "confirmed" for e in all_entries))


def test_ledger_summary(tmp_dir: Path) -> None:
    print("\n[13] revenue_ledger.compute_summary()")
    import revenue_layer.revenue_ledger as rl
    from revenue_layer.schemas import AttributionRecord, ClickEvent

    tmp_dir.mkdir(parents=True, exist_ok=True)
    legacy_file = tmp_dir / "records_legacy.jsonl"
    with patch.object(rl, "_LEDGER_DIR",   tmp_dir), \
         patch.object(rl, "_LEGACY_LEDGER_FILE", legacy_file), \
         patch.object(rl, "_SUMMARY_FILE", tmp_dir / "summary.json"):

        # Write a confirmed entry directly to legacy file (tests backward compat replay)
        recorded_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        entry_data = {
            "ledger_id": "led001",
            "attribution_id": "attr001",
            "click_id": "c3",
            "conversion_id": "conv001",
            "product_id": "B085DTZQNZ",
            "platform": "instagram",
            "estimated_revenue": 1.33,
            "confirmed_revenue": 1.32,
            "currency": "USD",
            "payout_status": "confirmed",
            "payout_date": "2026-06-01",
            "recorded_at": recorded_at,
        }
        with open(legacy_file, "a") as f:
            f.write(json.dumps(entry_data) + "\n")

        summary = rl.compute_summary()
        _check("Summary has total_products",           "total_products" in summary)
        _check("Total confirmed_revenue > 0",          summary["total_confirmed_revenue"] > 0)
        _check("summary.json written",                 (tmp_dir / "summary.json").exists())


# ── Full flow integration ─────────────────────────────────────────────────────

def test_full_revenue_flow(tmp_dir: Path) -> None:
    print("\n[14] Full flow: click → conversion → attribution → ledger")
    import revenue_layer.click_tracker      as ct
    import revenue_layer.conversion_ingestor as ci
    import revenue_layer.attribution_engine  as ae
    import revenue_layer.revenue_ledger      as rl

    ledger_dir = tmp_dir / "ledger"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    with patch.object(ct, "_CLICKS_DIR",           tmp_dir / "clicks"), \
         patch.object(ci, "_CONVERSIONS_DIR",       tmp_dir / "conversions"), \
         patch.object(ae, "_ATTRIBUTIONS_DIR",      tmp_dir / "attributions"), \
         patch.object(ae, "_UNATTRIBUTED_DIR",      tmp_dir / "unattributed"), \
         patch.object(rl, "_LEDGER_DIR",            ledger_dir), \
         patch.object(rl, "_LEGACY_LEDGER_FILE",    ledger_dir / "records_legacy.jsonl"), \
         patch.object(rl, "_SUMMARY_FILE",          ledger_dir / "summary.json"):

        for d in ["clicks", "conversions", "attributions"]:
            (tmp_dir / d).mkdir(parents=True, exist_ok=True)

        # 1. Record click from a post
        click = ct.record("post_abc", "B085DTZQNZ", "instagram")
        _check("Click recorded", click.click_id != "")

        # 2. Simulate a conversion 3 days later
        conv_ts = "2026-05-29T10:00:00Z"  # 3 days after a May 26 click
        from revenue_layer.schemas import ConversionEvent
        from revenue_layer.conversion_ingestor import make_conversion_id, _append as ci_append
        conv = ConversionEvent(
            conversion_id=make_conversion_id("ORD999", "B085DTZQNZ", conv_ts),
            product_id="B085DTZQNZ",
            revenue_amount=1.32,
            currency="USD",
            timestamp=conv_ts,
            source="amazon_associates",
            order_id="ORD999",
        )
        ci_append(conv)

        # 3. Run attribution
        clicks_for_product = ct.get_clicks_for_product("B085DTZQNZ")
        convs_for_product  = ci.get_conversions_for_product("B085DTZQNZ")
        _check("1 click readable",      len(clicks_for_product) == 1)
        _check("1 conversion readable", len(convs_for_product)  == 1)

        attribution, ua_rec = ae.attribute_conversion(convs_for_product[0], clicks_for_product, window_days=7)
        _check("Attribution matched",   not attribution.unattributed, f"confidence={attribution.confidence}")
        _check("Correct click matched", attribution.click_id == click.click_id)
        _check("No unattributed rec",   ua_rec is None)

        # 4. Post to ledger
        ledger_entry = rl.post_attribution(attribution, clicks_for_product[0], product_price=33.13)
        _check("Ledger entry written",         ledger_entry.payout_status == "pending")
        _check("Platform from click (instagram)", ledger_entry.platform == "instagram")
        _check("Estimated revenue present",    ledger_entry.estimated_revenue > 0)


# ── FIX 7: validate_tracked_url ───────────────────────────────────────────────

def test_validate_tracked_url() -> None:
    print("\n[15] affiliate_link_builder.validate_tracked_url() (FIX 7)")
    from revenue_layer.affiliate_link_builder import build, validate_tracked_url

    # Valid URL built by build() — should pass
    url = build("B085DTZQNZ", "post_001", "instagram")
    try:
        validate_tracked_url(url)
        _check("Valid URL passes validation", True)
    except ValueError as e:
        _check("Valid URL passes validation", False, str(e))

    # URL missing tag param
    no_tag = "https://www.amazon.com/dp/B085DTZQNZ?utm_source=instagram&utm_medium=social&utm_campaign=imperio_affiliate"
    try:
        validate_tracked_url(no_tag)
        _check("Missing tag raises ValueError", False)
    except ValueError:
        _check("Missing tag raises ValueError", True)

    # URL missing UTM params
    no_utm = "https://www.amazon.com/dp/B085DTZQNZ?tag=aetherglobal-20"
    try:
        validate_tracked_url(no_utm)
        _check("Missing UTM raises ValueError", False)
    except ValueError:
        _check("Missing UTM raises ValueError", True)

    # Empty URL
    try:
        validate_tracked_url("")
        _check("Empty URL raises ValueError", False)
    except ValueError:
        _check("Empty URL raises ValueError", True)

    # require_affiliate_tag=False — only UTM required
    no_tag_relaxed = "https://www.amazon.com/dp/B085DTZQNZ?utm_source=instagram&utm_medium=social&utm_campaign=x"
    try:
        validate_tracked_url(no_tag_relaxed, require_affiliate_tag=False)
        _check("No tag OK when require_affiliate_tag=False", True)
    except ValueError as e:
        _check("No tag OK when require_affiliate_tag=False", False, str(e))


# ── FIX 4: UnattributedRecord schema ─────────────────────────────────────────

def test_unattributed_record_schema() -> None:
    print("\n[16] schemas.UnattributedRecord (FIX 4)")
    from revenue_layer.schemas import UnattributedRecord, ReasonCode

    rec = UnattributedRecord(
        unattributed_id="ua001",
        conversion_id="conv001",
        click_id="",
        product_id="B085DTZQNZ",
        reason_code=ReasonCode.NO_MATCH_CLICK,
        revenue_amount=0.0,
        currency="USD",
        click_attempted=False,
        timestamp="2026-05-26T10:00:00Z",
    )
    _check("UnattributedRecord is frozen",    isinstance(rec, UnattributedRecord))
    _check("revenue_amount always 0.0",       rec.revenue_amount == 0.0)
    _check("reason_code populated",           rec.reason_code == ReasonCode.NO_MATCH_CLICK)
    _check("to_dict() works",                 isinstance(rec.to_dict(), dict))
    _check("from_dict() round-trips",         UnattributedRecord.from_dict(rec.to_dict()) == rec)

    # Immutable
    try:
        rec.revenue_amount = 99.0  # type: ignore
        _check("UnattributedRecord is frozen", False)
    except Exception:
        _check("UnattributedRecord is frozen (mutation blocked)", True)

    # from_dict forces revenue_amount=0.0 even if dict has non-zero
    d = rec.to_dict()
    d["revenue_amount"] = 999.0
    rec2 = UnattributedRecord.from_dict(d)
    _check("from_dict enforces revenue_amount=0.0", rec2.revenue_amount == 0.0)


# ── FIX 1: click_id burst uniqueness ─────────────────────────────────────────

def test_click_id_burst_unique() -> None:
    print("\n[17] click_tracker — burst uniqueness (FIX 1)")
    import revenue_layer.click_tracker as ct

    ids = set()
    for i in range(50):
        ts_us, nonce = ct._next_nonce()
        cid = ct.make_click_id("post_burst", "B085DTZQNZ", "instagram", ts_us, nonce)
        ids.add(cid)

    _check("50 rapid clicks → 50 unique IDs", len(ids) == 50)
    _check("All IDs are 16-char hex",
           all(len(x) == 16 and all(c in "0123456789abcdef" for c in x) for x in ids))


# ── FIX 2: conversion_id with order_item_id + source ─────────────────────────

def test_conversion_id_includes_source() -> None:
    print("\n[18] conversion_ingestor — conversion_id includes source (FIX 2)")
    from revenue_layer.conversion_ingestor import make_conversion_id

    id_amazon  = make_conversion_id("ORD001", "B085DTZQNZ", "2026-05-26", "", "amazon_associates")
    id_impact  = make_conversion_id("ORD001", "B085DTZQNZ", "2026-05-26", "", "impact")
    id_item    = make_conversion_id("ORD001", "B085DTZQNZ", "2026-05-26", "ITEM001", "amazon_associates")

    _check("Same order, diff source → diff ID",    id_amazon != id_impact)
    _check("Same order, diff item → diff ID",      id_amazon != id_item)
    _check("Same inputs → same ID (deterministic)", id_amazon == make_conversion_id(
        "ORD001", "B085DTZQNZ", "2026-05-26", "", "amazon_associates"))


if __name__ == "__main__":
    print("Revenue Layer tests")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        test_schemas_frozen()
        test_click_id_deterministic()
        test_click_different_platforms_differ()
        test_click_record_and_read(tmp_path / "clicks")
        test_affiliate_link_deterministic()
        test_affiliate_link_platform_varies()
        test_asin_detection()
        test_ingest_amazon_csv(tmp_path / "conversions")
        test_last_click_attribution()
        test_unattributed_no_clicks()
        test_click_after_conversion_not_matched()
        test_ledger_append_only(tmp_path / "ledger")
        test_ledger_summary(tmp_path / "ledger2")
        test_full_revenue_flow(tmp_path / "flow")
        test_validate_tracked_url()
        test_unattributed_record_schema()
        test_click_id_burst_unique()
        test_conversion_id_includes_source()

    print(f"\n{'='*50}")
    print(f"RESULT: {_PASS} PASS  {_FAIL} FAIL")
    sys.exit(0 if _FAIL == 0 else 1)
