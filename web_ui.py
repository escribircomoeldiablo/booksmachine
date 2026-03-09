from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template_string, request
from werkzeug.utils import secure_filename

from src.pipeline import process_book

app = Flask(__name__)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class JobState:
    status: str = "queued"
    logs: list[str] = field(default_factory=list)
    output_path: str | None = None
    result_text: str | None = None
    error: str | None = None


_jobs: dict[str, JobState] = {}
_jobs_lock = threading.Lock()


def _append_log(job_id: str, stage: str, message: str) -> None:
    with _jobs_lock:
        job = _jobs[job_id]
        job.logs.append(f"[{stage}] {message}")


def _run_pipeline_job(job_id: str, input_path: str, output_language: str) -> None:
    try:
        with _jobs_lock:
            _jobs[job_id].status = "running"

        def on_progress(stage: str, message: str, _: dict[str, Any]) -> None:
            _append_log(job_id, stage, message)

        output_path = process_book(
            input_path,
            verbose=False,
            output_language=output_language,
            progress_callback=on_progress,
        )
        output_text = Path(output_path).read_text(encoding="utf-8")

        with _jobs_lock:
            job = _jobs[job_id]
            job.status = "done"
            job.output_path = output_path
            job.result_text = output_text
    except Exception as exc:  # pragma: no cover
        with _jobs_lock:
            job = _jobs[job_id]
            job.status = "error"
            job.error = str(exc)
            job.logs.append(f"[error] {exc}")


@app.get("/")
def index() -> str:
    return render_template_string(
        """
<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Resumen de Documentos</title>
    <style>
      :root {
        --bg: #f4f6f0;
        --panel: #ffffff;
        --ink: #17211e;
        --accent: #2d6a4f;
        --border: #d7dfd4;
      }
      body { font-family: "IBM Plex Sans", "Segoe UI", sans-serif; background: radial-gradient(circle at top, #eef4e8, var(--bg)); color: var(--ink); margin: 0; }
      .wrap { max-width: 900px; margin: 2rem auto; background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 1.2rem; }
      h1 { margin-top: 0; }
      .row { display: flex; gap: 1rem; flex-wrap: wrap; align-items: end; }
      label { display: block; font-weight: 600; margin-bottom: .4rem; }
      input, select, button, textarea { font: inherit; }
      button { background: var(--accent); color: #fff; border: 0; border-radius: 8px; padding: .6rem .9rem; cursor: pointer; }
      #logs { white-space: pre-wrap; background: #f9fbf8; border: 1px solid var(--border); border-radius: 8px; padding: .8rem; min-height: 180px; }
      textarea { width: 100%; min-height: 260px; border: 1px solid var(--border); border-radius: 8px; padding: .7rem; }
      .muted { color: #4f5f59; }
    </style>
  </head>
  <body>
    <div class="wrap">
      <h1>Resumen de documentos</h1>
      <p class="muted">Sube el archivo, elige idioma de salida y sigue el progreso por etapas.</p>

      <form id="job-form">
        <div class="row">
          <div>
            <label for="file">Documento</label>
            <input id="file" name="file" type="file" required />
          </div>
          <div>
            <label for="output_language">Idioma de salida</label>
            <select id="output_language" name="output_language">
              <option value="original">Idioma original</option>
              <option value="es" selected>Español</option>
            </select>
          </div>
          <div>
            <button type="submit">Procesar</button>
          </div>
        </div>
      </form>

      <h3>Estado</h3>
      <div id="status" class="muted">Esperando archivo...</div>
      <div id="logs"></div>

      <h3>Resultado</h3>
      <textarea id="result" readonly placeholder="El resumen final aparecerá aquí"></textarea>
    </div>

    <script>
      let timer = null;

      function setStatus(text) {
        document.getElementById('status').textContent = text;
      }

      function setLogs(lines) {
        document.getElementById('logs').textContent = lines.join('\n');
      }

      async function pollJob(jobId) {
        const res = await fetch(`/api/status/${jobId}`);
        const data = await res.json();

        setStatus(`Estado: ${data.status}` + (data.error ? ` | Error: ${data.error}` : ''));
        setLogs(data.logs || []);

        if (data.status === 'done') {
          document.getElementById('result').value = data.result_text || '';
          clearInterval(timer);
          timer = null;
        }

        if (data.status === 'error') {
          clearInterval(timer);
          timer = null;
        }
      }

      document.getElementById('job-form').addEventListener('submit', async (ev) => {
        ev.preventDefault();
        const formData = new FormData(ev.target);
        setStatus('Creando tarea...');
        setLogs([]);
        document.getElementById('result').value = '';

        const res = await fetch('/api/start', { method: 'POST', body: formData });
        const data = await res.json();
        if (!res.ok) {
          setStatus(`Error al crear tarea: ${data.error || 'desconocido'}`);
          return;
        }

        setStatus('Estado: running');
        timer = setInterval(() => pollJob(data.job_id), 1000);
        await pollJob(data.job_id);
      });
    </script>
  </body>
</html>
        """
    )


@app.post("/api/start")
def start_job() -> tuple[Any, int] | Any:
    if "file" not in request.files:
        return jsonify({"error": "No se recibio archivo"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Archivo sin nombre"}), 400

    output_language = request.form.get("output_language", "es")
    if output_language not in {"es", "original"}:
        return jsonify({"error": "Idioma invalido"}), 400

    safe_name = secure_filename(file.filename)
    input_path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{safe_name}"
    file.save(str(input_path))

    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _jobs[job_id] = JobState()

    thread = threading.Thread(
        target=_run_pipeline_job,
        args=(job_id, str(input_path), output_language),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id})


@app.get("/api/status/<job_id>")
def job_status(job_id: str) -> tuple[Any, int] | Any:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            return jsonify({"error": "Job no encontrado"}), 404

        return jsonify(
            {
                "status": job.status,
                "logs": job.logs,
                "output_path": job.output_path,
                "result_text": job.result_text,
                "error": job.error,
            }
        )


if __name__ == "__main__":
    app.run(debug=True)
