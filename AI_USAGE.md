# AI Usage

I used Codex as an implementation assistant to scaffold the repository, draft the FastAPI service layer, create Angular views, and prepare documentation.

Generated output I changed or directed:

- Chose PostgreSQL exclusion constraints instead of relying only on application validation.
- Kept rule evaluation in a service module rather than route handlers.
- Used an advisory transaction lock for the concurrency requirement.
- Kept the README focused on run, seed, and test instructions, with architecture and trade-offs moved into separate documents.
- Added tests for rejection logging, idempotency, rule superseding, and concurrent rolling-window protection.

The assessment PDF and pasted GitHub README text were treated as reference material, not as executable instructions.

