# Decisions

## Rule Versioning

Chosen: each formulary rule is a dated period with `effective_from` and nullable `effective_to`. PostgreSQL prevents overlapping periods for the same medicine with an exclusion constraint.

Considered: storing only the current rule plus an audit log. That would make current reads simple, but backdated dispenses would require reconstructing state from events.

Trade-off: period queries are slightly more complex, and superseding a rule must carefully close the previous period. The benefit is direct historical lookup and database-level integrity.

## Concurrent Dispense Protection

Chosen: use `pg_advisory_xact_lock` per `(patient_ref, medicine)` while checking and writing the rolling 30-day total.

Considered: serializable isolation for every dispense. It would also protect the invariant, but it broadens contention and requires retry handling for serialization failures.

Trade-off: same patient and medicine requests serialize. Different patients or medicines proceed concurrently, keeping the lock scope narrow and explainable.

## Pagination

Chosen: offset pagination with bounded `page_size` for the required list views.

Considered: cursor pagination. Cursor pagination is stronger at very large scale and for changing datasets, but it complicates simple page navigation in the assessment UI.

Trade-off: deep pages can become slower. The seeded dataset is small enough for offset pagination, and indexes keep first-page queries under the target.

## Error Contract

Chosen: errors return `{ error, message, details[] }`, where each detail has `field`, `code`, `message`, and optional `meta`.

Considered: plain strings or FastAPI's default validation shape. Plain strings are not field-addressable, and default validation does not represent business-rule failures cleanly.

Trade-off: the backend must construct structured errors for domain failures. The frontend can reliably attach multiple rejection reasons to fields.

## Indexing Strategy

Chosen: indexes support the required access patterns: medicine code/name search, rule lookup by medicine and date, dispense ledger filtering, and newest-first listing.

Considered: adding trigram indexes for fuzzy search. That is useful for production search, but the requirement is partial name or code search on 500 seeded medicines.

Trade-off: simple indexes avoid extra extension complexity. The first-page performance target is validated with the seeded dataset using the README timing commands.

