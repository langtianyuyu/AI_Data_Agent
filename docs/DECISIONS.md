# Architecture decisions

## 1. A bounded workflow before multi-agent orchestration

A single SQL task does not currently justify multiple cooperating agents. Generation, permission checking and execution are separate interfaces. Add orchestration only when experiments show a benefit for a concrete task.

## 2. Permissions belong in the execution layer

A model's safety judgment is not authorization. The new SQLite adapter denies writes, attached databases, schema catalog access and functions outside an explicit allowlist. Each attempt gets a fresh connection. This is a database boundary, not a Python or operating-system sandbox.

## 3. Repair is limited

SQL rejection becomes feedback for at most two default attempts. Provider errors stop immediately. This prevents unbounded repair loops; it does not guarantee a successful repair or correct interpretation. A future version should distinguish non-retryable policy violations from repairable syntax errors.

## 4. Validate values rather than generated wording

Reference queries have expected result rows. Exact result matching is interpretable, but ordering, floating-point tolerance, ambiguity and equivalent result representations need a more sophisticated evaluator as the dataset expands. The present five visible cases are smoke checks only.

## 5. Preserve an inspectable result

Return the actual columns and rows with SQL attempt history. Do not add a narrative generation stage before its factual accuracy can be evaluated. Do not label the prototype production-grade without deployment and operational evidence.
