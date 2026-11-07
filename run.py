"""roxmltree upstream-series benchmark kit.

usage (from the kit folder):
    python -I run.py setup <path to roxmltree clone>   # fetch, worktrees, release builds
    python -I run.py bench [rounds=11]                  # all builds per round: out/bench-min.json (steps)
                                                        # and out/bench-totals.json (master <-> end)
    python -I run.py downstream [rounds=15]             # dependents' files: out/downstream-steps.json
    python -I run.py cargo [max_rounds=4]               # cargo bench, filtered: out/cargobench-q.json
    python -I run.py all                                # setup must have run; does the three above in order

Every measurement alternates the builds in shuffled order and keeps the fastest run, so load that
hits one run doesn't count. base vs baseB is the same build twice (an A/A noise check).
"""
import json
import os
import platform
import random
import re
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

K = Path(__file__).resolve().parent
OUT = K / 'out'
BIN = K / 'bin'
WT = K / 'wt'
EXE = '.exe' if os.name == 'nt' else ''

REFS = {
    'base': 'upstream-ready/base',
    'p2': 'rehearsal/02-duplicate-attributes',
    'rh03': 'rehearsal/03-bound-reservation',
    'rh04': 'rehearsal/04-external-entity-text',
    'rh05': 'rehearsal/05-find-markup-ends',
    'rh06': 'rehearsal/06-check-text-once',
    'rh07': 'rehearsal/07-line-ends',
    'rh08': 'rehearsal/08-borrow-crlf-indentation',
    'rh09': 'rehearsal/09-attribute-runs',
    'rh10': 'rehearsal/10-attribute-check-once',
    'rh11': 'rehearsal/11-parsing-options-caps',
}
V = list(REFS)
STEP_PAIRS = ['base:baseB'] + [f'{a}:{b}' for a, b in zip(V, V[1:])] + ['base:rh10', 'base:rh11']
FILES = sorted(str(p) for p in (K / 'files').iterdir()) + sorted(str(p) for p in (K / 'gen').iterdir())


def sh(cmd, **kw):
    print('+', ' '.join(map(str, cmd)), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def setup(repo):
    repo = Path(repo).resolve()
    OUT.mkdir(exist_ok=True)
    BIN.mkdir(exist_ok=True)
    WT.mkdir(exist_ok=True)
    sh(['git', '-C', repo, 'fetch', 'origin'])
    shas = {}
    for v, ref in REFS.items():
        d = WT / v
        if d.exists():
            subprocess.run(['git', '-C', repo, 'worktree', 'remove', '--force', d])
            shutil.rmtree(d, ignore_errors=True)
        sh(['git', '-C', repo, '-c', 'core.autocrlf=false', 'worktree', 'add', '--detach', d, f'origin/{ref}'])
        sh(['git', '-C', d, 'config', 'core.autocrlf', 'false'])
        shas[v] = subprocess.run(['git', '-C', d, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
        h = K / 'h' / v
        h.mkdir(parents=True, exist_ok=True)
        rox = d.as_posix()
        src = (K / 'harness' / 'src').as_posix()
        (h / 'Cargo.toml').write_text(
            f'[package]\nname = "h-{v}"\nversion = "0.1.0"\nedition = "2021"\n[workspace]\n'
            f'[dependencies]\nroxmltree = {{ path = "{rox}" }}\n'
            f'[[bin]]\nname = "bm-{v}"\npath = "{src}/bm.rs"\n'
            f'[[bin]]\nname = "ds-{v}"\npath = "{src}/ds.rs"\n'
            f'[profile.release]\ncodegen-units = 1\n')
        sh(['cargo', 'build', '--release', '-q'], cwd=h)
        for b in ('bm', 'ds'):
            shutil.copy2(h / 'target' / 'release' / f'{b}-{v}{EXE}', BIN / f'{b}-{v}{EXE}')
    shutil.copy2(BIN / f'bm-base{EXE}', BIN / f'bm-baseB{EXE}')
    info = {
        'shas': shas,
        'rustc': subprocess.run(['rustc', '-V'], capture_output=True, text=True).stdout.strip(),
        'platform': platform.platform(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'cpu_count': os.cpu_count(),
    }
    if os.name == 'nt':
        r = subprocess.run(['powershell', '-NoProfile', '-Command',
                            '(Get-CimInstance Win32_Processor).Name; (Get-CimInstance Win32_OperatingSystem).Caption'],
                           capture_output=True, text=True)
        info['cpu_os'] = r.stdout.strip().splitlines()
    (OUT / 'machine.json').write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


def run_bm(v):
    out = subprocess.run([str(BIN / f'bm-{v}{EXE}'), *FILES], capture_output=True, text=True, check=True).stdout
    rows = {}
    for line in out.splitlines():
        name, ns, peak, fin = line.split('\t')
        rows[name] = (float(ns), int(peak), int(fin))
    return rows


TOTAL_PAIRS = ['base:rh10', 'rh10:base', 'base:rh11', 'rh11:base']


def pair_result(times, mem, a, b):
    rows = []
    for name in sorted(times[a]):
        ta, tb = min(times[a][name]), min(times[b][name])
        rows.append({'file': name, 'parent_us': ta / 1000, 'child_us': tb / 1000,
                     'time_pct': 100 * (tb / ta - 1),
                     'parent_peak': mem[a][name][0], 'child_peak': mem[b][name][0],
                     'parent_final': mem[a][name][1], 'child_final': mem[b][name][1]})
    real = [r for r in rows if not r['file'].startswith('g')]
    geo = statistics.geometric_mean([r['child_us'] / r['parent_us'] for r in real])
    return {'rows': rows, 'geomean_pct_17': 100 * (geo - 1)}


def bench(rounds):
    # Every round runs all builds (plus baseB) once in shuffled order, so each build is measured
    # once per round and every pair, step or total, is compared from the same runs.
    builds = V + ['baseB']
    times = {v: {} for v in builds}
    mem = {v: {} for v in builds}
    for rnd in range(rounds):
        order = builds[:]
        random.shuffle(order)
        for v in order:
            for name, (ns, peak, fin) in run_bm(v).items():
                times[v].setdefault(name, []).append(ns)
                mem[v][name] = (peak, fin)
        print(f'bench round {rnd + 1}/{rounds} done', flush=True)
    for out_name, pairs in (('bench-min.json', STEP_PAIRS), ('bench-totals.json', TOTAL_PAIRS)):
        results = {}
        for pair in pairs:
            a, b = pair.split(':')
            results[pair] = pair_result(times, mem, a, b)
            print(f'{pair}: geomean over 17 real files {results[pair]["geomean_pct_17"]:+.1f}%', flush=True)
        (OUT / out_name).write_text(json.dumps(results, indent=1))


def downstream(rounds):
    ds = {v: {} for v in V}
    for _ in range(rounds):
        order = V[:]
        random.shuffle(order)
        for v in order:
            out = subprocess.run([str(BIN / f'ds-{v}{EXE}'), str(K / 'ds'), str(K / 'ds-list.txt')],
                                 capture_output=True, text=True, check=True).stdout
            for line in out.splitlines():
                g, n, b, ns, e = line.split('\t')
                ds[v].setdefault(g, {'n': int(n), 'bytes': int(b), 'errors': int(e), 't': []})['t'].append(float(ns))
    res = {'ds': {v: {g: {'n': d['n'], 'bytes': d['bytes'], 'errors': d['errors'], 'min_ns': min(d['t'])}
                      for g, d in ds[v].items()} for v in V}, 'usvg': {}}
    (OUT / 'downstream-steps.json').write_text(json.dumps(res, indent=1))
    for g in ds[V[0]]:
        print(g, ' '.join(f"{v}={res['ds'][v][g]['min_ns'] / 1e6:.3f}ms" for v in V), flush=True)


def cargo(max_rounds):
    runs = {v: {} for v in V}

    def clean(v, k):
        return sum(1 for ns, pm in runs[v].get(k, []) if pm <= 0.15 * ns)

    for v in V:
        sh(['cargo', 'bench', '--no-run', '-q'], cwd=WT / v / 'benches',
           env={**os.environ, 'CARGO_TARGET_DIR': str(K / 'cbt' / v)})
    for rnd in range(max_rounds):
        order = V[:]
        random.shuffle(order)
        for v in order:
            if runs[v] and all(clean(v, k) >= 2 for k in runs[v]):
                continue
            out = subprocess.run(['cargo', 'bench', '-q', '--', 'roxmltree'], cwd=WT / v / 'benches',
                                 env={**os.environ, 'CARGO_TARGET_DIR': str(K / 'cbt' / v)},
                                 capture_output=True, text=True).stdout
            for line in out.splitlines():
                m = re.match(r'test (\S+)\s+\.\.\. bench:\s+([\d,]+) ns/iter \(\+/- ([\d,]+)\)', line)
                if m:
                    runs[v].setdefault(m.group(1), []).append(
                        (int(m.group(2).replace(',', '')), int(m.group(3).replace(',', ''))))
        left = sum(1 for v in V for k in runs[v] if clean(v, k) < 2)
        print(f'cargo round {rnd + 1}: cells still without two clean runs: {left}', flush=True)
        (OUT / 'cargobench-q.json').write_text(json.dumps(runs, indent=1))
        if left == 0:
            break


def main():
    cmd = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    OUT.mkdir(exist_ok=True)
    if cmd == 'setup':
        setup(arg)
    elif cmd == 'bench':
        bench(int(arg or 11))
    elif cmd == 'downstream':
        downstream(int(arg or 15))
    elif cmd == 'cargo':
        cargo(int(arg or 4))
    elif cmd == 'all':
        bench(11)
        downstream(15)
        cargo(4)
    else:
        sys.exit(__doc__)


main()
