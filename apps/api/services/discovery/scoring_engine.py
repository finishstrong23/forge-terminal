"""
Forge Terminal Scoring Engine (ported verbatim from Pump.Fair)

Calculates:
1. Rug Risk Score (0-100, lower is better)
2. Momentum Score (0-100, higher is better)
3. Confidence Score (0-100)
4. Explainability data
"""
from typing import Dict, List, Tuple
from datetime import datetime, timezone
import math


class PumpFairScorer:
    PROGRAM_ACCOUNTS = {
        "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
        "Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1",
    }

    def calculate_all_scores(self, token_data: Dict) -> Dict:
        rug_risk = self.calculate_rug_risk(token_data)
        momentum = self.calculate_momentum(token_data)
        confidence = self.calculate_confidence(token_data)
        explainability = self.generate_explainability(token_data, rug_risk, momentum, confidence)

        return {
            "rug_risk_score": round(rug_risk, 2),
            "momentum_score": round(momentum, 2),
            "confidence_score": round(confidence, 2),
            "explainability_data": explainability,
        }

    def calculate_rug_risk(self, token_data: Dict) -> float:
        risk_score = 0.0

        entity_adjusted_buyers = token_data.get("entity_adjusted_buyers", 0)
        total_holders = token_data.get("total_holders", entity_adjusted_buyers)
        holders = max(entity_adjusted_buyers, total_holders)

        if holders < 3:
            risk_score += 30
        elif holders < 5:
            risk_score += 25
        elif holders < 8:
            risk_score += 20
        elif holders < 12:
            risk_score += 15
        elif holders < 20:
            risk_score += 10
        elif holders < 30:
            risk_score += 5
        elif holders < 50:
            risk_score += 2

        holder_concentration = token_data.get("holder_concentration", 0)
        if holder_concentration > 80:
            risk_score += 30
        elif holder_concentration > 65:
            risk_score += 25
        elif holder_concentration > 50:
            risk_score += 20
        elif holder_concentration > 40:
            risk_score += 12
        elif holder_concentration > 30:
            risk_score += 6
        elif holder_concentration > 20:
            risk_score += 2

        buy_ratio_5m = token_data.get("buy_ratio_5m", 50)
        sells_5m = token_data.get("sells_5m", 0) if "sells_5m" in token_data else 0
        buys_5m = token_data.get("buys_5m", 0)
        total_txs = buys_5m + sells_5m

        if total_txs >= 3:
            if buy_ratio_5m < 20:
                risk_score += 20
            elif buy_ratio_5m < 35:
                risk_score += 15
            elif buy_ratio_5m < 45:
                risk_score += 10
            elif buy_ratio_5m < 50:
                risk_score += 5
        else:
            risk_score += 5

        age_minutes = token_data.get("age_minutes", 0)
        if age_minutes < 1:
            risk_score += 10
        elif age_minutes < 3:
            risk_score += 7
        elif age_minutes < 5:
            risk_score += 4
        elif age_minutes < 10:
            risk_score += 2

        creator_cluster_pct = token_data.get("creator_cluster_pct", 0)
        if creator_cluster_pct > 40:
            risk_score += 5
        elif creator_cluster_pct > 25:
            risk_score += 3
        elif creator_cluster_pct > 10:
            risk_score += 1

        instant_buy_pct = token_data.get("instant_buy_pct", 0)
        if instant_buy_pct > 50:
            risk_score += 5
        elif instant_buy_pct > 30:
            risk_score += 3
        elif instant_buy_pct > 15:
            risk_score += 1

        if token_data.get("has_freeze_authority", False):
            risk_score += 5
        if token_data.get("has_mint_authority", False):
            risk_score += 3

        return min(risk_score, 100)

    def calculate_momentum(self, token_data: Dict) -> float:
        momentum_score = 0.0

        buys_5m = token_data.get("buys_5m", 0)
        age_minutes = token_data.get("age_minutes", 0)

        window = min(age_minutes, 5) if age_minutes > 0 else 5
        buy_velocity = buys_5m / max(window, 0.5)

        if buy_velocity >= 8:
            momentum_score += 30
        elif buy_velocity >= 5:
            momentum_score += 25
        elif buy_velocity >= 3:
            momentum_score += 20
        elif buy_velocity >= 2:
            momentum_score += 15
        elif buy_velocity >= 1:
            momentum_score += 10
        elif buy_velocity >= 0.5:
            momentum_score += 5
        elif buys_5m >= 1:
            momentum_score += 2

        holder_growth_rate = token_data.get("holder_growth_rate", 0)
        entity_adjusted_buyers = token_data.get("entity_adjusted_buyers", 0)

        if holder_growth_rate >= 5:
            momentum_score += 30
        elif holder_growth_rate >= 3:
            momentum_score += 25
        elif holder_growth_rate >= 2:
            momentum_score += 20
        elif holder_growth_rate >= 1:
            momentum_score += 15
        elif holder_growth_rate >= 0.5:
            momentum_score += 10
        elif holder_growth_rate >= 0.2:
            momentum_score += 5
        elif entity_adjusted_buyers >= 5:
            momentum_score += 3

        retention_5m = token_data.get("retention_5m", 0)
        if retention_5m >= 90:
            momentum_score += 20
        elif retention_5m >= 80:
            momentum_score += 17
        elif retention_5m >= 70:
            momentum_score += 14
        elif retention_5m >= 60:
            momentum_score += 10
        elif retention_5m >= 50:
            momentum_score += 6
        elif retention_5m >= 40:
            momentum_score += 3

        net_sol_flow = token_data.get("net_sol_flow_15m", 0)
        if net_sol_flow > 10:
            momentum_score += 10
        elif net_sol_flow > 5:
            momentum_score += 8
        elif net_sol_flow > 2:
            momentum_score += 6
        elif net_sol_flow > 0.5:
            momentum_score += 4
        elif net_sol_flow > 0:
            momentum_score += 2

        buy_ratio_5m = token_data.get("buy_ratio_5m", 0)
        if buy_ratio_5m >= 85:
            momentum_score += 10
        elif buy_ratio_5m >= 75:
            momentum_score += 8
        elif buy_ratio_5m >= 65:
            momentum_score += 6
        elif buy_ratio_5m >= 55:
            momentum_score += 4
        elif buy_ratio_5m >= 50:
            momentum_score += 2

        return min(momentum_score, 100)

    def calculate_confidence(self, token_data: Dict) -> float:
        confidence_score = 0.0

        data_points = 0
        max_data_points = 6

        if token_data.get("entity_adjusted_buyers", 0) > 0:
            data_points += 1
        if token_data.get("buys_5m", 0) > 0:
            data_points += 1
        if token_data.get("retention_5m") is not None:
            data_points += 1
        if token_data.get("holder_concentration", 0) > 0:
            data_points += 1
        if token_data.get("buy_ratio_5m", 0) > 0:
            data_points += 1
        if token_data.get("age_minutes", 0) > 0:
            data_points += 1

        completeness_pct = (data_points / max_data_points) * 100
        confidence_score += (completeness_pct / 100) * 30

        entity_adjusted_buyers = token_data.get("entity_adjusted_buyers", 0)
        if entity_adjusted_buyers >= 30:
            confidence_score += 35
        elif entity_adjusted_buyers >= 20:
            confidence_score += 30
        elif entity_adjusted_buyers >= 15:
            confidence_score += 25
        elif entity_adjusted_buyers >= 10:
            confidence_score += 20
        elif entity_adjusted_buyers >= 7:
            confidence_score += 14
        elif entity_adjusted_buyers >= 5:
            confidence_score += 10
        elif entity_adjusted_buyers >= 3:
            confidence_score += 5

        age_minutes = token_data.get("age_minutes", 0)
        if 5 <= age_minutes <= 30:
            confidence_score += 25
        elif 3 <= age_minutes < 5:
            confidence_score += 18
        elif 30 < age_minutes <= 60:
            confidence_score += 18
        elif 1 <= age_minutes < 3:
            confidence_score += 10
        elif age_minutes < 1:
            confidence_score += 3
        elif age_minutes > 60:
            confidence_score += 12

        last_update_minutes = token_data.get("last_update_minutes_ago", 0)
        if last_update_minutes < 2:
            confidence_score += 10
        elif last_update_minutes < 5:
            confidence_score += 7
        elif last_update_minutes < 10:
            confidence_score += 4

        return min(confidence_score, 100)

    def generate_explainability(
        self, token_data: Dict, rug_risk: float, momentum: float, confidence: float
    ) -> Dict:
        promising_reasons = []
        risk_reasons = []
        upgrade_suggestions = []

        entity_adjusted_buyers = token_data.get("entity_adjusted_buyers", 0)
        total_holders = token_data.get("total_holders", entity_adjusted_buyers)
        holders = max(entity_adjusted_buyers, total_holders)
        buys_5m = token_data.get("buys_5m", 0)
        sells_5m = token_data.get("sells_5m", 0) if "sells_5m" in token_data else 0
        buy_ratio_5m = token_data.get("buy_ratio_5m", 0)
        retention = token_data.get("retention_5m", 0)
        net_sol_flow = token_data.get("net_sol_flow_15m", 0)
        holder_growth = token_data.get("holder_growth_rate", 0)
        holder_conc = token_data.get("holder_concentration", 0)
        age_minutes = token_data.get("age_minutes", 0)

        if buys_5m >= 10:
            promising_reasons.append(f"High buy pressure: {buys_5m} buys recently")
        elif buys_5m >= 5:
            promising_reasons.append(f"Active buying: {buys_5m} buys recently")

        if holders >= 20:
            promising_reasons.append(f"Growing community: {holders} unique holders")

        if retention >= 80:
            promising_reasons.append(f"{retention:.0f}% of buyers still holding (strong conviction)")
        elif retention >= 65:
            promising_reasons.append(f"{retention:.0f}% of buyers still holding")

        if buy_ratio_5m >= 75 and buys_5m + sells_5m >= 3:
            promising_reasons.append(f"Bullish sentiment: {buy_ratio_5m:.0f}% buys vs sells")

        if holder_growth >= 2:
            promising_reasons.append(f"Fast organic growth: {holder_growth:.1f} new holders/min")

        if net_sol_flow > 2:
            promising_reasons.append(f"Strong inflow: +{net_sol_flow:.1f} SOL net")

        if holder_conc > 0 and holder_conc < 30:
            promising_reasons.append(f"Well distributed: top holders own only {holder_conc:.0f}%")

        if not promising_reasons:
            if buys_5m > 0:
                promising_reasons.append(f"Active: {buys_5m} recent buys detected")
            elif holders >= 1:
                promising_reasons.append(f"New token with {holders} holder(s)")

        if holders < 5:
            risk_reasons.append(f"Only {holders} unique holder(s) (easy to manipulate)")
        elif holders < 10:
            risk_reasons.append(f"Only {holders} holders (still early)")

        if holder_conc > 60:
            risk_reasons.append(f"Concentrated holdings: top holders own {holder_conc:.0f}%")
        elif holder_conc > 40:
            risk_reasons.append(f"Moderate concentration: top holders own {holder_conc:.0f}%")

        if buy_ratio_5m < 40 and buys_5m + sells_5m >= 3:
            risk_reasons.append(f"Sell pressure: only {buy_ratio_5m:.0f}% of transactions are buys")

        if retention < 50 and retention > 0 and holders > 3:
            risk_reasons.append(f"Low retention: only {retention:.0f}% still holding")

        if age_minutes < 2:
            risk_reasons.append(f"Very new token ({age_minutes:.0f} min old) - limited data")

        creator_cluster = token_data.get("creator_cluster_pct", 0)
        if creator_cluster > 20:
            risk_reasons.append(f"Creator cluster holds {creator_cluster:.0f}% of supply")

        if token_data.get("has_freeze_authority"):
            risk_reasons.append("Token has freeze authority enabled")
        if token_data.get("has_mint_authority"):
            risk_reasons.append("Token has mint authority enabled")

        instant_buy_pct = token_data.get("instant_buy_pct", 0)
        if instant_buy_pct > 30:
            risk_reasons.append(f"{instant_buy_pct:.0f}% of buyers were instant (likely bots)")

        if confidence < 70:
            upgrade_suggestions.append(f"Watch for more data (confidence: {confidence:.0f}/100)")

        if holders < 15:
            upgrade_suggestions.append(f"Wait for 15+ holders (currently {holders})")

        if age_minutes < 5:
            upgrade_suggestions.append("Token very young - check back in 5 min")

        if net_sol_flow < 1 and buys_5m > 0:
            upgrade_suggestions.append("Watch for stronger net SOL inflow")

        if buy_ratio_5m < 60 and buys_5m + sells_5m >= 3:
            upgrade_suggestions.append("Buy ratio could improve (currently below 60%)")

        return {
            "promising": promising_reasons[:3],
            "risks": risk_reasons[:2],
            "upgrades": upgrade_suggestions[:2]
            if upgrade_suggestions
            else ["Looking strong - continue monitoring"],
        }

    def should_send_alert(self, rug_risk: float, momentum: float, confidence: float) -> Tuple[bool, str]:
        if rug_risk > 40:
            return False, f"Rug risk too high ({rug_risk:.0f}/100)"
        if momentum < 60:
            return False, f"Momentum too low ({momentum:.0f}/100)"
        if confidence < 70:
            return False, f"Confidence too low ({confidence:.0f}/100)"
        return True, "Strong signal - high momentum + high confidence + low rug risk"


scorer = PumpFairScorer()


def score_token(token_data: Dict) -> Dict:
    return scorer.calculate_all_scores(token_data)
