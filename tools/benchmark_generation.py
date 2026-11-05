"""Real local comparison; no manually painted masks or fixed region colors."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studio.generation import Renderer, image, sha

parser = argparse.ArgumentParser()
parser.add_argument("--models", type=Path, required=True)
parser.add_argument("--sources", type=Path, nargs="+", required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--reference", default="")
parser.add_argument("--renderer", choices=("flux",), default="flux")
parser.add_argument("--mode", choices=("color", "reference", "redraw"), default="color")
parser.add_argument("--precision", choices=("bf16", "nf4", "auto"), default="bf16")
parser.add_argument("--freedom", type=float, default=1.)
parser.add_argument("--chapter", action="store_true")
parser.add_argument("--seed", type=int, default=20261105)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
renderer = Renderer(args.models, lambda stage, **values: print(json.dumps({"stage":stage, **values}), flush=True))
options = {"renderer":args.renderer, "generation":args.mode, "precision":args.precision,
           "reference":args.reference, "freedom":args.freedom, "seed":args.seed}
for i, source in enumerate(args.sources, 1):
    output = args.output / f"{i:03d}.png"
    if output.is_file():
        if args.chapter and i == 1:
            options["anchor"] = str(output.resolve())
        continue
    result, report = renderer.render(image(source), options)
    result.save(output)
    report.update(source=str(source.resolve()), source_sha256=sha(source), output_sha256=sha(output))
    output.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"saved":str(output), "seconds":report["seconds_total"]}), flush=True)
    if args.chapter and i == 1:
        options["anchor"] = str(output.resolve())
renderer.release()
