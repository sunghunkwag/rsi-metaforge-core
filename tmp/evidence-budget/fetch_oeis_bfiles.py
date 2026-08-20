from __future__ import annotations

import csv
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path('/mnt/data/evidence_curve')
AIDS_FILE = ROOT / 'aids_400.txt'
BFILE_DIR = ROOT / 'bfiles'
FETCH_LOG_JSON = ROOT / 'bfile_http_fetch_log.json'
FETCH_LOG_CSV = ROOT / 'bfile_http_fetch_log.csv'
BASE_URL = 'https://oeis.org/{aid}/b{digits}.txt'
REQUEST_INTERVAL_SECONDS = 1.0
TIMEOUT_SECONDS = 30
MAX_TRANSIENT_RETRIES = 2
USER_AGENT = 'OEIS-EvidenceBudget-Audit/1.0 (polite research fetch; one request per second)'


def load_aids(path: Path) -> list[str]:
    aids = [line.strip() for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if len(aids) != 400 or len(set(aids)) != 400:
        raise ValueError(f'Expected 400 unique A-numbers; got {len(aids)} rows and {len(set(aids))} unique values.')
    return aids


def bfile_path(aid: str) -> Path:
    return BFILE_DIR / f'b{aid[1:]}.txt'


def parse_term_rows(text: str) -> tuple[int, int | None, int | None]:
    count = 0
    first_index = None
    last_index = None
    previous = None
    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split()
        if len(parts) != 2:
            raise ValueError(f'Line {line_number}: expected two whitespace-separated integers.')
        n = int(parts[0])
        int(parts[1])
        if previous is not None and n != previous + 1:
            raise ValueError(f'Line {line_number}: non-contiguous index {previous} -> {n}.')
        if first_index is None:
            first_index = n
        last_index = n
        previous = n
        count += 1
    return count, first_index, last_index


def sleep_after_request(started_at: float) -> None:
    elapsed = time.monotonic() - started_at
    remaining = REQUEST_INTERVAL_SECONDS - elapsed
    if remaining > 0:
        time.sleep(remaining)


def fetch_one(aid: str) -> dict:
    digits = aid[1:]
    url = BASE_URL.format(aid=aid, digits=digits)
    path = bfile_path(aid)
    row = {
        'aid': aid,
        'url': url,
        'cache_path': str(path),
        'status': None,
        'http_status': None,
        'bytes': 0,
        'term_count': 0,
        'first_index': None,
        'last_index': None,
        'error': None,
        'from_cache': False,
    }

    if path.exists():
        try:
            payload = path.read_bytes()
            text = payload.decode('utf-8')
            count, first_index, last_index = parse_term_rows(text)
            row.update({
                'status': 'cached',
                'bytes': len(payload),
                'term_count': count,
                'first_index': first_index,
                'last_index': last_index,
                'from_cache': True,
            })
            return row
        except Exception as exc:
            row['status'] = 'cache_invalid_refetching'
            row['error'] = f'{type(exc).__name__}: {exc}'

    for attempt in range(MAX_TRANSIENT_RETRIES + 1):
        started_at = time.monotonic()
        request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'text/plain,*/*;q=0.1'})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                status = int(getattr(response, 'status', 200))
                payload = response.read()
            sleep_after_request(started_at)
            text = payload.decode('utf-8')
            count, first_index, last_index = parse_term_rows(text)
            path.write_bytes(payload)
            row.update({
                'status': 'fetched',
                'http_status': status,
                'bytes': len(payload),
                'term_count': count,
                'first_index': first_index,
                'last_index': last_index,
                'error': None,
            })
            return row
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            sleep_after_request(started_at)
            row['http_status'] = status
            if status == 404:
                row['status'] = 'absent_404'
                row['error'] = f'HTTPError: {status} {exc.reason}'
                return row
            if status == 429 or 500 <= status <= 599:
                if attempt < MAX_TRANSIENT_RETRIES:
                    retry_after = exc.headers.get('Retry-After') if exc.headers else None
                    if retry_after:
                        try:
                            time.sleep(max(0.0, float(retry_after)))
                        except ValueError:
                            pass
                    continue
            row['status'] = 'http_error'
            row['error'] = f'HTTPError: {status} {exc.reason}'
            return row
        except Exception as exc:
            sleep_after_request(started_at)
            if attempt < MAX_TRANSIENT_RETRIES:
                continue
            row['status'] = 'fetch_error'
            row['error'] = f'{type(exc).__name__}: {exc}'
            return row

    raise AssertionError('Unreachable retry state.')


def write_logs(rows: list[dict]) -> None:
    FETCH_LOG_JSON.write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
    fields = [
        'slot', 'aid', 'url', 'status', 'http_status', 'bytes', 'term_count',
        'first_index', 'last_index', 'from_cache', 'error', 'cache_path'
    ]
    with FETCH_LOG_CSV.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    BFILE_DIR.mkdir(parents=True, exist_ok=True)
    aids = load_aids(AIDS_FILE)
    rows = []
    for slot, aid in enumerate(aids):
        row = fetch_one(aid)
        row = {'slot': slot, **row}
        rows.append(row)
        print(f"{slot:03d} {aid} {row['status']} terms={row['term_count']} http={row['http_status']}", flush=True)
        write_logs(rows)

    summary = {
        'sample_size': len(aids),
        'fetched_or_cached': sum(row['status'] in ('fetched', 'cached') for row in rows),
        'absent_404': sum(row['status'] == 'absent_404' for row in rows),
        'errors': sum(row['status'] not in ('fetched', 'cached', 'absent_404') for row in rows),
        'term_threshold_counts': {
            '>=40': sum(row['term_count'] >= 40 for row in rows),
            '>=64': sum(row['term_count'] >= 64 for row in rows),
            '>=112': sum(row['term_count'] >= 112 for row in rows),
            '>=208': sum(row['term_count'] >= 208 for row in rows),
        },
    }
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
