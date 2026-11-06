# Data Agent — Bounded SQL Analytics

An evaluated tool-layer prototype for natural-language analytics: generate SQL, execute within a database-enforced read boundary, repair failures within a fixed attempt budget, and return inspectable tables rather than unsupported narrative answers.

**Status:** offline verification passes; live model quality and Langfuse delivery have not been verified. This is a tutorial-derived portfolio extension, not a production deployment.

## Quick start

The new `analyst/` workflow uses Python 3.9+ standard library only. The original tutorial dependencies in `pyproject.toml` are needed only for the legacy workflow.

```sh
python3 -m analyst --init-demo
python3 -m analyst --sql "SELECT SUM(amount) FROM orders WHERE status='paid'"
python3 -m unittest discover -s tests -v
python3 -m evaluation.run
```

Expected paid revenue is `300.0`. The demo database is synthetic; initialization refuses to overwrite a file.

### Live model

Use a provider implementing the Chat Completions JSON-object interface. Configure a model supported by your provider; no model name or key is embedded in source. Environment variables are read from the process, not automatically from `.env`.

```sh
export ANALYST_MODEL='your-model-id'
export ANALYST_API_KEY='your-key'
# Optional: export ANALYST_BASE_URL='https://your-provider/v1'
python3 -m analyst --question 'Paid revenue by region, sorted by region ascending?'
python3 -m evaluation.run --live --output evaluation/live-results.json
```

Model/API compatibility, quality, and paid API calls require separate verification. A failed provider request stops the run instead of being reported as a successful answer.

## Architecture

```text
Question + allowlisted schema
        ↓
SQL generator (untrusted output)
        ↓
SQLite read-only connection + authorizer + execution budget
        ├── accepted → columns, rows, truncation flag, attempt history
        └── rejected → error feedback → bounded regeneration → failure
```

- Database opened using `mode=ro`, with `query_only` enabled.
- Table and SQL function allowlists, deny-by-default authorizer, single-statement execution.
- Defaults: 100 returned rows, one-second SQLite progress budget, two generation attempts.
- No Python execution or arbitrary ETL tool is exposed in the new workflow.
- Provider failures, rejected queries, and successful results have distinct statuses.
- Raw SQL and execution errors are retained for inspection. Execution success does not prove semantic correctness.

## Evaluation and observability

`evaluation/cases.json` contains five small synthetic reference cases: aggregation, counting, regional join, empty result, and refund filtering. Exact ordered row comparisons provide deterministic scores.

`python3 -m evaluation.run` checks reference SQL against the tool; it **does not measure model accuracy**. `--live` sends questions to a real model and evaluates its returned rows. The cases are a visible smoke suite, not a held-out benchmark. See `evaluation/reference-results.json` for the offline result.

Optional Langfuse integration exports one evaluation span per case and an `exact_result_match` trace score:

```sh
python3 -m pip install langfuse
export LANGFUSE_PUBLIC_KEY='your-public-key'
export LANGFUSE_SECRET_KEY='your-secret-key'
export LANGFUSE_BASE_URL='https://your-langfuse-host'
python3 -m evaluation.run --live --langfuse
```

The integration follows the [Langfuse Python SDK interface](https://python.reference.langfuse.com/langfuse). SDK installation and remote ingestion remain unverified. Export is explicit and includes questions, generated SQL, result rows and errors; use synthetic data for the portfolio demo. Token accounting, nested model/tool spans, and prompt/model comparison dashboards are not implemented.

## Design decisions and limits

See [architecture decisions](docs/DECISIONS.md). SQLite makes permissions and regression cases reproducible without credentials. PostgreSQL parity is not implemented in this new path. No claim is made of multi-tenant isolation, a process sandbox, production readiness or business impact. The progress handler limits SQLite virtual-machine work; it is not a hard process-level memory or wall-clock limit. Result row count does not bound individual cell size.

Next useful evidence: larger held-out questions, ambiguity/refusal cases, repeated model runs, cost/latency comparisons, and a separately permissioned PostgreSQL adapter.

## Provenance and contribution boundaries

Based on [anshlambagit/AI_Data_Agent](https://github.com/anshlambagit/AI_Data_Agent), upstream baseline commit `f5c96e900b7f89768de78614458967b2f7bf9712`. Original commit history and source remain intact. Original README is preserved at [docs/UPSTREAM_README.md](docs/UPSTREAM_README.md).

The original `agents/`, `Models/`, `utils/`, `main.py` and dependency files are tutorial code. They remain available for reference, and their execution paths have not been hardened by this extension. Run `python3 -m analyst` for the new implementation.

The portfolio extension adds `analyst/`, `evaluation/`, `tests/`, CI, and design documentation. These additions were implemented with AI coding assistance; repository ownership alone does not demonstrate mastery. Personal ownership should be supported by explaining, reviewing and extending these decisions. No new license or relicensing claim is added for upstream code.
