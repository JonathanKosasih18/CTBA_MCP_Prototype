# CTBA MCP Server

Lightweight MCP server exposing analytic tools over the CTBA dataset.

## Quick start
- Run the MCP server:
  - [server.py](server.py) (registers tools & prompts via [server_instance.py](server_instance.py))
- Example client:
  - [client.py](client.py) — shows SSE connection and LLM-driven agent loop.

## Features / Tools
Each tool is registered in [tools.py](tools.py) and most have companion prompts in [prompts.py](prompts.py).

- Planned visits (deduplicated / cleaned)
  - By customer: [`tools.fetch_deduplicated_visit_report`](tools.py) — prompt: [`prompts.generate_planned_visits_report_by_customer`](prompts.py)
  - By salesman: [`tools.fetch_visit_plans_by_salesman`](tools.py) — prompt: [`prompts.generate_planned_visits_report_by_salesman`](prompts.py)
  - By clinic: [`tools.fetch_visit_plans_by_clinic`](tools.py) — prompt: [`prompts.generate_planned_visits_report_by_clinic`](prompts.py)

- Transactions (deduplicated / cleaned)
  - By customer (acc_customers cid): [`tools.fetch_transaction_report_by_customer_name`](tools.py) — prompt: [`prompts.generate_transaction_report_by_customer`](prompts.py)
  - By salesman: [`tools.fetch_deduplicated_sales_report`](tools.py) — prompt: [`prompts.generate_transaction_report_by_salesmen`](prompts.py)
  - By product name: [`tools.fetch_transaction_report_by_product`](tools.py) — prompt: [`prompts.generate_transaction_report_by_product`](prompts.py)

- Reports & performance
  - Completed visit report counts by salesman: [`tools.fetch_report_counts_by_salesman`](tools.py) — prompt: [`prompts.generate_report_counts_by_salesman`](prompts.py)
  - Salesman performance scorecard (Plans vs Visits vs Transactions): [`tools.fetch_comprehensive_salesman_performance`](tools.py) — prompt: [`prompts.generate_comprehensive_salesman_report`](prompts.py)
  - Analyze a single salesman's visit effectiveness (visit reports vs transactions): [`tools.fetch_salesman_visit_history`](tools.py) — prompt: [`prompts.analyze_salesman_visit_effectiveness`](prompts.py)
  - Compare two salesmen's visit effectiveness (side‑by‑side): [`tools.fetch_salesman_comparison_data`](tools.py) — prompt: [`prompts.compare_salesmen_effectiveness`](prompts.py)

## Core components
- Tool implementations & registration: [tools.py](tools.py)
- Prompt registry: [prompts.py](prompts.py)
- MCP server instance: [server_instance.py](server_instance.py)
- Server entrypoint: [server.py](server.py)
- Example client & LLM integration: [client.py](client.py)
- DB engine config: [database.py](database.py)
- Normalization & identity helpers: [helpers.py](helpers.py) — key helpers: [`helpers.normalize_name`](helpers.py), [`helpers.resolve_salesman_identity`](helpers.py), [`helpers.load_official_users_map`](helpers.py), [`helpers.fetch_single_salesman_data`](helpers.py)

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
