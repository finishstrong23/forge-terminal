"""
Helius Webhook Handler
======================

Receives Pump.fun program events from Helius webhooks and processes them
into token signals with anti-rug scores.

Helius webhook setup:
1. Go to Helius dashboard
2. Create webhook for Pump.fun program: 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P
3. Subscribe to: SWAP, TOKEN_MINT, TRANSFER events
4. Set webhook URL to: https://api.forgeterminal.com/api/v1/webhooks/helius
"""
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import json
import hashlib
import hmac
import logging
import secrets
import httpx
import asyncio

from core.database import get_db
from models.token import HeliusEvent, TokenSignal
from services.discovery.scoring_engine import score_token, scorer
from core.config import settings

logger = logging.getLogger(__name__)

# Pump.fun API endpoint for token metadata
PUMP_FUN_API = "https://frontend-api.pump.fun/coins"

# Use shared rate limiter (also used by token_discovery.py)
from core.rate_limiter import rate_limiter

# Backwards-compatible aliases for code that uses the old API
def _can_call_pump_fun() -> bool:
    return rate_limiter.can_call()

def _record_pump_fun_request():
    rate_limiter.record_request()

def _disable_pump_fun(duration: int = 300):
    rate_limiter.disable(duration)

router = APIRouter()


async def fetch_pump_fun_metadata(mint_address: str) -> Optional[Dict]:
    """
    Fetch token metadata from Pump.fun API

    Returns: {name, symbol, image_uri, description, creator, ...} or None

    IMPORTANT: Rate limited to avoid Cloudflare bans
    """
    # Check rate limits first
    if not _can_call_pump_fun():
        print(f"⏳ Rate limited - skipping Pump.fun API call for {mint_address[:8]}...")
        return None

    try:
        _record_pump_fun_request()

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{PUMP_FUN_API}/{mint_address}")

            # Handle rate limiting
            if response.status_code in (429, 403):
                print(f"⚠️  Pump.fun rate limit hit! Status: {response.status_code}")
                _disable_pump_fun()
                return None

            if response.status_code == 200:
                text = response.text
                # Check for Cloudflare error page
                if 'error code' in text.lower() or 'cloudflare' in text.lower() or '1015' in text:
                    print(f"⚠️  Cloudflare block detected!")
                    _disable_pump_fun(900)  # 15 minute cooldown
                    return None

                data = response.json()
                return {
                    "name": data.get("name", "Unknown Token"),
                    "symbol": data.get("symbol", "UNKNOWN"),
                    "image_uri": data.get("image_uri"),
                    "description": data.get("description"),
                    "creator": data.get("creator"),
                    "market_cap": data.get("usd_market_cap"),
                    "reply_count": data.get("reply_count", 0),
                    "complete": data.get("complete", False),  # Graduated to PumpSwap
                    "virtual_sol_reserves": data.get("virtual_sol_reserves"),
                    "virtual_token_reserves": data.get("virtual_token_reserves"),
                }
            else:
                print(f"⚠️  Pump.fun API returned {response.status_code} for {mint_address}")
                return None
    except Exception as e:
        print(f"❌ Error fetching pump.fun metadata for {mint_address}: {e}")
        return None


def fetch_pump_fun_metadata_sync(mint_address: str) -> Optional[Dict]:
    """
    Synchronous version of fetch_pump_fun_metadata for use in non-async contexts

    IMPORTANT: Rate limited to avoid Cloudflare bans
    """
    import requests

    # Check rate limits first
    if not _can_call_pump_fun():
        print(f"⏳ Rate limited - skipping Pump.fun API call for {mint_address[:8]}...")
        return None

    try:
        _record_pump_fun_request()

        response = requests.get(f"{PUMP_FUN_API}/{mint_address}", timeout=10)

        # Handle rate limiting
        if response.status_code in (429, 403):
            print(f"⚠️  Pump.fun rate limit hit! Status: {response.status_code}")
            _disable_pump_fun()
            return None

        if response.status_code == 200:
            text = response.text
            # Check for Cloudflare error page
            if 'error code' in text.lower() or 'cloudflare' in text.lower() or '1015' in text:
                print(f"⚠️  Cloudflare block detected!")
                _disable_pump_fun(900)  # 15 minute cooldown
                return None

            data = response.json()
            return {
                "name": data.get("name", "Unknown Token"),
                "symbol": data.get("symbol", "UNKNOWN"),
                "image_uri": data.get("image_uri"),
                "description": data.get("description"),
                "creator": data.get("creator"),
                "market_cap": data.get("usd_market_cap"),
                "reply_count": data.get("reply_count", 0),
                "complete": data.get("complete", False),
                "virtual_sol_reserves": data.get("virtual_sol_reserves"),
                "virtual_token_reserves": data.get("virtual_token_reserves"),
            }
        return None
    except Exception as e:
        print(f"❌ Error fetching pump.fun metadata: {e}")
        return None


class HeliusWebhookProcessor:
    """
    Process Helius webhook events and create token signals
    """

    PUMP_FUN_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
    PROGRAM_ACCOUNTS = {
        "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",  # Pump.fun program
        "Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1",  # Pump.fun fee account
        "11111111111111111111111111111111",                  # System program
    }


    def __init__(self, db: Session):
        self.db = db

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify Helius webhook signature (if they provide one)

        Note: As of now, Helius may not sign webhooks. If they do, uncomment this.
        """
        if not settings.HELIUS_WEBHOOK_SECRET:
            return True  # Skip verification if no secret configured

        expected_signature = hmac.new(
            settings.HELIUS_WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected_signature)

    def store_raw_event(self, event_data: Dict) -> HeliusEvent:
        """
        Store raw Helius event for debugging and reprocessing
        """
        try:
            # Extract key fields
            signature = event_data.get('signature', '')
            event_type = event_data.get('type', 'UNKNOWN')

            # Try to extract mint address (depends on event structure)
            mint_address = self._extract_mint_address(event_data)
            bonding_curve_address = self._extract_bonding_curve(event_data)

            # Parse timestamp
            timestamp = event_data.get('timestamp')
            if timestamp:
                event_timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            else:
                event_timestamp = datetime.now(timezone.utc)

            # Check if event already exists
            existing = self.db.query(HeliusEvent).filter(
                HeliusEvent.signature == signature
            ).first()

            if existing:
                return existing

            # Create new event
            event = HeliusEvent(
                event_type=event_type,
                signature=signature,
                mint_address=mint_address,
                bonding_curve_address=bonding_curve_address,
                raw_data=event_data,
                event_timestamp=event_timestamp,
                processed=False
            )

            self.db.add(event)
            self.db.commit()
            self.db.refresh(event)

            return event

        except Exception as e:
            print(f"❌ Error storing raw event: {e}")
            self.db.rollback()
            raise

    def _extract_mint_address(self, event_data: Dict) -> Optional[str]:
        """
        Extract mint address from Helius event

        Event structure varies by type. Common patterns:
        - event_data['tokenTransfers'][0]['mint']
        - event_data['accountData'][0]['account']
        """
        # Try tokenTransfers first (most common)
        if 'tokenTransfers' in event_data and event_data['tokenTransfers']:
            return event_data['tokenTransfers'][0].get('mint')

        # Try accountData
        if 'accountData' in event_data and event_data['accountData']:
            for account in event_data['accountData']:
                if account.get('mint'):
                    return account['mint']

        # Try instructions
        if 'instructions' in event_data and event_data['instructions']:
            for instruction in event_data['instructions']:
                if instruction.get('accounts'):
                    # Mint is usually first account in Pump.fun swaps
                    return instruction['accounts'][0] if instruction['accounts'] else None

        return None

    def _extract_bonding_curve(self, event_data: Dict) -> Optional[str]:
        """
        Extract bonding curve address from event

        The bonding curve is the unique identifier for each Pump.fun token
        """
        # Bonding curve is typically in the accounts list
        if 'accounts' in event_data and event_data['accounts']:
            # Usually second or third account
            accounts = event_data['accounts']
            if len(accounts) > 1:
                return accounts[1]  # Common position

        return None

    def process_event(self, event: HeliusEvent) -> Optional[TokenSignal]:
        """
        Process a Helius event and create/update token signal

        This is where we:
        1. Extract transaction data
        2. Aggregate metrics (buys, sells, holders, etc.)
        3. Calculate scores
        4. Create/update TokenSignal
        """
        try:
            event_data = event.raw_data
            event_type = event.event_type

            # Only process relevant event types
            if event_type not in ['SWAP', 'TOKEN_MINT', 'TRANSFER']:
                event.processed = True
                self.db.commit()
                return None

            mint_address = event.mint_address
            if not mint_address:
                print(f"⚠️  No mint address found in event {event.signature}")
                event.processed = True
                self.db.commit()
                return None

            # Get or create token signal
            signal = self._get_or_create_signal(mint_address, event_data)

            # Update metrics based on event
            self._update_metrics_from_event(signal, event_data, event_type)

            # Calculate scores
            scores = self._calculate_scores(signal)

            # Update signal with scores
            signal.rug_risk_score = scores['rug_risk_score']
            signal.momentum_score = scores['momentum_score']
            signal.confidence_score = scores['confidence_score']
            signal.explainability_data = scores['explainability_data']

            # Determine tier visibility based on age
            signal.tier_level = self._determine_tier(signal.age_minutes or 0)

            # Update timestamp
            signal.scan_timestamp = datetime.now(timezone.utc)

            # Mark event as processed
            event.processed = True
            event.processed_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(signal)

            print(f"✅ Processed {signal.symbol}: Momentum={signal.momentum_score:.1f} Risk={signal.rug_risk_score:.1f}")

            # Invalidate cached signal data so fresh scores are served
            try:
                from core.redis_cache import cache
                cache.invalidate_pattern("signals:*")
                cache.delete("stats:overview")
            except Exception:
                pass  # Cache invalidation is non-critical

            # Broadcast scored token to WebSocket clients (cross-process via Redis pub/sub).
            # TODO(scaling): move broadcast to separate task if worker throughput becomes an issue.
            try:
                from core.pubsub import publish_token_update
                publish_token_update(signal)
            except Exception as exc:
                logger.warning(
                    "broadcast failed for token %s (%s): %s",
                    signal.symbol, signal.token_address, exc,
                )

            # Check if this signal should trigger alerts
            try:
                from services.discovery.alert_service import check_and_broadcast
                check_and_broadcast(self.db, signal)
            except Exception as alert_err:
                print(f"Alert dispatch error (non-critical): {alert_err}")

            return signal

        except Exception as e:
            print(f"❌ Error processing event {event.id}: {e}")
            event.processing_error = str(e)
            self.db.commit()
            return None

    def _get_or_create_signal(self, mint_address: str, event_data: Dict) -> TokenSignal:
        """
        Get existing signal or create new one
        """
        # Try to find existing signal
        signal = self.db.query(TokenSignal).filter(
            TokenSignal.token_address == mint_address
        ).order_by(TokenSignal.scan_timestamp.desc()).first()

        if signal:
            # Update metadata if still unknown
            if signal.symbol == "UNKNOWN" or signal.name == "Unknown Token":
                metadata = fetch_pump_fun_metadata_sync(mint_address)
                if metadata:
                    signal.symbol = metadata.get("symbol", signal.symbol)
                    signal.name = metadata.get("name", signal.name)
                    signal.token_metadata = metadata
                    signal.dev_wallet = metadata.get("creator")
                    signal.has_graduated = metadata.get("complete", False)
                    if metadata.get("market_cap"):
                        signal.market_cap = metadata["market_cap"]
            return signal

        # Fetch metadata from Pump.fun API for new tokens
        metadata = fetch_pump_fun_metadata_sync(mint_address)

        # Create new signal with fetched metadata
        symbol = "UNKNOWN"
        name = "Unknown Token"
        dev_wallet = None
        has_graduated = False
        market_cap = None

        if metadata:
            symbol = metadata.get("symbol", "UNKNOWN")
            name = metadata.get("name", "Unknown Token")
            dev_wallet = metadata.get("creator")
            has_graduated = metadata.get("complete", False)
            market_cap = metadata.get("market_cap")

        signal = TokenSignal(
            token_address=mint_address,
            chain_id="solana",
            symbol=symbol,
            name=name,
            dev_wallet=dev_wallet,
            has_graduated=has_graduated,
            market_cap=market_cap,
            token_metadata=metadata,
            tier_level="ultra",  # Start as ultra, will be updated based on age
            scan_timestamp=datetime.now(timezone.utc),
            pair_created_at=datetime.now(timezone.utc),
            age_minutes=0.0,
            pump_fun_url=f"https://pump.fun/{mint_address}",
            # Initialize metrics
            total_holders=1,
            entity_adjusted_buyers=1,
            buys_5m=0,
            sells_5m=0,
            holder_concentration=0,
            retention_5m=100,  # Start at 100% (no one has sold yet)
        )

        self.db.add(signal)
        self.db.flush()

        print(f"✨ New token: {symbol} ({mint_address[:8]}...)")

        return signal

    def _update_metrics_from_event(self, signal: TokenSignal, event_data: Dict, event_type: str):
        """
        Update signal metrics based on event data.

        Uses wallet clustering for accurate entity-adjusted buyers
        and records per-wallet activity for historical aggregation.
        """
        from services.discovery import wallet_clustering

        # Update age
        if signal.pair_created_at:
            age = datetime.now(timezone.utc) - signal.pair_created_at
            signal.age_minutes = age.total_seconds() / 60
            signal.age_hours = signal.age_minutes / 60

        # Initialize metrics if not set
        if signal.total_holders is None:
            signal.total_holders = 1
        if signal.entity_adjusted_buyers is None:
            signal.entity_adjusted_buyers = 1
        if signal.buys_5m is None:
            signal.buys_5m = 0
        if signal.sells_5m is None:
            signal.sells_5m = 0

        # Extract SOL amount from event if available
        sol_amount = self._extract_sol_amount(event_data)

        # Increment counters and record wallet activity
        if event_type == 'SWAP':
            is_buy = self._is_buy_event(event_data)

            # Extract the user wallet for clustering
            wallet_address = wallet_clustering.extract_wallet_from_event(event_data, is_buy)

            if is_buy:
                signal.buys_5m = (signal.buys_5m or 0) + 1
                signal.total_holders = (signal.total_holders or 1) + 1
                if sol_amount and sol_amount > 0:
                    signal.net_sol_flow_15m = (signal.net_sol_flow_15m or 0) + sol_amount
            else:
                signal.sells_5m = (signal.sells_5m or 0) + 1
                if sol_amount and sol_amount > 0:
                    signal.net_sol_flow_15m = (signal.net_sol_flow_15m or 0) - sol_amount

            # Record wallet activity for clustering + historical aggregation
            if wallet_address and signal.token_address:
                event_sig = event_data.get("signature", "")
                wallet_clustering.record_wallet_activity(
                    db=self.db,
                    wallet_address=wallet_address,
                    token_address=signal.token_address,
                    activity_type="buy" if is_buy else "sell",
                    sol_amount=sol_amount,
                    event_signature=event_sig,
                    timestamp=datetime.now(timezone.utc),
                )

                # Dispatch async cluster resolution for this wallet
                try:
                    from services.discovery.tasks import resolve_wallet_cluster
                    resolve_wallet_cluster.delay(wallet_address)
                except Exception:
                    pass  # Non-critical -- clustering happens async

            # Recalculate entity-adjusted buyers from wallet data
            if signal.token_address:
                signal.entity_adjusted_buyers = wallet_clustering.recalculate_entity_adjusted_buyers(
                    self.db, signal.token_address
                )

        # Calculate buy ratio
        total_txs = (signal.buys_5m or 0) + (signal.sells_5m or 0)
        if total_txs > 0:
            signal.buy_ratio_5m = ((signal.buys_5m or 0) / total_txs) * 100

        # Calculate retention from wallet data (more accurate than counter-based)
        if signal.token_address:
            net_holders = wallet_clustering.get_unique_holders(self.db, signal.token_address)
            total_buyers = max(signal.entity_adjusted_buyers or 1, 1)
            if net_holders > 0:
                signal.retention_5m = min((net_holders / total_buyers) * 100, 100)
            else:
                signal.retention_5m = 0

        # Estimate holder concentration (heuristic based on holder count)
        holders = signal.entity_adjusted_buyers or 1
        if holders >= 50:
            signal.holder_concentration = max(10, 50 - (holders - 50) * 0.5)
        elif holders >= 20:
            signal.holder_concentration = max(20, 70 - (holders - 20) * 0.67)
        elif holders >= 10:
            signal.holder_concentration = max(30, 80 - (holders - 10) * 1)
        else:
            signal.holder_concentration = max(50, 100 - holders * 5)

        # Calculate holder growth rate (holders per minute)
        if signal.age_minutes and signal.age_minutes > 0:
            signal.holder_growth_rate = (signal.entity_adjusted_buyers or 1) / signal.age_minutes

    def _extract_sol_amount(self, event_data: Dict) -> Optional[float]:
        """
        Extract SOL amount from a swap event
        """
        try:
            # Try to get from nativeTransfers
            if 'nativeTransfers' in event_data and event_data['nativeTransfers']:
                for transfer in event_data['nativeTransfers']:
                    amount = transfer.get('amount', 0)
                    if amount > 0:
                        return amount / 1e9  # Convert lamports to SOL
            return None
        except:
            return None

    def _is_buy_event(self, event_data: Dict) -> bool:
        """
        Determine if a swap event is a buy or sell

        In Pump.fun:
        - Buy: User sends SOL to bonding curve, receives tokens
        - Sell: User sends tokens to bonding curve, receives SOL

        Detection strategy (in priority order):
        1. Check nativeTransfers: if SOL goes TO the bonding curve/program, it's a buy
        2. Check tokenTransfers: if tokens come FROM the bonding curve, it's a buy
        3. Fallback: assume buy (better to over-count buys than miss them)
        """
        bonding_curve = self._extract_bonding_curve(event_data)

        # Strategy 1: Check nativeTransfers (SOL movement)
        # Buy = user sends SOL to bonding curve or program
        # Sell = bonding curve or program sends SOL to user
        native_transfers = event_data.get('nativeTransfers', [])
        if native_transfers and bonding_curve:
            for transfer in native_transfers:
                to_account = transfer.get('toUserAccount', '')
                from_account = transfer.get('fromUserAccount', '')
                amount = transfer.get('amount', 0)

                if amount <= 0:
                    continue

                # SOL going TO bonding curve or Pump.fun program = buy
                if to_account == bonding_curve or to_account == self.PUMP_FUN_PROGRAM:
                    return True
                # SOL coming FROM bonding curve or Pump.fun program = sell
                if from_account == bonding_curve or from_account == self.PUMP_FUN_PROGRAM:
                    return False

        # Strategy 2: Check tokenTransfers direction
        token_transfers = event_data.get('tokenTransfers', [])
        if token_transfers and bonding_curve:
            for transfer in token_transfers:
                from_account = transfer.get('fromUserAccount', '')
                to_account = transfer.get('toUserAccount', '')

                # Tokens FROM bonding curve TO user = buy (user received tokens)
                if from_account == bonding_curve:
                    return True
                # Tokens FROM user TO bonding curve = sell (user sent tokens back)
                if to_account == bonding_curve:
                    return False

        # Strategy 3: Check nativeTransfers without bonding curve
        # If we don't know the bonding curve, look for Pump.fun fee account patterns
        if native_transfers:
            fee_account = "Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1"
            for transfer in native_transfers:
                # Fee going to Pump.fun fee account is typical of both buys and sells,
                # but the larger SOL transfer direction tells us:
                to_account = transfer.get('toUserAccount', '')
                from_account = transfer.get('fromUserAccount', '')
                amount = transfer.get('amount', 0)

                # Skip tiny fee transfers
                if amount < 10_000_000:  # < 0.01 SOL in lamports
                    continue

                # Large SOL transfer TO a known program account = buy
                if to_account in self.PROGRAM_ACCOUNTS or to_account == fee_account:
                    continue  # fee transfer, skip
                # Large SOL transfer FROM a known program account = sell
                if from_account in self.PROGRAM_ACCOUNTS:
                    return False

            # If we saw native transfers but none from program, likely a buy
            if len(native_transfers) > 0:
                return True

        # Fallback: assume buy
        return True

    def _calculate_scores(self, signal: TokenSignal) -> Dict:
        """
        Calculate scores using the scoring engine
        """
        # Calculate holder growth rate
        holder_growth_rate = 0
        if signal.age_minutes and signal.age_minutes > 0:
            holder_growth_rate = (signal.entity_adjusted_buyers or 1) / signal.age_minutes

        token_data = {
            'holder_concentration': signal.holder_concentration or 0,
            'creator_cluster_pct': signal.creator_cluster_pct or 0,
            'instant_buy_pct': signal.instant_buy_pct or 0,
            'entity_adjusted_buyers': signal.entity_adjusted_buyers or 1,
            'net_sol_flow_15m': signal.net_sol_flow_15m or 0,
            'retention_5m': signal.retention_5m or 100,  # Default to 100% if not calculated
            'buys_5m': signal.buys_5m or 0,
            'sells_5m': signal.sells_5m or 0,
            'buy_ratio_5m': signal.buy_ratio_5m or 50,  # Default to neutral
            'age_minutes': signal.age_minutes or 0,
            'has_freeze_authority': False,  # TODO: Get from token metadata
            'has_mint_authority': False,
            'last_update_minutes_ago': 0,
            'holder_growth_rate': holder_growth_rate,
            'total_holders': signal.total_holders or 1,
        }

        return score_token(token_data)

    @staticmethod
    def _determine_tier(age_minutes: float) -> str:
        """
        Determine which tier can see this token based on age

        - 0-1 min: ultra only
        - 1-15 min: pro and ultra
        - 15+ min: free, pro, ultra
        """
        if age_minutes < 1:
            return "ultra"
        elif age_minutes < 15:
            return "pro"
        else:
            return "free"


# ==================== WEBHOOK ENDPOINT ====================

# Owner guard for the mutating registration endpoint. Safe as a top-level
# import: routes.auth depends only on core/models/schemas, never on
# discovery services, so no cycle.
from routes.auth import require_owner

AUTH_FAILURE_CACHE_KEY = "helius:webhook_auth_failures"


def _record_webhook_auth_failure(had_header: bool) -> None:
    """Count rejected deliveries in Redis: distinguishes 'Helius sends but
    we 401 it' (secret mismatch) from 'Helius never sends'. Best-effort."""
    try:
        from core.redis_cache import cache as _cache

        current = _cache.get(AUTH_FAILURE_CACHE_KEY) or {}
        _cache.set(
            AUTH_FAILURE_CACHE_KEY,
            {
                "count": int(current.get("count", 0)) + 1,
                "last_at": datetime.now(timezone.utc).isoformat(),
                "last_had_header": had_header,
            },
            ttl=7 * 24 * 3600,
        )
    except Exception:
        pass

@router.post("/webhooks/helius")
async def helius_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Receive Helius webhook events

    Auth policy: When HELIUS_WEBHOOK_SECRET is configured, requests must
    include an Authorization header whose value exactly matches the secret
    (bearer-token style as sent by Helius, compared in constant time).
    When the secret is unset, requests are accepted unauthenticated and a
    warning is logged — this preserves dev/test workflows.

    Pipeline:
    1. Authorization check (above)
    2. Stores raw event immediately
    3. Returns 200 OK fast
    4. Processes event in background
    """
    # Verify Helius webhook authorization (Authorization header carries the
    # webhook's configured authHeader — accept it raw or Bearer-prefixed).
    expected_secret = settings.HELIUS_WEBHOOK_SECRET
    if not expected_secret:
        print("⚠️  HELIUS_WEBHOOK_SECRET not configured, accepting unsigned requests")
    else:
        auth_header = request.headers.get("Authorization", "")
        bare = auth_header.removeprefix("Bearer ").strip()
        authorized = bool(auth_header) and (
            secrets.compare_digest(auth_header, expected_secret)
            or secrets.compare_digest(bare, expected_secret)
        )
        if not authorized:
            _record_webhook_auth_failure(bool(auth_header))
            raise HTTPException(status_code=401, detail={"error": "invalid authorization"})

    try:
        # Get raw body for signature verification
        body = await request.body()

        # Parse JSON
        events = await request.json()

        # Helius sends an array of events
        if not isinstance(events, list):
            events = [events]

        processor = HeliusWebhookProcessor(db)

        # Store events and dispatch to Celery for async processing
        queued_count = 0
        sync_count = 0
        for event_data in events:
            try:
                # Store raw event (committed to DB immediately)
                event = processor.store_raw_event(event_data)

                # Try Celery dispatch first, fall back to sync if Redis is down
                try:
                    from services.discovery.tasks import process_webhook_event
                    process_webhook_event.delay(event.id)
                    queued_count += 1
                except Exception as celery_err:
                    # Redis/Celery unavailable — process synchronously
                    print(f"⚠️  Celery unavailable ({celery_err}), processing sync")
                    processor.process_event(event)
                    sync_count += 1

            except Exception as e:
                print(f"❌ Error handling event: {e}")
                continue

        return {
            "success": True,
            "events_received": len(events),
            "events_queued": queued_count,
            "events_processed_sync": sync_count,
            "message": "Events queued for background processing" if queued_count else "Events processed synchronously (Celery unavailable)"
        }

    except Exception as e:
        print(f"❌ Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/webhooks/helius/registration")
async def helius_registration_status(live: bool = False):
    """
    Read-only: is this deployment's webhook registered with Helius?
    Shows config presence (not values), the URL we register under, the
    outcome of the most recent registration attempt (runs at every boot),
    and rejected-delivery counts. With ?live=true, also fetches the
    account's webhook configs from Helius as currently stored.
    """
    from services.discovery.helius_webhooks import live_account_view, registration_status

    report = registration_status()
    if live:
        report["live"] = await live_account_view()
    return report


@router.post("/webhooks/helius/register")
async def helius_register_now(user=Depends(require_owner)):
    """
    Owner-only: force a create-or-update of the Helius webhook right now
    instead of waiting for the next deploy's startup pass.
    """
    from services.discovery.helius_webhooks import ensure_webhook_registered

    return await ensure_webhook_registered()


@router.get("/webhooks/helius/stats")
async def webhook_stats(db: Session = Depends(get_db)):
    """
    Get webhook processing statistics
    """
    from sqlalchemy import func

    total_events = db.query(func.count(HeliusEvent.id)).scalar()
    processed_events = db.query(func.count(HeliusEvent.id)).filter(
        HeliusEvent.processed == True
    ).scalar()
    pending_events = total_events - processed_events

    recent_events = db.query(HeliusEvent).order_by(
        HeliusEvent.received_at.desc()
    ).limit(10).all()

    return {
        "total_events": total_events,
        "processed_events": processed_events,
        "pending_events": pending_events,
        "recent_events": [
            {
                "id": e.id,
                "type": e.event_type,
                "mint": e.mint_address,
                "processed": e.processed,
                "received_at": e.received_at
            }
            for e in recent_events
        ]
    }


@router.post("/webhooks/helius/archive-stale")
async def archive_stale_events(
    before: str,
    user=Depends(require_owner),
    db: Session = Depends(get_db),
):
    """
    Owner-only: mark unprocessed events received before the cutoff as
    processed WITHOUT running them.

    For the pre-outage backlog: process_event stamps wallet activity at
    processing time, not event time, so replaying months-old events would
    poison live leaderboard/scoring data. Archiving keeps the raw rows
    for forensics but takes them out of the pipeline (and makes the
    unprocessed_backlog health metric meaningful again).
    """
    try:
        cutoff = datetime.fromisoformat(before)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="'before' must be an ISO date/datetime, e.g. 2026-07-12",
        )
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)

    archived = (
        db.query(HeliusEvent)
        .filter(HeliusEvent.processed.is_(False), HeliusEvent.received_at < cutoff)
        .update(
            {
                HeliusEvent.processed: True,
                HeliusEvent.processed_at: datetime.now(timezone.utc),
                HeliusEvent.processing_error: "archived: pre-outage backlog (never processed)",
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return {"success": True, "archived": archived, "cutoff": cutoff.isoformat()}


@router.post("/webhooks/helius/reprocess")
async def reprocess_events(
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Reprocess failed or pending events

    Useful for:
    - Fixing bugs in processing logic
    - Recovering from errors
    - Testing
    """
    processor = HeliusWebhookProcessor(db)

    # Get unprocessed or failed events
    events = db.query(HeliusEvent).filter(
        or_(
            HeliusEvent.processed == False,
            HeliusEvent.processing_error != None
        )
    ).order_by(HeliusEvent.event_timestamp).limit(limit).all()

    processed_count = 0
    for event in events:
        try:
            processor.process_event(event)
            processed_count += 1
        except Exception as e:
            print(f"❌ Failed to reprocess {event.id}: {e}")
            continue

    return {
        "success": True,
        "events_found": len(events),
        "events_processed": processed_count
    }


@router.post("/webhooks/helius/refresh-metadata")
async def refresh_token_metadata(
    limit: int = 10,  # Reduced default limit to avoid rate limiting
    db: Session = Depends(get_db)
):
    """
    Refresh metadata for tokens with UNKNOWN symbol/name

    Fetches fresh data from Pump.fun API for tokens missing metadata.

    NOTE: This is rate limited to max 3 tokens per minute to avoid Cloudflare bans.
    Call this endpoint multiple times with small batches.
    """
    # Find tokens with missing metadata
    tokens = db.query(TokenSignal).filter(
        or_(
            TokenSignal.symbol == "UNKNOWN",
            TokenSignal.symbol == None,
            TokenSignal.name == "Unknown Token",
            TokenSignal.name == None
        )
    ).limit(min(limit, 10)).all()  # Cap at 10 per call

    updated_count = 0
    skipped_count = 0

    for token in tokens:
        # Check if rate limited before each call
        if not _can_call_pump_fun():
            skipped_count += len(tokens) - (updated_count + skipped_count)
            print(f"⏳ Rate limited - skipped remaining {skipped_count} tokens")
            break

        try:
            metadata = fetch_pump_fun_metadata_sync(token.token_address)
            if metadata:
                token.symbol = metadata.get("symbol", token.symbol)
                token.name = metadata.get("name", token.name)
                token.token_metadata = metadata
                token.dev_wallet = metadata.get("creator")
                token.has_graduated = metadata.get("complete", False)
                if metadata.get("market_cap"):
                    token.market_cap = metadata["market_cap"]
                updated_count += 1
                print(f"✅ Updated {token.symbol} ({token.token_address[:8]}...)")

            # Wait between requests to be extra safe
            from core.rate_limiter import PUMP_FUN_MIN_INTERVAL
            await asyncio.sleep(PUMP_FUN_MIN_INTERVAL)

        except Exception as e:
            print(f"❌ Failed to update {token.token_address}: {e}")
            continue

    db.commit()

    return {
        "success": True,
        "tokens_found": len(tokens),
        "tokens_updated": updated_count,
        "tokens_skipped_rate_limit": skipped_count,
        "note": "Rate limited to ~3 tokens per minute. Call again for more."
    }


@router.post("/webhooks/helius/recalculate-scores")
async def recalculate_all_scores(
    limit: int = 500,
    rebuild_metrics: bool = True,
    db: Session = Depends(get_db)
):
    """
    Recalculate scores for all tokens

    If rebuild_metrics=True (default), recomputes metrics from WalletActivity
    data (Phase 2) with fallback to HeliusEvent estimates for tokens without
    wallet activity yet.
    """
    from services.discovery.scoring_engine import score_token
    from services.discovery.metrics_aggregator import get_current_metrics
    from services.discovery.wallet_clustering import recalculate_entity_adjusted_buyers, get_unique_holders

    tokens = db.query(TokenSignal).order_by(
        TokenSignal.scan_timestamp.desc()
    ).limit(limit).all()

    updated_count = 0
    for token in tokens:
        try:
            # === REBUILD METRICS ===
            if rebuild_metrics and token.token_address:
                # Recompute age from pair_created_at
                if token.pair_created_at:
                    age = datetime.now(timezone.utc) - token.pair_created_at
                    token.age_minutes = age.total_seconds() / 60
                    token.age_hours = token.age_minutes / 60

                # Try Phase 2 live metrics from WalletActivity first
                live = get_current_metrics(db, token.token_address)
                has_wallet_data = live.get("total_unique_buyers", 0) > 0

                if has_wallet_data:
                    # Use real wallet-activity-based metrics
                    token.buys_5m = live["buys_5m"]
                    token.sells_5m = live["sells_5m"]
                    token.buy_ratio_5m = live["buy_ratio_5m"]
                    token.net_sol_flow_15m = live["net_sol_flow_15m"]
                    token.retention_5m = live["retention_5m"]
                    token.total_holders = live["total_holders"]

                    # Entity-adjusted buyers from clustering
                    token.entity_adjusted_buyers = recalculate_entity_adjusted_buyers(
                        db, token.token_address
                    )
                else:
                    # Fallback: estimate from HeliusEvent counts (pre-Phase 2 tokens)
                    total_swaps = db.query(func.count(HeliusEvent.id)).filter(
                        HeliusEvent.mint_address == token.token_address,
                        HeliusEvent.event_type == 'SWAP'
                    ).scalar() or 0

                    if total_swaps > 0 and (token.entity_adjusted_buyers or 1) <= 1:
                        estimated_buys = max(1, int(total_swaps * 0.6))
                        estimated_sells = max(0, total_swaps - estimated_buys)
                        token.buys_5m = estimated_buys
                        token.sells_5m = estimated_sells
                        token.entity_adjusted_buyers = max(estimated_buys, 1)
                        token.total_holders = max(estimated_buys - estimated_sells, 1)

                    # Recompute derived metrics from stored values
                    buys = token.buys_5m or 0
                    sells = token.sells_5m or 0
                    total_txs = buys + sells
                    if total_txs > 0:
                        token.buy_ratio_5m = (buys / total_txs) * 100
                    else:
                        token.buy_ratio_5m = 50

                    holders = max(token.entity_adjusted_buyers or 1, 1)
                    if holders > sells:
                        token.retention_5m = ((holders - sells) / holders) * 100
                    else:
                        token.retention_5m = 10

                # Holder concentration heuristic (shared logic)
                holders = max(token.entity_adjusted_buyers or 1, 1)
                if holders >= 50:
                    token.holder_concentration = max(10, 50 - (holders - 50) * 0.5)
                elif holders >= 20:
                    token.holder_concentration = max(20, 70 - (holders - 20) * 0.67)
                elif holders >= 10:
                    token.holder_concentration = max(30, 80 - (holders - 10) * 1)
                else:
                    token.holder_concentration = max(50, 100 - holders * 5)

                # Holder growth rate
                if token.age_minutes and token.age_minutes > 0:
                    token.holder_growth_rate = holders / token.age_minutes

            # === SCORE CALCULATION ===
            holder_growth_rate = 0
            if token.age_minutes and token.age_minutes > 0:
                holder_growth_rate = (token.entity_adjusted_buyers or 1) / token.age_minutes

            token_data = {
                'holder_concentration': token.holder_concentration or 0,
                'creator_cluster_pct': token.creator_cluster_pct or 0,
                'instant_buy_pct': token.instant_buy_pct or 0,
                'entity_adjusted_buyers': token.entity_adjusted_buyers or 1,
                'net_sol_flow_15m': token.net_sol_flow_15m or 0,
                'retention_5m': token.retention_5m or 100,
                'buys_5m': token.buys_5m or 0,
                'sells_5m': token.sells_5m or 0,
                'buy_ratio_5m': token.buy_ratio_5m or 50,
                'age_minutes': token.age_minutes or 0,
                'has_freeze_authority': False,
                'has_mint_authority': False,
                'last_update_minutes_ago': 0,
                'holder_growth_rate': holder_growth_rate,
                'total_holders': token.total_holders or 1,
            }

            scores = score_token(token_data)

            token.rug_risk_score = scores['rug_risk_score']
            token.momentum_score = scores['momentum_score']
            token.confidence_score = scores['confidence_score']
            token.explainability_data = scores['explainability_data']

            # Update tier based on new age
            token.tier_level = HeliusWebhookProcessor._determine_tier(token.age_minutes or 0)

            updated_count += 1
        except Exception as e:
            print(f"❌ Failed to recalculate {token.token_address}: {e}")
            continue

    db.commit()

    # Invalidate cached data after mass recalculation
    try:
        from core.redis_cache import cache
        cache.invalidate_pattern("signals:*")
        cache.delete("stats:overview")
    except Exception:
        pass

    return {
        "success": True,
        "tokens_processed": len(tokens),
        "tokens_updated": updated_count,
        "rebuild_metrics": rebuild_metrics
    }
