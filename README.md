# CTBA MCP Server

Lightweight MCP server exposing analytic tools over your CTBA dataset.

## Quick start
- Start the MCP server:
  - [server.py](server.py) (registers tools & prompts via [server_instance.py](server_instance.py))
- Connect a client:
  - [client.py](client.py) provides an example client that connects over SSE.

## Features / Tools
Each tool is registered in [tools.py](tools.py) and typically has a companion prompt in [prompts.py](prompts.py).

- Planned visits (deduplicated / cleaned)
  - By customer: [`tools.fetch_deduplicated_visit_report`](tools.py) — prompt: [`prompts.generate_planned_visits_report_by_customer`](prompts.py)
  - By salesman: [`tools.fetch_visit_plans_by_salesman`](tools.py) — prompt: [`prompts.generate_planned_visits_report_by_salesman`](prompts.py)
  - By clinic: [`tools.fetch_visit_plans_by_clinic`](tools.py) — prompt: [`prompts.generate_planned_visits_report_by_clinic`](prompts.py)

- Transactions (deduplicated / cleaned)
  - By customer (acc_customers): [`tools.fetch_transaction_report_by_customer_name`](tools.py) — prompt: [`prompts.generate_transaction_report_by_customer`](prompts.py)
  - By salesman: [`tools.fetch_deduplicated_sales_report`](tools.py) — prompt: [`prompts.generate_transaction_report_by_salesmen`](prompts.py)
  - By product name: [`tools.fetch_transaction_report_by_product`](tools.py) — prompt: [`prompts.generate_transaction_report_by_product`](prompts.py)

- Reports & performance
  - Completed visit report counts by salesman: [`tools.fetch_report_counts_by_salesman`](tools.py) — prompt: [`prompts.generate_report_counts_by_salesman`](prompts.py)
  - Salesman performance scorecard (plans vs visits vs transactions): [`tools.fetch_comprehensive_salesman_performance`](tools.py) — prompt: [`prompts.generate_comprehensive_salesman_report`](prompts.py)
  - Analyze a single salesman's visit effectiveness (visit notes vs transactions): [`tools.fetch_salesman_visit_history`](tools.py) — prompt: [`prompts.analyze_salesman_visit_effectiveness`](prompts.py)

## Core components
- Tool implementations & registration: [tools.py](tools.py)
  - Uses SQLAlchemy [database.engine](database.py) and normalization helpers in [helpers.py](helpers.py).
- Prompts registry: [prompts.py](prompts.py)
- MCP server instance: [server_instance.py](server_instance.py)
- Server entrypoint: [server.py](server.py)
- Example client & LLM integration: [client.py](client.py)
- DB engine config: [database.py](database.py)
- String normalization & identity-resolution utilities: [helpers.py](helpers.py)

## Environment
- Configure DB and API keys via `.env` (loaded in [database.py](database.py) and [client.py](client.py)).

## Notes
- Tools perform entity resolution and fuzzy matching using helpers in [`helpers.py`](helpers.py).
- All reports return Markdown tables or plain text for easy display in the client.
- Scripts and raw SQL dumps are intentionally excluded (see `/scripts` and `*.sql`).