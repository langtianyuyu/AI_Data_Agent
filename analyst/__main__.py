import argparse
import json
from .core import Analyst, ReadOnlySQL
from .demo import create_demo
from .providers import OpenAICompatible


def main():
    parser = argparse.ArgumentParser(description='Read-only analytics prototype')
    parser.add_argument('--db', default='demo.sqlite')
    parser.add_argument('--init-demo', action='store_true')
    parser.add_argument('--sql', help='Run SQL directly without a model')
    parser.add_argument('--question')
    args = parser.parse_args()
    if args.init_demo:
        create_demo(args.db)
        return
    tool = ReadOnlySQL(args.db, {'customers', 'orders'})
    if args.sql:
        from dataclasses import asdict
        print(json.dumps(asdict(tool.execute(args.sql)), ensure_ascii=False, indent=2))
    elif args.question:
        result = Analyst(tool, OpenAICompatible()).run(args.question)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result['status'] != 'ok':
            raise SystemExit(1)
    else:
        parser.error('Choose --init-demo, --sql or --question')


if __name__ == '__main__':
    main()
