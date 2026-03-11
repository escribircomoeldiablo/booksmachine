# V2 Full Artifacts Audit

## Resumen ejecutivo

El set completo de `Vol 2` muestra un avance real en la capa procedural, pero sigue teniendo fallos estructurales importantes en cuatro zonas:

1. los `summary_*` siguen perdiendo demasiado detalle doctrinal y parecen sesgados hacia una lectura de casas/regencias;
2. la capa procedural ya extrae bastante, pero todavía contamina frames y conceptos entre si;
3. `families`, `taxonomy` y `candidate discovery` siguen siendo mucho mas debiles de lo necesario para 135 conceptos;
4. el `knowledge_metrics_report` no corresponde a la corrida completa actual y no debe usarse como señal de calidad.

En terminos practicos:

- `knowledge_chunks` y `knowledge_concepts` ya son utilizables para exploracion seria
- `procedure_frames` ya demuestran valor real
- `summary.txt` todavia no puede tratarse como compendio doctrinal fiable del volumen completo
- `family_candidates`, `taxonomy` y parte de `ontology` siguen verdes

## Conteos base

- `knowledge_chunks.jsonl`: 494585 bytes
- `knowledge_concepts.json`: 135 conceptos
- `procedural_audit.json`: 17 conceptos con señal procedural
- `procedure_frames.json`: 3 frames
- `knowledge_ontology.json`: 157 nodos
- `knowledge_families.json`: 18 familias aceptadas
- `knowledge_taxonomy.json`: 3 links
- `document_map.json`: 998 secciones, 343 `unknown`

## Hallazgos principales

### 1. `summary_chunks.txt`

Estado:
- estructuralmente rico
- mejor que antes para trazabilidad

Avances:
- ya incluye secciones procedurales explicitas (`PASOS DEL PROCEDIMIENTO`, `REGLAS DE DECISION`, etc.)
- sirve para detectar donde nace el contenido procedural real

Errores:
- sigue habiendo chunks muy vacios o con estructura formal pero poco contenido operativo
- mezcla demasiado facil terminologia, variantes y doctrina local
- en chunks tempranos todavia aparecen bloques casi vacios

Posibilidades:
- seguir usandolo como artifact diagnostico principal
- usarlo para medir cobertura procedural por chunk
- no usarlo como lectura final del volumen

### 2. `summary_blocks.txt`

Estado:
- util como compresion intermedia
- todavia demasiado editorial

Avances:
- preserva bastante mas estructura que la version anterior del pipeline
- deja ver agrupaciones doctrinales mayores

Errores:
- fusiona diferencias reales demasiado pronto
- sigue privilegiando presentacion sobre fidelidad procedural
- arranca muy sesgado hacia casas/regencias en un volumen que contiene mas variedad tecnica

Posibilidades:
- mantenerlo como artifact de lectura rapida
- no tratarlo como base suficiente para procedimientos complejos

### 3. `summary.txt`

Estado:
- el artifact mas debil del set actual

Avances:
- legible como panorama general

Errores:
- el compendio final esta claramente sobrerresumido
- el contenido visible esta muy inclinado a casas y regencias, con poca representacion de otras tecnicas del volumen
- no refleja bien la riqueza procedural que si aparece en `knowledge_*` y `procedure_frames`

Posibilidades:
- si el objetivo es “manual resumido fiel”, esta capa necesita otra iteracion
- no conviene usar `summary.txt` como prueba principal de exito del motor

### 4. `knowledge_chunks.jsonl`

Estado:
- es uno de los artifacts mas valiosos del set

Avances:
- el volumen completo ya contiene extraccion procedural real
- hay procedimientos claros para:
  - `predominator`
  - `kurio`
  - `profection`
  - `lot of fortune`
- se confirma que la arquitectura nueva si generaliza mas alla de un solo caso vertical

Errores:
- aun aparecen reglas rotas o mal segmentadas
- parte del contenido procedural sigue cayendo en conceptos vecinos o demasiado amplios
- algunos procedimientos siguen mezclando seleccion, evaluacion y comentario metodologico

Posibilidades:
- usar este artifact como base de auditoria de cobertura
- si se quiere medir calidad real, aqui hay que mirar antes que en `summary.txt`

### 5. `knowledge_concepts.json`

Estado:
- buen avance, pero todavia desigual

Avances:
- 135 conceptos es una señal razonable para `Vol 2`
- hay 17 conceptos con señal procedural consolidada
- `predominator`, `kurio`, `profection` y `lot of fortune` ya conservan estructura util

Errores:
- `predominator` absorbio contenido que no deberia vivir ahi:
  - pasos de `profections`
  - pasos de `oikodespotes`
- `oikodespotes` quedo muy pobre procedimentalmente a nivel concepto completo
- `kurio` esta mejor estructurado que `oikodespotes`, lo cual es doctrinalmente llamativo y sugiere asimetria del extractor/consolidator

Posibilidades:
- separar mejor ownership procedural entre conceptos vecinos
- usar `knowledge_concepts` como base para explorer y auditoria
- no confiar todavia en que cada concepto procedural ya sea “autosuficiente”

### 6. `procedural_audit.json`

Estado:
- muy util

Avances:
- confirma que el motor ya extrae procedimiento en conceptos importantes
- permite auditar con claridad:
  - pasos
  - reglas
  - outputs
  - evidencia

Errores:
- tambien deja visible la contaminacion:
  - `predominator` contiene pasos de `profections`
- `oikodespotes` sigue casi vacio pese a estar doctrinalmente cargado en el volumen

Posibilidades:
- este artifact ya sirve como base para benchmark
- deberia ser uno de los artifacts centrales del desarrollo

### 7. `procedure_frames.json`

Estado:
- prueba de concepto exitosa, pero todavia no estable para todo el volumen

Frames actuales:
- `determine_predominator`
- `apply_profections`
- `determine_oikodespotes`

Avances:
- `apply_profections` esta razonablemente bien
- `determine_predominator` existe a escala de volumen completo

Errores:
- `determine_predominator` esta contaminado:
  - contiene pasos de `oikodespotes`
  - contiene pasos de `profections`
- `determine_oikodespotes` existe pero esta vacio en la practica
- falta al menos un frame de `evaluation`

Posibilidades:
- reforzar separacion por tipo procedural:
  - `selection`
  - `evaluation`
  - `timing`
  - `calculation`
- `lot of fortune` ya pide un frame de tipo `calculation` o `analysis`
- `kurio` ya pide un frame propio

### 8. `knowledge_families.json`

Estado:
- mejor de lo esperado, pero muy incompleto

Avances:
- hay 18 familias aceptadas
- varias son utiles y razonables:
  - `chart_authorities`
  - `house_classification`
  - `house_qualities`
  - `planetary_phases`
  - `configuration`

Errores:
- varias familias importantes siguen subrepresentadas
- `lots` es demasiado pobre para el contenido real del volumen
- falta mejor cobertura para:
  - testimonios
  - lotes
  - timing techniques
  - rulers beyond chart authorities

Posibilidades:
- el sistema de familias ya es rescatable
- pero necesita mucha mejor discovery para salir del nivel “base”

### 9. `knowledge_family_candidates.json`

Estado:
- problematico

Avances:
- deja visible el estado del discovery y no oculta el fallo

Errores:
- `discovery_error`: `Invalid control character`
- `candidate_families`: vacio
- `left_unclustered`: 48 conceptos

Esto es un fallo real, no solo debilidad.

Posibilidades:
- corregir el parser/normalizador de salida de discovery
- hasta que eso no se resuelva, no conviene confiar demasiado en la capa de discovery automatico de familias

### 10. `knowledge_taxonomy.json`

Estado:
- claramente insuficiente

Avances:
- al menos detecta bien el patron estructural de `house angularity -> angular/succedent/cadent`

Errores:
- solo 3 links
- demasiado pobre para 135 conceptos

Posibilidades:
- taxonomy inference necesita otra iteracion completa
- hoy no es una capa robusta del sistema

### 11. `knowledge_ontology.json`

Estado:
- amplia, pero requiere cautela

Avances:
- 157 nodos para 135 conceptos indica que ya hay tejido relacional
- sirve para explorer y related concepts

Errores:
- parte de esas relaciones probablemente hereda ruido de la consolidacion
- mientras `families` y `taxonomy` sigan verdes, la ontology completa no puede tomarse como madurez estructural plena

Posibilidades:
- buena base para navegacion
- todavia no buena base para evaluacion final de calidad doctrinal

### 12. `knowledge_metrics_report.json`

Estado:
- no util para auditar esta corrida completa

Errores:
- reporta `15` chunks totales
- incluye nota explicita: `no LLM re-extraction was performed due connection errors in this environment`
- no corresponde al artifact completo actual

Conclusión:
- tratarlo como stale o no representativo
- no usarlo para decisiones sobre calidad del set actual

### 13. `document_map.json`

Estado:
- util, pero ruidoso

Avances:
- 998 secciones generadas
- estructura suficiente para chunking y explorer

Errores:
- 343 secciones `unknown`
- bastante ruido de headings y material no doctrinal

Posibilidades:
- suficientemente bueno para estructura
- no suficientemente limpio para considerarlo ya resuelto

## Balance general

### Avances reales

- la capa procedural ya es real y no anecdótica
- `knowledge_chunks`, `knowledge_concepts`, `procedural_audit` y parte de `procedure_frames` ya justifican el rediseño
- `selection`, `timing` y parte de `evaluation` ya tienen evidencia fuerte en el volumen completo

### Errores importantes

- `summary.txt` sigue siendo demasiado pobre como compendio doctrinal
- `predominator` esta sobrecargado y contaminado
- `oikodespotes` esta infrarrepresentado en frames
- `family candidate discovery` fallo
- `taxonomy` sigue casi vacia
- `knowledge_metrics_report` no representa la corrida actual

## Prioridades recomendadas

### Prioridad 1

- limpiar ownership procedural:
  - sacar de `predominator` lo que pertenece a `oikodespotes` y `profections`
- reconstruir `determine_oikodespotes`
- añadir frame para `kurio`

### Prioridad 2

- reparar `family_candidate_discovery`
- reforzar `taxonomy`

### Prioridad 3

- rediseñar `summary.txt` para que deje de perder casi toda la ganancia procedural

## Juicio final

El motor ya no esta en fase “experimental ciega”. La capa de conocimiento estructurado del volumen completo ya produce valor real. Pero el set completo todavia no puede considerarse doctrinalmente estable de punta a punta, porque la capa final de sintesis y parte de la estructura relacional siguen bastante por debajo de la calidad alcanzada por la extraccion procedural.
