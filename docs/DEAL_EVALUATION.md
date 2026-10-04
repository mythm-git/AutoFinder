# Deterministic Deal Evaluation

## Purpose

Step 10 turns validated financial scenarios, evidence-based vehicle risk, and separate confidence values into an explainable decision-support result. It never instructs a purchase: even STRONG_CANDIDATE requires seller contact, document checks, negotiation, inspection, and human approval.

DealEvaluator is pure local Python. It makes no AI, provider, marketplace, or web call and does not change upstream inputs.

## Decisions

- REJECT: current evidence fails a hard financial or configured very-high-risk gate.
- REVIEW: the expected financial case passes, but meaningful downside, risk, or uncertainty prevents a strong classification.
- STRONG_CANDIDATE: the expected case is attractive and every configured strong requirement passes. This is not “safe to buy.”

## Fixed rule flow

1. Reject when expected profit is non-positive.
2. Reject when expected ROI is below configured minimum (initially 20%). ROI is already based on full investment from Step 9.
3. Reject very-high vehicle risk when enabled in configuration.
4. Otherwise, check strong requirements independently: conservative ROI, risk level, analysis confidence, repair confidence, and valuation confidence.
5. Return STRONG_CANDIDATE only when every strong requirement passes; otherwise return REVIEW.

Optimistic ROI is context only and can never rescue a failed expected-profit or expected-ROI gate. The conservative scenario measures downside quality: a negative conservative ROI with a profitable expected scenario is REVIEW, not strong.

## Configuration

config/autofinder.yaml defines the non-secret deal_evaluation policy:

- minimum_expected_roi_percent: 20.0
- minimum_conservative_roi_for_strong_percent: 0.0
- minimum_analysis_confidence: 0.60
- minimum_repair_confidence: 0.55
- minimum_valuation_confidence: 0.60
- maximum_risk_for_strong: medium (only low and medium are eligible)
- reject_very_high_risk: true

Confidence values are evaluated separately—there is no hidden weighted score or meaningless combined average. High and unknown risk are review-only; very_high is a configurable hard reject.

## Traceability

DealEvaluation returns stable machine-readable blocking reasons and non-blocking warnings, alongside expected/conservative/optimistic ROI, expected profit and investment, risk, each confidence, valuation source, and rules version. Its financially_eligible field means that the expected-profit and expected-ROI gates passed; a separate hard risk rule can still reject the deal.

Current AI_ESTIMATE valuation is retained as the valuation_ai_only warning/context. It is not automatically rejected. Later mobile.de comparable evidence can introduce a new valuation source and intentionally revised policy; Step 10 does not implement that integration.
