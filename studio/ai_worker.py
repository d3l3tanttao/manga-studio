"""JSON-line child process. Stdout is protocol only; model logs go to stderr."""
import contextlib
import json
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
protocol = sys.stdout


def send(kind, **payload):
    protocol.write(json.dumps({"kind": kind, **payload}, ensure_ascii=False)+"\n")
    protocol.flush()


def main():
    with contextlib.redirect_stdout(sys.stderr):
        from studio.generation import Renderer, image
    renderer = None
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if request.get("action") == "quit":
                break
            with contextlib.redirect_stdout(sys.stderr):
                if renderer is None or renderer.models.resolve() != Path(request["models"]).resolve():
                    if renderer is not None:
                        renderer.release()
                    renderer = Renderer(request["models"], lambda stage, **data: send("progress", stage=stage, **data))
                try:
                    result, metadata = renderer.render(image(request["source"]), request["options"])
                except RuntimeError as error:
                    if "out of memory" not in str(error).lower() or request["options"].get("precision","auto") != "auto":
                        raise
                    renderer.release()
                    send("progress",stage="memory_retry")
                    result, metadata = renderer.render(image(request["source"]), {**request["options"],"precision":"nf4"})
                    metadata["memory_retry"] = "nf4"
                output = Path(request["output"])
                output.parent.mkdir(parents=True, exist_ok=True)
                result.save(output, format="PNG")
                output.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            send("result", output=str(output), metadata=metadata)
        except Exception as error:
            traceback.print_exc(file=sys.stderr)
            if renderer is not None:
                renderer.release()
            send("error", message=str(error))
    if renderer is not None:
        renderer.release()


if __name__ == "__main__":
    main()
