# Vehicle analysis

## Boundary

`VehicleAnalyzer` accepts an already-filtered `NormalizedListing` and calls only `AIManager`; Groq and Gemini remain interchangeable provider adapters. `build_vehicle_analysis_evidence` sends canonical identity, selected structured facts, title/description, price context, seller type, location, and a small whitelist of useful raw vehicle attributes. It excludes images, arbitrary raw payloads, URLs, state, credentials, and irrelevant metadata.

## Evidence semantics

The response is the canonical Pydantic `VehicleAnalysis` model. `vehicle.structured_source` must exactly reproduce normalized make, model, mileage, and power. `interpreted_from_listing` holds only facts explicitly supported by title or description. The analyzer rejects an output that changes structured source facts, while conflicts are represented as evidence-backed risk flags.

Current unresolved faults, completed repairs, routine maintenance, seller claims, positive signals, risks, and relevant missing information are independent categories. A seller statement such as “technically perfect” remains a seller claim; a completed brake replacement is not a current brake fault. Unknown accident status, TÜV, ownership, and service information remain null or explicit missing-information items rather than assumptions.

## Condition, risk, and confidence

`overall_condition` is one of `excellent`, `good`, `average`, `poor`, `very_poor`, or `unknown`, based solely on listing evidence. `risk_level` is `low`, `medium`, `high`, `very_high`, or `unknown`; high levels require at least one evidence-backed risk flag. `analysis_confidence` is bounded from 0 to 1 and measures confidence in the analysis of the available evidence, not the probability that the car is good.

## Deliberate exclusions

Step 7 is text and structured-data analysis only. It does not download or analyze images, estimate repair costs, calculate parts/labour, value the vehicle, estimate resale, calculate profit or ROI, score candidates, or send runtime reports. Those remain later approved stages.


## Verification note

The bounded sanitized live check correctly separated stated front-brake and battery replacements from current faults. It also returned several relevant unknowns because the fixture lacks TÜV, accident, ownership, and broader maintenance detail. This is expected: listing analysis reports evidence limits rather than filling them with assumptions; downstream repair and valuation work must not treat missing data as a vehicle defect or a monetary estimate.
