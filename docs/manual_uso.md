# Manual de uso

Guia practica para generar cada artefacto del proyecto sin adivinar comandos.

## 1. Preparacion minima

### Crear o usar el entorno virtual

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Si ya existe `.venv`, basta con activarlo. La documentacion oficial de Python tambien indica que puedes ejecutar directamente `.venv/bin/python` sin activar el entorno.

### Configurar la API key

```bash
export OPENAI_API_KEY="tu_api_key"
```

El proyecto llama a `OpenAI().responses.create(...)`, asi que necesita `OPENAI_API_KEY` disponible en la terminal.

## 2. Comando base del pipeline

El punto de entrada principal es:

```bash
.venv/bin/python run_pipeline.py "books/Ancient Astrology - Vol 2.pdf"
```

Opciones utiles:

```bash
.venv/bin/python run_pipeline.py "books/Ancient Astrology - Vol 2.pdf" --mode smoke
.venv/bin/python run_pipeline.py "books/Ancient Astrology - Vol 2.pdf" --dry-run
.venv/bin/python run_pipeline.py "books/Ancient Astrology - Vol 2.pdf" --max-chunks 5
.venv/bin/python run_pipeline.py "books/Ancient Astrology - Vol 2.pdf" --output-language original
.venv/bin/python run_pipeline.py "books/Ancient Astrology - Vol 2.pdf" --knowledge-language original
.venv/bin/python run_pipeline.py "books/Ancient Astrology - Vol 2.pdf" --no-resume
.venv/bin/python run_pipeline.py "books/Ancient Astrology - Vol 2.pdf" --quiet
```

Que hace cada opcion:

- `--mode smoke`: procesa solo una muestra pequena.
- `--dry-run`: calcula el plan, pero no llama al modelo ni escribe artefactos.
- `--max-chunks N`: limita cuantos chunks nuevos procesar.
- `--output-language original`: deja los resúmenes legibles en el idioma fuente.
- `--knowledge-language original`: deja los artefactos canonicos de conocimiento en el idioma fuente. Es la opcion recomendada para PDFs en ingles.
- `--no-resume`: ignora checkpoints previos.
- `--quiet`: reduce logs en consola.

## 3. Artefactos que genera el pipeline principal

Al ejecutar el pipeline normal, el proyecto escribe en `outputs/`:

- `<libro>_summary.txt`: compendio final.
- `<libro>_summary_chunks.txt`: resumen historico por chunk.
- `<libro>_summary_blocks.txt`: resumen intermedio por bloques.

Si activas extraccion de conocimiento, tambien genera:

- `<libro>_knowledge_chunks.jsonl`: conocimiento extraido chunk por chunk.
- `<libro>_knowledge_audit.jsonl`: decisiones y auditoria por chunk.

Politica recomendada de idioma:

- `summary*.txt`: controlados por `--output-language`.
- `knowledge_*`: controlados por `--knowledge-language`.
- Para libros en ingles, lo mas seguro es `--output-language es --knowledge-language original`.

### Activar extraccion de conocimiento

```bash
KNOWLEDGE_EXTRACTION_ENABLED=true .venv/bin/python run_pipeline.py "books/Ancient Astrology - Vol 2.pdf" --knowledge-language original
```

## 4. Comandos para generar cada artefacto derivado

Todos estos comandos parten de un archivo `*_knowledge_chunks.jsonl`.

### 4.1 Conceptos consolidados

```bash
.venv/bin/python -m src.knowledge_consolidator \
  "outputs/Ancient Astrology - Vol 2_knowledge_chunks.jsonl" \
  --artifact concepts
```

Salida esperada:

- `outputs/Ancient Astrology - Vol 2_knowledge_concepts.json`

Uso: consolida conocimiento repetido de varios chunks en un concepto canonico.

### 4.2 Familias de conceptos

```bash
.venv/bin/python -m src.knowledge_consolidator \
  "outputs/Ancient Astrology - Vol 2_knowledge_chunks.jsonl" \
  --artifact families
```

Salida esperada:

- `outputs/Ancient Astrology - Vol 2_knowledge_families.json`

Uso: asigna conceptos a familias definidas en `config/domain_families/`.

### 4.3 Candidatos de nuevas familias

```bash
.venv/bin/python -m src.knowledge_consolidator \
  "outputs/Ancient Astrology - Vol 2_knowledge_chunks.jsonl" \
  --artifact family-candidates
```

Salida esperada:

- `outputs/Ancient Astrology - Vol 2_knowledge_family_candidates.json`

Uso: propone grupos nuevos para conceptos que quedaron fuera del catalogo actual.

### 4.4 Ontologia final

```bash
.venv/bin/python -m src.knowledge_consolidator \
  "outputs/Ancient Astrology - Vol 2_knowledge_chunks.jsonl" \
  --artifact ontology
```

Salida esperada:

- `outputs/Ancient Astrology - Vol 2_knowledge_ontology.json`

Uso: construye la ontologia final y, durante el proceso, tambien actualiza:

- `..._knowledge_families.json`
- `..._knowledge_family_candidates.json`

### 4.5 Generar todo en una sola pasada

```bash
.venv/bin/python -m src.knowledge_consolidator \
  "outputs/Ancient Astrology - Vol 2_knowledge_chunks.jsonl" \
  --artifact all
```

Este comando genera, en orden:

- conceptos
- familias
- candidatos de familias
- ontologia

## 5. Sobrescribir la ruta de salida

Solo aplica cuando generas un artefacto individual:

```bash
.venv/bin/python -m src.knowledge_consolidator \
  "outputs/Ancient Astrology - Vol 2_knowledge_chunks.jsonl" \
  --artifact concepts \
  --output-path "outputs/mi_consolidado.json"
```

`--output-path` no se puede usar con `--artifact all`.

## 6. Perfiles estructurales para PDFs dificiles

Si el PDF viene limpio:

```bash
set -a
source profiles/structural_clean.env
set +a
.venv/bin/python run_pipeline.py "books/Ancient Astrology - Vol 2.pdf"
```

Si el PDF tiene OCR ruidoso:

```bash
set -a
source profiles/structural_noisy.env
set +a
.venv/bin/python run_pipeline.py "books/Ancient Astrology - Vol 2.pdf"
```

Si no sabes cual usar, empieza con:

```bash
set -a
source profiles/structural_base.env
set +a
.venv/bin/python run_pipeline.py "books/Ancient Astrology - Vol 2.pdf"
```

## 7. UI web

Si prefieres interfaz web:

```bash
.venv/bin/python web_ui.py
```

Luego abre `http://127.0.0.1:5000/`.

La UI permite subir el archivo, elegir idioma de salida y ver el progreso. Hoy esta interfaz devuelve el resumen final; los artefactos derivados de conocimiento siguen siendo un flujo por consola.

## 8. Flujo recomendado

Para un libro nuevo:

```bash
KNOWLEDGE_EXTRACTION_ENABLED=true .venv/bin/python run_pipeline.py "books/Ancient Astrology - Vol 2.pdf" --output-language es --knowledge-language original
.venv/bin/python -m src.knowledge_consolidator "outputs/Ancient Astrology - Vol 2_knowledge_chunks.jsonl" --artifact all
```

Resultado final:

- resumen final
- resumen por chunks
- resumen por bloques
- front matter outline auxiliar
- conocimiento por chunk
- auditoria de conocimiento
- conceptos consolidados
- familias
- candidatos de familias
- ontologia

Artifact adicional del pipeline base:

- `..._front_matter_outline.json`

Notas:

- se genera antes del chunking principal
- es auxiliar y auditable
- no modifica por si solo `knowledge_chunks`, `knowledge_concepts`, `knowledge_families` ni `knowledge_ontology`
- se puede desactivar con `FRONT_MATTER_OUTLINE_ENABLED=false`

## 9. Errores comunes

### `Missing OPENAI_API_KEY environment variable.`

Falta exportar la API key en la terminal actual.

### `No readable content found in: ...`

El archivo no pudo extraerse o quedo vacio tras la carga.

### El pipeline retoma un estado viejo

Ejecuta con:

```bash
.venv/bin/python run_pipeline.py "books/Ancient Astrology - Vol 2.pdf" --no-resume
```

## 10. Referencias oficiales revisadas

- Python `venv`: https://docs.python.org/3.12/library/venv.html
- OpenAI Python SDK: https://github.com/openai/openai-python
- OpenAI API, uso de `OPENAI_API_KEY`: https://platform.openai.com/docs/libraries/python-sdk
- Flask quickstart: https://flask.palletsprojects.com/es/stable/quickstart/
