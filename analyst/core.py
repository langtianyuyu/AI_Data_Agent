"""Database permissions, rather than model judgment, enforce the tool boundary."""
import json
import sqlite3
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Protocol


class QueryRejected(ValueError):
    pass


@dataclass
class QueryResult:
    columns: list
    rows: list
    truncated: bool


class ReadOnlySQL:
    def __init__(self, path, allowed_tables, max_rows=100, timeout_seconds=1.0):
        self.path = Path(path).resolve()
        self.allowed_tables = frozenset(allowed_tables)
        if not self.allowed_tables or max_rows < 1 or timeout_seconds <= 0:
            raise ValueError('Provide tables and positive execution bounds')
        self.max_rows = max_rows
        self.timeout_seconds = timeout_seconds

    def schema(self):
        # Only explicitly selected tables are exposed to the model.
        with sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True) as conn:
            rows = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table'").fetchall()
        return '\n'.join(sql for name, sql in rows if name in self.allowed_tables)

    def execute(self, sql):
        if not isinstance(sql, str) or len(sql) > 20000:
            raise QueryRejected('Invalid SQL input')
        conn = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)
        try:
            conn.execute('PRAGMA query_only=ON')
            deadline = time.monotonic() + self.timeout_seconds
            conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            safe_functions = {'count', 'sum', 'avg', 'min', 'max', 'round', 'coalesce',
                              'lower', 'upper', 'length', 'abs', 'strftime', 'date'}

            def authorize(action, arg1, arg2, database, source):
                if action == sqlite3.SQLITE_SELECT:
                    return sqlite3.SQLITE_OK
                if action == sqlite3.SQLITE_READ:
                    return sqlite3.SQLITE_OK if database in ('main', None) and arg1 in self.allowed_tables else sqlite3.SQLITE_DENY
                if action == sqlite3.SQLITE_FUNCTION:
                    return sqlite3.SQLITE_OK if arg2 in safe_functions else sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_DENY

            conn.set_authorizer(authorize)
            cursor = conn.execute(sql)  # sqlite rejects multiple statements.
            if cursor.description is None:
                raise QueryRejected('A tabular query is required')
            rows = cursor.fetchmany(self.max_rows + 1)
            return QueryResult([col[0] for col in cursor.description],
                               [list(row) for row in rows[:self.max_rows]],
                               len(rows) > self.max_rows)
        except (sqlite3.Error, sqlite3.Warning) as exc:
            raise QueryRejected(str(exc)) from exc
        finally:
            conn.close()


class Generator(Protocol):
    def generate(self, question, schema, feedback): ...


class Analyst:
    def __init__(self, tool, generator, max_attempts=2):
        if not 1 <= max_attempts <= 3:
            raise ValueError('max_attempts must be between 1 and 3')
        self.tool, self.generator, self.max_attempts = tool, generator, max_attempts

    def run(self, question):
        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            raise ValueError('Question must contain 1–4000 characters')
        attempts, feedback = [], ''
        started = time.monotonic()
        schema = self.tool.schema()
        for _ in range(self.max_attempts):
            try:
                sql = self.generator.generate(question, schema, feedback)
            except Exception:
                # Provider failures are not SQL errors and are not blindly retried.
                return {'status': 'provider_error', 'attempts': attempts,
                        'latency_ms': round((time.monotonic()-started)*1000, 2)}
            try:
                result = self.tool.execute(sql)
                attempts.append({'sql': sql, 'status': 'ok'})
                return {'status': 'ok', 'result': asdict(result), 'attempts': attempts,
                        'latency_ms': round((time.monotonic()-started)*1000, 2)}
            except QueryRejected as exc:
                feedback = str(exc)
                attempts.append({'sql': sql, 'status': 'rejected', 'error': feedback})
        return {'status': 'failed', 'attempts': attempts,
                'latency_ms': round((time.monotonic()-started)*1000, 2)}
