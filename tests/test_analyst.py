import sqlite3
import tempfile
import unittest
from pathlib import Path
from analyst.core import Analyst, QueryRejected, ReadOnlySQL
from analyst.demo import create_demo


class SequenceGenerator:
    def __init__(self, queries):
        self.queries = iter(queries)
        self.feedback = []

    def generate(self, question, schema, feedback):
        self.feedback.append(feedback)
        return next(self.queries)


class AnalystTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'demo.sqlite'
        create_demo(self.path)
        self.tool = ReadOnlySQL(self.path, {'customers', 'orders'}, max_rows=2)

    def tearDown(self):
        self.tmp.cleanup()

    def test_correct_aggregation(self):
        result = self.tool.execute("SELECT SUM(amount) FROM orders WHERE status='paid'")
        self.assertEqual(result.rows, [[300.0]])

    def test_authorization_boundaries(self):
        forbidden = ["DELETE FROM orders", "DROP TABLE orders", "PRAGMA table_info(orders)",
                     "ATTACH DATABASE ':memory:' AS other", "SELECT * FROM sqlite_master",
                     "SELECT load_extension('x')", "SELECT 1; DELETE FROM orders",
                     "WITH x AS (SELECT 1) DELETE FROM orders",
                     "SELECT randomblob(100000000)"]
        for sql in forbidden:
            with self.subTest(sql=sql), self.assertRaises(QueryRejected):
                self.tool.execute(sql)
        self.assertEqual(self.tool.execute('SELECT COUNT(*) FROM orders').rows, [[4]])

    def test_private_table(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute('CREATE TABLE secrets (token TEXT)')
        self.assertNotIn('secrets', self.tool.schema())
        with self.assertRaises(QueryRejected):
            self.tool.execute('SELECT * FROM secrets')

    def test_truncation(self):
        self.assertTrue(self.tool.execute('SELECT * FROM orders').truncated)

    def test_bounded_repair(self):
        generator = SequenceGenerator(['SELECT missing FROM orders', 'SELECT COUNT(*) FROM orders'])
        result = Analyst(self.tool, generator).run('How many orders?')
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(len(result['attempts']), 2)
        self.assertIn('missing', generator.feedback[1])

    def test_stops_on_persistent_failure(self):
        result = Analyst(self.tool, SequenceGenerator(['DELETE FROM orders']*2)).run('Delete')
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(len(result['attempts']), 2)

    def test_provider_failure(self):
        result = Analyst(self.tool, SequenceGenerator([])).run('Count')
        self.assertEqual(result['status'], 'provider_error')

    def test_missing_database_not_created(self):
        with self.assertRaises(sqlite3.Error):
            ReadOnlySQL(self.path.parent/'absent.sqlite', {'orders'}).schema()


if __name__ == '__main__':
    unittest.main()
