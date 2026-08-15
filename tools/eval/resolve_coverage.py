"""How much of a real menu can NUTRITION_SOURCES actually resolve?

`plan.md` §29 asks for four measures of the pipeline. Three of them need
photographs; **this one does not.** A dish name is enough to ask the resolver
chain whether it has an answer, so the least expensive of the four can be run
today, against a name list nobody in this project wrote.

What it reports, per corpus:

- how many names resolved at all, and which source answered each
- how many resolved **only** because of the unsourced development table
  (`is_reference`), which is the figure that says how load-bearing
  `vietnamese_foods.py` still is
- every miss, so the output is a worklist rather than a score

Usage:

    NUTRITION_SOURCES=local .venv/bin/python -m tools.eval.resolve_coverage
    .venv/bin/python -m tools.eval.resolve_coverage --sources openfoodfacts,local
    .venv/bin/python -m tools.eval.resolve_coverage --corpus vietnamese_dishes

`--sources` sets NUTRITION_SOURCES before the repository is built, so it does
what `NUTRITION_SOURCES=… ` on the command line does and saves exporting it.
Network sources are only consulted when they are configured; an unconfigured
one is skipped by `NutritionRepository`, not silently counted as a miss.
"""

import argparse
import asyncio
import os
import sys
from collections import Counter
from pathlib import Path
from typing import List, Tuple

CORPUS_DIR = Path(__file__).parent / "corpus"


def read_corpus(name: str) -> List[str]:
    path = CORPUS_DIR / f"{name}.txt"
    if not path.exists():
        available = ", ".join(sorted(p.stem for p in CORPUS_DIR.glob("*.txt")))
        raise SystemExit(f"no corpus {name!r}. Available: {available}")
    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            names.append(line)
    # Keeps the file's order while dropping accidental repeats.
    return list(dict.fromkeys(names))


async def resolve_all(names: List[str], concurrency: int) -> List[Tuple[str, object]]:
    # Imported here, not at module scope: `build_repository` reads
    # NUTRITION_SOURCES at call time but the source classes read their own
    # configuration in `__init__`, so `--sources` has to land in the environment
    # before any of this is touched.
    from app.nutrition.repository import build_repository

    repository = build_repository()
    # Reported from the repository, not from `os.getenv`: importing `app` loads
    # `.env`, so reading the variable before that prints whatever the shell had
    # and not what actually ran. This said "local" through a run that was
    # plainly hitting USDA and Open Food Facts.
    configured = ", ".join(
        f"{source['name']}{'' if source['configured'] else ' (unconfigured, skipped)'}"
        for source in repository.status()
    )
    print(f"sources: {configured}")
    # A network source is rate-limited and this is a few hundred names; the
    # semaphore is what keeps a coverage run from looking like an attack.
    gate = asyncio.Semaphore(concurrency)

    async def one(name: str):
        async with gate:
            return name, await repository.lookup(name)

    return await asyncio.gather(*(one(name) for name in names))


def report(corpus: str, results: List[Tuple[str, object]]) -> None:
    total = len(results)
    by_source: Counter = Counter()
    reference_only = 0
    misses = []

    for name, record in results:
        if record is None:
            misses.append(name)
            continue
        by_source[record.source] += 1
        if getattr(record, "is_reference", False):
            reference_only += 1

    resolved = total - len(misses)
    print(f"\n=== {corpus}: {resolved}/{total} resolved ({resolved / total:.0%})")
    for source, count in by_source.most_common():
        print(f"    {source:<18} {count:>4}  ({count / total:.0%})")
    if reference_only:
        print(
            f"    of which unsourced reference rows: {reference_only} "
            f"({reference_only / total:.0%} of the corpus)"
        )
    print(f"\n  {len(misses)} unresolved:")
    for name in misses:
        print(f"    {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        action="append",
        help="corpus stem under tools/eval/corpus (repeatable; default: all)",
    )
    parser.add_argument(
        "--sources",
        help="value for NUTRITION_SOURCES, e.g. 'usda,openfoodfacts,local'",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="parallel lookups; keep low for network sources (default 4)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help=(
            "only the first N names. Open Food Facts rate-limits *search* to "
            "around 10 requests a minute, so a full corpus against it is both "
            "slow and rude — sample instead when the question is only whether a "
            "network source moves the number at all"
        ),
    )
    args = parser.parse_args()

    if args.sources:
        os.environ["NUTRITION_SOURCES"] = args.sources

    corpora = args.corpus or sorted(p.stem for p in CORPUS_DIR.glob("*.txt"))

    for corpus in corpora:
        names = read_corpus(corpus)
        if args.limit:
            names = names[: args.limit]
        results = asyncio.run(resolve_all(names, args.concurrency))
        report(corpus, results)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    main()
