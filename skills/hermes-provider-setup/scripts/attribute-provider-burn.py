#!/usr/bin/env python3
"""Attribute provider burn per model from Hermes' local ledger (state.db).

Answers "where did my subscription quota go?": /usage reports percentages for
the whole account, session_model_usage says which model spent it. The ledger is
opened read-only — it is hundreds of MB and shared with live sessions.

  scripts/attribute-provider-burn.py --since 2026-09-26T16:39
  scripts/attribute-provider-burn.py --since 2026-09-26T16:39 --provider opencode-go
  scripts/attribute-provider-burn.py --since 2026-09-26T16:39 --prices prices.json

prices.json maps a model onto the provider's own rows, USD per 1M tokens:
  {"deepseek-v4.1-flash": {"in": 0.15, "out": 0.60, "cache_read": 0.003}}
Name the peak/off-peak basis of the rows you feed in. Plan providers report
estimated_cost_usd = 0 ("no catalogue price"), so the dollar column comes from
these rows, never from the ledger's own estimate.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sqlite3
import sys


def to_epoch(value: str) -> float:
    stamp = dt.datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        stamp = stamp.astimezone()  # naive input is local time
    return stamp.timestamp()


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument('--since', required=True, help='window start, ISO timestamp')
    ap.add_argument('--until', help='window end, ISO timestamp (default: now)')
    ap.add_argument('--provider', help='filter billing_provider (e.g. opencode-go)')
    ap.add_argument('--task', help='filter the aux task column (empty string = the session itself)')
    ap.add_argument('--db', help='path to state.db (default: $HERMES_HOME/state.db or ~/.hermes/state.db)')
    ap.add_argument('--prices', help='JSON: model -> {"in","out","cache_read"} per 1M USD')
    ap.add_argument('--top', type=int, default=25, help='rows to print (default 25)')
    args = ap.parse_args()

    home = pathlib.Path(os.environ.get('HERMES_HOME') or pathlib.Path.home() / '.hermes')
    db_path = pathlib.Path(args.db) if args.db else home / 'state.db'
    if not db_path.exists():
        sys.exit(f'no ledger at {db_path}')

    prices = json.loads(pathlib.Path(args.prices).read_text()) if args.prices else {}
    since = to_epoch(args.since)
    until = to_epoch(args.until) if args.until else dt.datetime.now().timestamp()

    where, params = ['last_seen >= ?', 'first_seen <= ?'], [since, until]
    if args.provider:
        where.append('billing_provider = ?')
        params.append(args.provider)
    if args.task is not None:
        where.append('task = ?')
        params.append(args.task)

    sql = f"""
        SELECT billing_provider, model, task,
               SUM(api_call_count), SUM(input_tokens), SUM(output_tokens),
               SUM(cache_read_tokens)
        FROM session_model_usage
        WHERE {' AND '.join(where)}
        GROUP BY billing_provider, model, task
    """
    con = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    rows = con.execute(sql, params).fetchall()
    con.close()

    print(f'{db_path.name}: {dt.datetime.fromtimestamp(since):%Y-%m-%d %H:%M} -> '
          f'{dt.datetime.fromtimestamp(until):%Y-%m-%d %H:%M}, {len(rows)} rows')
    print(f'{"provider":14} {"model":28} {"task":18} {"calls":>6} '
          f'{"in M":>7} {"out M":>7} {"cache M":>8} {"$ est":>8}')

    out_rows, total = [], 0.0
    for prov, model, task, calls, inp, out, cache_read in rows:
        calls, inp, out, cache_read = (calls or 0), (inp or 0), (out or 0), (cache_read or 0)
        price = prices.get(model)
        usd = ((inp * price.get('in', 0.0) + out * price.get('out', 0.0)
                + cache_read * price.get('cache_read', 0.0)) / 1e6) if price else None
        if usd is not None:
            total += usd
        out_rows.append((prov or '?', model, task or '(session)', calls, inp, out, cache_read, usd))

    out_rows.sort(key=lambda r: (-(r[7] or 0.0), -(r[4] + r[5])))
    for prov, model, task, calls, inp, out, cache_read, usd in out_rows[:args.top]:
        usd_col = f'{usd:>8.2f}' if usd is not None else f'{"-":>8}'
        print(f'{prov:14} {model:28} {task:18} {calls:>6} '
              f'{inp/1e6:>7.2f} {out/1e6:>7.2f} {cache_read/1e6:>8.2f} {usd_col}')

    if prices:
        print(f'{"":>92} {total:>8.2f}   USD at the rows in --prices')
    else:
        print('no --prices given: dollar column empty - feed the plan\'s own rows '
              'and name the peak/off-peak basis')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
