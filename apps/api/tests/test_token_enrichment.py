"""P1 credibility: DAS metadata enrichment + live price from swap events.

Network is stubbed (conftest): fetch_das_metadata returns {} unless a test
overrides it, and SOL price fetches return None.
"""
from datetime import datetime, timezone

import pytest

MINT = "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


def _signal(db, **overrides):
    from models.token import TokenSignal

    defaults = dict(
        id="ts-enrich-1",
        token_address=MINT,
        symbol="UNKNOWN",
        name="Unknown Token",
        scan_timestamp=datetime.now(timezone.utc),
        momentum_score=0.0,
        rug_risk_score=50.0,
    )
    defaults.update(overrides)
    row = TokenSignal(**defaults)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_swap_event_sets_execution_price_and_market_cap(db, monkeypatch):
    from services.discovery.webhook_handler import HeliusWebhookProcessor

    monkeypatch.setattr(
        "services.execution.price_feed.get_sol_price_usd", lambda: 100.0
    )
    signal = _signal(db)
    event = {
        "nativeTransfers": [{"amount": 2_000_000_000}],  # 2 SOL in lamports
        "tokenTransfers": [{"mint": MINT, "tokenAmount": 50_000}],
    }
    HeliusWebhookProcessor(db)._update_metrics_from_event(signal, event, "SWAP")

    # 2 SOL for 50k tokens at $100/SOL -> $0.004/token; 1B fixed supply.
    assert signal.price_usd == pytest.approx(0.004)
    assert signal.market_cap == pytest.approx(4_000_000)


def test_swap_without_token_amount_leaves_price_untouched(db, monkeypatch):
    from services.discovery.webhook_handler import HeliusWebhookProcessor

    monkeypatch.setattr(
        "services.execution.price_feed.get_sol_price_usd", lambda: 100.0
    )
    signal = _signal(db)
    event = {"nativeTransfers": [{"amount": 2_000_000_000}]}
    HeliusWebhookProcessor(db)._update_metrics_from_event(signal, event, "SWAP")
    assert signal.price_usd is None and signal.market_cap is None


def test_parse_das_asset_extracts_fields():
    from services.discovery.token_metadata import parse_das_asset

    asset = {
        "id": MINT,
        "content": {
            "metadata": {"name": "Doge Wif Hat", "symbol": "DWH"},
            "links": {"image": "https://img.example/x.png"},
        },
    }
    assert parse_das_asset(asset) == {
        "name": "Doge Wif Hat",
        "symbol": "DWH",
        "image_uri": "https://img.example/x.png",
    }
    assert parse_das_asset(None) is None
    assert parse_das_asset({"id": MINT, "content": {}}) is None


def test_feed_item_exposes_image_from_metadata(db):
    from schemas.discovery import TokenFeedItem

    signal = _signal(db, token_metadata={"image_uri": "https://img.example/y.png"})
    assert TokenFeedItem.from_signal(signal).image_uri == "https://img.example/y.png"


def test_apply_das_metadata_merges_not_replaces(db):
    from services.discovery.webhook_handler import HeliusWebhookProcessor

    signal = _signal(db, token_metadata={"source": "helius_das"})
    HeliusWebhookProcessor(db)._apply_das_metadata(
        signal, {"name": "Foo Coin", "symbol": "FOO", "image_uri": "https://i.example/z.png"}
    )
    assert signal.symbol == "FOO" and signal.name == "Foo Coin"
    assert signal.token_metadata["image_uri"] == "https://i.example/z.png"
    assert signal.token_metadata["source"] == "helius_das"


def test_enrich_task_backfills_unknown_tokens(db, monkeypatch):
    from models.token import TokenSignal
    from services.discovery.tasks import enrich_token_metadata

    _signal(db)
    monkeypatch.setattr(
        "services.discovery.token_metadata.fetch_das_metadata",
        lambda mints: {MINT: {"name": "Foo Coin", "symbol": "FOO", "image_uri": None}},
    )
    result = enrich_token_metadata()
    assert result["status"] == "completed"
    assert result["updated"] == 1

    db.expire_all()
    row = db.query(TokenSignal).filter_by(token_address=MINT).one()
    assert row.symbol == "FOO" and row.name == "Foo Coin"
