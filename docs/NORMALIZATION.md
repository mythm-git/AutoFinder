# Canonical listing normalization

Normalization is the source-adapter boundary between collected marketplace payloads and AutoFinder business logic. It runs only after early deduplication, so listings already seen are not normalized again.

`ApifyKleinanzeigenNormalizer` currently maps the verified Apify fields `id`, `title`, `description`, `url`, `price`, `currency`, `location.city`, `location.postalCode`, `images`, `vehicle.make`, `vehicle.model`, `vehicle.mileage`, `vehicle.powerPs`, and `seller.type`. These become a `NormalizedListing` with nested identity, location, vehicle, seller, media, and source-evidence models.

The normalizer makes no semantic interpretation. A title such as “Golf 1.6 TÜV neu” remains text; it does not create inferred make, repairs, or condition facts. Optional unavailable data is represented by `None`, never invented values, and produces a non-fatal normalization warning where useful. Invalid structured optional values are likewise unavailable and warned about.

The normalized model retains a deep-copied lossless raw payload with provider and marketplace provenance. It preserves the source collection timestamp and adds an aware UTC normalization timestamp. Downstream modules—including `BasicDealFilter`—use only canonical fields and do not know Apify-specific paths. This lets a later direct Kleinanzeigen collector provide the same normalized contract without rewriting business logic.
