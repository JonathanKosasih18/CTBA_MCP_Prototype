# CTBA MCP Server

Lightweight MCP server exposing analytic tools over the CTBA dataset.

## Quick start
- Run the MCP server:
  - [server.py](server.py) (registers tools & prompts via [server_instance.py](server_instance.py))
- Example client:
  - [client.py](client.py) — shows SSE connection and LLM-driven agent loop.

## Implemented features
The server now includes the following implemented analytics tools (deduped/cleaned using normalization helpers in [helpers.py](helpers.py)):

- Planned visits (grouped & deduplicated)
  - By customer (group by custcode from customers): [`tools.fetch_deduplicated_visit_report`](tools.py)
  - By salesman (group by username from users): [`tools.fetch_visit_plans_by_salesman`](tools.py)
  - By clinic (group by clinicname from clinics): [`tools.fetch_visit_plans_by_clinic`](tools.py)

- Transactions (grouped & deduplicated)
  - By customer (group by cid from acc_customers): [`tools.fetch_transaction_report_by_customer_name`](tools.py)
  - By salesman (group by username from users): [`tools.fetch_deduplicated_sales_report`](tools.py)
  - By product name (group by prodname from products): [`tools.fetch_transaction_report_by_product`](tools.py)

- Reports & performance
  - Completed visit report counts by salesman: [`tools.fetch_report_counts_by_salesman`](tools.py)
  - Salesman performance (Plans vs Visits vs Transactions): [`tools.fetch_comprehensive_salesman_performance`](tools.py)
  - Analyze visit effectiveness for a single salesman (visit reports vs transactions): [`tools.fetch_salesman_visit_history`](tools.py)
  - Compare two salesmen (side‑by‑side visit reports vs transactions): [`tools.fetch_salesman_comparison_data`](tools.py)
  - Time‑range leaderboard (highest visit count, transaction count, and visit→transaction ratio): [`tools.fetch_best_performers`](tools.py) — accepts start_date and end_date

## Core components
- Tool implementations & registration: [tools.py](tools.py)
- Prompt registry: [prompts.py](prompts.py)
- MCP server instance: [server_instance.py](server_instance.py)
- Server entrypoint: [server.py](server.py)
- Example client & LLM integration: [client.py](client.py)
- DB engine config: [database.py](database.py)
- Normalization & identity helpers: [helpers.py](helpers.py) — key helpers: [`helpers.normalize_name`](helpers.py), [`helpers.resolve_salesman_identity`](helpers.py), [`helpers.load_official_users_map`](helpers.py), [`helpers.fetch_single_salesman_data`](helpers.py)

## API / FastAPI integration
A minimal FastAPI integration is included with a sample root endpoint defined in [server.py](server.py) (returns a health message). The MCP SSE app is mounted at /mcp via the server entrypoint.

The FastAPI integration is still currently under development

## Output format
- Tools return human-readable Markdown tables or plain text summary logs suitable for LLM consumption and display in the example client.

## Environment
- Configure DB and API keys via `.env` (loaded by [database.py](database.py) and [client.py](client.py)):
  - DB_USER, DB_PASSWORD, DB_HOST, DB_NAME
  - OPENAI_API_KEY (used by [client.py](client.py))

## Notes
- Deduplication & entity resolution rely on fuzzy matching and normalization helpers in [helpers.py](helpers.py).
- Reports group by canonical identifiers (customer custcode / acc_customers.cid, users.username, clinics.clinicname, products.prodname) after cleaning and deduplication.
- Scripts and raw SQL dumps are intentionally excluded from feature documentation (see /scripts and *.sql files in repo).
