"""Quick, stratified Cypher-generation eval.

The full harness run is 80 records x 2 Gemini calls per model, which takes the
better part of an hour and is far more precision than a routine check needs.
This samples a small set stratified across question families, so a run costs a
few minutes and still touches both the easy lookup families and the multi-hop
ones where accuracy actually varies.

Usage:
    python finetuning/quick_eval.py
    python finetuning/quick_eval.py --n 20 --model gemini-3.5-flash-lite
    python finetuning/quick_eval.py --n 40 --seed 7

Costs 2 Gemini calls per record on the chosen model's daily bucket.
Flash Lite models allow 500/day; Flash models allow 20/day, so keep --n small
if you point this at a Flash model.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO / ".env")

from finetuning.evaluation.harness import Evaluator, run_evaluation  # noqa: E402
from finetuning.evaluation.model_adapters import GeminiModelAdapter  # noqa: E402
from src.pipeline.executor import Neo4jExecutor  # noqa: E402
from src.pipeline.types import PipelineConfig  # noqa: E402
from src.pipeline.validator import RuleBasedValidator  # noqa: E402

TEST_SET = REPO / "finetuning/data/processed/splits/test_sample.jsonl"


def stratified_sample(records: list[dict], n: int, seed: int) -> list[dict]:
    """Take ~n records spread as evenly as possible across question families.

    Families are cycled round-robin rather than sampled proportionally, so the
    rarer multi-hop families are not crowded out by the large F2.2 family.
    """
    rng = random.Random(seed)
    by_family: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_family[r.get("family_id", "?")].append(r)

    for bucket in by_family.values():
        rng.shuffle(bucket)

    picked: list[dict] = []
    families = sorted(by_family)
    while len(picked) < n and any(by_family[f] for f in families):
        for fam in families:
            if len(picked) >= n:
                break
            if by_family[fam]:
                picked.append(by_family[fam].pop())
    return picked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=20, help="number of records to evaluate (default: 20)")
    parser.add_argument(
        "--model",
        default=os.getenv("GEMINI_CYPHER_GENERATOR_MODEL", "gemini-3.5-flash-lite"),
        help="Gemini model to evaluate (default: the configured Cypher generator)",
    )
    parser.add_argument("--seed", type=int, default=0, help="sampling seed; change it for a different sample")
    parser.add_argument("--rpm", type=int, default=12, help="client-side rate limit (default: 12)")
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO / "finetuning/evaluation/results/quick",
        help="directory for checkpoint and metrics output",
    )
    args = parser.parse_args()

    records = [json.loads(line) for line in TEST_SET.open(encoding="utf-8")]
    sample = stratified_sample(records, args.n, args.seed)
    families = sorted({r.get("family_id", "?") for r in sample})
    print(f"model:    {args.model}")
    print(f"sample:   {len(sample)} records across {len(families)} families (seed={args.seed})")
    print(f"families: {', '.join(families)}")
    print(f"cost:     ~{len(sample) * 2} calls on this model's daily bucket\n")

    args.out.mkdir(parents=True, exist_ok=True)

    cfg = PipelineConfig()
    executor = Neo4jExecutor(
        uri=os.getenv("NEO4J_URI"),
        user=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD"),
        config=cfg,
    )
    adapter = GeminiModelAdapter(
        model=args.model,
        api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.1,
        rate_limit_rpm=args.rpm,
    )
    evaluator = Evaluator(
        validator=RuleBasedValidator(config=cfg),
        executor=executor,
        model_adapter=adapter,
    )

    # A stale checkpoint would silently skip records, so scope it to this run.
    checkpoint = args.out / f"{args.model}_n{args.n}_seed{args.seed}_checkpoint.jsonl"
    checkpoint.unlink(missing_ok=True)

    results = run_evaluation(adapter, sample, checkpoint, evaluator, checkpoint_interval=5)
    metrics = evaluator.aggregate_metrics(results)

    print(f"\n{'=' * 60}")
    print(f"{args.model}  (n={metrics['total']})")
    print(f"  syntactic validity  {metrics['syntactic_validity_pct']:5.1f}%")
    print(f"  execution success   {metrics['execution_success_pct']:5.1f}%")
    print(f"  output accuracy     {metrics['output_accuracy_pct']:5.1f}%")
    print(f"  avg latency         {metrics['avg_latency_ms']:.0f} ms")

    per_family: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in results:
        fam = r["id"].split("-")[0]
        per_family[fam][1] += 1
        per_family[fam][0] += 1 if r["result_match"] else 0
    print("\n  by family (accurate/total):")
    for fam, (ok, total) in sorted(per_family.items()):
        print(f"    {fam:<6} {ok}/{total}")

    (args.out / f"{args.model}_n{args.n}_seed{args.seed}_metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
