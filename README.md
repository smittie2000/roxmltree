# roxmltree upstream-series bench kit

Measures each PR in the `rehearsal/*` stack against its parent, and master (`upstream-ready/base`, #169's head) against the end of the stack. This branch holds only code. The bench files are fetched from their original sources.

```
python -I fetch.py "D:\Dev work\roxmltree"   # files/ and ds/, checked by SHA-256 (the CSW file is a live query and will differ)
python -I gen.py                              # gen/: 6 generated cases + CRLF copies of 3 real files
python -I run.py setup "D:\Dev work\roxmltree"   # worktrees for every step, release builds
python -I run.py all                          # about 1.5 h on a Ryzen 5 5500; results in out/
```

- `files/`: 17 real files: the 8 in `benches/`, plus 9 from public repositories and services, as stored there.
- `gen/`: 9 generated cases.
- `ds/`: 1,968 files from roxmltree's dependents (resvg, fontconfig, fontconfig-parser, mailrs, dioxus, openvmm) at fixed commits.
- `harness/src/bm.rs`: parses each file and reports the median of 7 timed samples (each at least 40 ms), plus peak and final heap from a counting allocator.
- `harness/src/ds.rs`: parses each dependent's file set per round and reports the median of 9.
- `run.py`: each round runs every build once in shuffled order; each file keeps its fastest run, and every step and master-to-end pair is compared from the same rounds. `base` vs `baseB` is an A/A noise check.

Keep the machine idle while it runs: stop builds, syncs and background compute such as BOINC. `run.py` refuses to start above 15% CPU load (set `KIT_IGNORE_LOAD=1` to override), waits for idle before each round, and records what it saw in `out/load.json`; a `busy: true` entry means that stage's numbers are suspect. Don't change any roxmltree branch. When it's done, commit `out/*.json` to a `bench-results` branch and push it to the fork.
