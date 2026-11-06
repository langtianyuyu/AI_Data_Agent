"""Offline = reference SQL/tool verification, NOT model accuracy."""
import argparse
import json
import tempfile
from pathlib import Path
from analyst.core import Analyst, ReadOnlySQL
from analyst.demo import create_demo
from analyst.providers import OpenAICompatible


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--langfuse', action='store_true')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.langfuse and not args.live:
        parser.error('Langfuse export requires --live')
    client = None
    if args.langfuse:
        from langfuse import get_client
        client = get_client()
    cases = json.loads(Path(__file__).with_name('cases.json').read_text())
    results = []
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/'demo.sqlite'
        create_demo(path)
        tool = ReadOnlySQL(path, {'customers', 'orders'})
        for case in cases:
            def evaluate():
                if args.live:
                    response = Analyst(tool, OpenAICompatible()).run(case['question'])
                    actual = response.get('result', {}).get('rows')
                else:
                    actual = tool.execute(case['sql']).rows
                    response = {'status': 'ok'}
                passed = response['status'] == 'ok' and actual == case['expected']
                return {'id': case['id'], 'passed': passed, 'actual': actual,
                        'expected': case['expected'], 'response': response}
            if client:
                with client.start_as_current_observation(as_type='span', name='data-agent-evaluation',
                                                         input={'question': case['question']}) as span:
                    result = evaluate()
                    span.update(output=result)
                    span.score_trace(name='exact_result_match', value=int(result['passed']))
            else:
                result = evaluate()
            results.append(result)
    report = {'mode': 'live-model' if args.live else 'reference-sql-only',
              'passed': sum(r['passed'] for r in results), 'total': len(results), 'cases': results}
    if client:
        client.flush()
    print(json.dumps(report, indent=2))
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2)+'\n')
    if not all(r['passed'] for r in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
