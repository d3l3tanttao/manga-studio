"""Cancellable isolated AI runtime; the GUI environment stays independent."""
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
from uuid import uuid4


class AIClient:
    def __init__(self, runtime):
        self.runtime = Path(runtime)
        self.process = None
        self.log = None
        self.messages = queue.Queue()
        self.last_report = {}

    def start(self):
        if self.process and self.process.poll() is None:
            return
        python = self.runtime / ".reference-venv" / "Scripts" / "python.exe"
        if not python.is_file():
            raise FileNotFoundError("AI runtime is not installed. Run setup-ai.ps1.")
        logs = self.runtime / ".ai-jobs"
        logs.mkdir(exist_ok=True)
        self.log_path = logs / ("worker-"+uuid4().hex+".log")
        self.log = self.log_path.open("w", encoding="utf-8")
        self.messages = queue.Queue()
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        self.process = subprocess.Popen([str(python), "-u", str(Path(__file__).with_name("ai_worker.py"))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log, text=True,
            encoding="utf-8", bufsize=1, env=env, creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        process, messages = self.process, self.messages
        def read():
            try:
                for line in process.stdout:
                    try:
                        messages.put(json.loads(line))
                    except ValueError:
                        continue
            finally:
                messages.put({"kind":"exit"})
        threading.Thread(target=read, daemon=True).start()

    def generate(self, image, settings, cancelled, notify):
        from dataclasses import asdict
        from PIL import Image
        self.start()
        with tempfile.TemporaryDirectory(prefix="render-", dir=self.runtime / ".ai-jobs") as folder:
            source, output = Path(folder)/"source.png", Path(folder)/"output.png"
            image.save(source)
            options = asdict(settings)
            options.pop("models", None)
            request = {"source":str(source), "output":str(output), "models":str(settings.models), "options":options}
            self.process.stdin.write(json.dumps(request, ensure_ascii=False)+"\n")
            self.process.stdin.flush()
            while True:
                if cancelled():
                    self.close()
                    raise InterruptedError()
                try:
                    event = self.messages.get(timeout=.1)
                except queue.Empty:
                    continue
                if event["kind"] == "progress":
                    notify(event)
                elif event["kind"] == "result":
                    self.last_report = event["metadata"]
                    with Image.open(output) as result:
                        return result.convert("RGB")
                elif event["kind"] == "error":
                    raise RuntimeError(event["message"])
                elif event["kind"] == "exit":
                    raise RuntimeError("AI worker stopped. Log: "+str(self.log_path))

    def close(self):
        if self.process:
            if self.process.poll() is None:
                if os.name == "nt":
                    # Windows venv uses a redirector child. Stop our entire worker
                    # tree so cancellation cannot orphan a GPU allocation.
                    subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0), timeout=15)
                else:
                    self.process.terminate()
                try:
                    self.process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=8)
            for stream in (self.process.stdin,self.process.stdout):
                if stream:
                    stream.close()
            self.process = None
        if self.log:
            self.log.close()
            self.log = None
