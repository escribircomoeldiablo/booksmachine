# Procedural Benchmark Plan

## Objetivo

Medir si el motor ya recoge y organiza procedimientos doctrinales de forma suficientemente general, sin depender de impresiones o de un solo caso exitoso.

Este benchmark no busca demostrar perfeccion. Busca responder tres preguntas:

- que tipos de procedimiento ya salen bien
- cuales siguen fallando
- si ya tiene sentido correr libros completos con esta arquitectura

## Regla de uso

Cada caso del benchmark debe evaluarse sobre artifacts regenerados con el pipeline procedural actual.

Para cada procedimiento se revisa:

- `procedure_frame` existe o no
- el `frame_type` es correcto o no
- hay `shared_steps` o `decision_rules` suficientes
- las variantes autorales se conservan cuando corresponde
- no hay contaminacion fuerte desde conceptos vecinos
- hay evidencia trazable a chunks

## Escala de scoring

- `0` = fallo claro
- `1` = existe pero sigue siendo confuso o muy incompleto
- `2` = util
- `3` = fuerte

## Criterio de aprobacion

El sistema pasa esta fase si cumple:

- promedio global `>= 2`
- ningun caso critico en `0`
- al menos un caso fuerte por tipo principal:
  - `selection`
  - `timing`
  - `evaluation`

## Casos propuestos

| Procedure ID | Tipo | Objetivo de validacion | Estado actual |
| --- | --- | --- | --- |
| `determine_predominator` | `selection` | Probar seleccion con fallback y conceptos vecinos | Parcialmente validado |
| `determine_oikodespotes` | `selection` | Probar seleccion con metodos rivales por autor | Parcialmente validado |
| `evaluate_oikodespotes` | `evaluation` | Probar juicio de condicion y efectos | Parcialmente validado |
| `apply_profections` | `timing` | Probar tecnica temporal lineal con pasos claros | Parcialmente validado |
| `circumambulations_through_bounds` | `timing` | Probar secuencia de senores del tiempo mas compleja | Pendiente |
| `determine_annual_lord` | `timing` | Ver si el sistema distingue o colapsa bien frente a profections | Pendiente |
| `determine_prenatal_lunation` | `selection` | Probar criterio tecnico relativamente concreto | Validado indirectamente dentro de `determine_predominator` |
| `determine_lot_of_fortune_or_spirit_usage` | `selection` | Probar seleccion de puntos derivados de las luces | Pendiente |
| `classify_house_angularity` | `ranking/comparison` | Probar procedimientos de clasificacion y prioridad | Pendiente |
| `determine_witnessing_for_master` | `fallback/comparison` | Probar criterios relacionales aplicados a seleccion | Pendiente |

## Rubrica por caso

Para cada procedimiento, registrar:

- `frame_exists`
- `frame_type_correct`
- `anchor_concepts_correct`
- `shared_steps_or_rules_present`
- `author_variants_preserved_if_expected`
- `major_contamination_absent`
- `evidence_present`
- `score_0_to_3`
- `notes`

## Plantilla de registro

```md
### Procedure: determine_predominator

- frame_exists:
- frame_type_correct:
- anchor_concepts_correct:
- shared_steps_or_rules_present:
- author_variants_preserved_if_expected:
- major_contamination_absent:
- evidence_present:
- score_0_to_3:
- notes:
```

## Primera evaluacion provisional

### Procedure: determine_predominator

- `frame_exists`: si
- `frame_type_correct`: si, aunque el artifact actual no expone `frame_type`
- `anchor_concepts_correct`: si
- `shared_steps_or_rules_present`: si, `3 shared_steps` y `3 decision_rules`
- `author_variants_preserved_if_expected`: si, `3 author_variant_overrides`
- `major_contamination_absent`: bastante si
- `evidence_present`: si
- `score_0_to_3`: `3`
- `notes`: subio de nivel. Ahora el frame separa mejor el nucleo de seleccion en `candidate_priority_rules` y `fallback_rules`, y mueve las observaciones de `house system` a `methodological_notes`. Ya se siente como un procedimiento de seleccion legible y no solo como una agregacion de reglas.

### Procedure: determine_oikodespotes

- `frame_exists`: si
- `frame_type_correct`: si
- `anchor_concepts_correct`: si
- `shared_steps_or_rules_present`: si, `3 shared_steps` y `4 decision_rules`
- `author_variants_preserved_if_expected`: si, `7 author_method_variants` y `2 author_variant_overrides`
- `major_contamination_absent`: mayormente si
- `evidence_present`: si
- `score_0_to_3`: `2`
- `notes`: mejoro bastante con `candidate_priority_rules` y `fallback_rules`, y ya no mezcla evaluacion con seleccion. Pero sigue dependiendo mucho de metodos autorales rivales y el nucleo comun todavia no es tan fuerte ni tan compacto como en `predominator`.

### Procedure: evaluate_oikodespotes

- `frame_exists`: si
- `frame_type_correct`: si
- `anchor_concepts_correct`: si
- `shared_steps_or_rules_present`: si, `3 shared_steps`, `5 decision_rules` y `2 preconditions`
- `author_variants_preserved_if_expected`: parcialmente; aqui no era el foco principal
- `major_contamination_absent`: si
- `evidence_present`: si
- `score_0_to_3`: `3`
- `notes`: es el frame mas convincente de los evaluados. Ya separa bien evaluacion de seleccion y conserva condiciones doctrinales utiles para juicio de estado y efectos.

### Procedure: apply_profections

- `frame_exists`: si
- `frame_type_correct`: si
- `anchor_concepts_correct`: si
- `shared_steps_or_rules_present`: si, `5 shared_steps`
- `author_variants_preserved_if_expected`: si, al menos la variante terminologica de Ptolemy
- `major_contamination_absent`: si
- `evidence_present`: si
- `score_0_to_3`: `3`
- `notes`: es el mejor caso de tecnica lineal. La secuencia sale limpia, no depende de demasiada reconstruccion y valida que el extractor ya puede generalizar fuera del cluster de longevidad.

### Procedure: determine_prenatal_lunation

- `frame_exists`: si, pero integrado dentro de `determine_predominator`
- `frame_type_correct`: si
- `anchor_concepts_correct`: si, como rama del arbol de seleccion del Predominador
- `shared_steps_or_rules_present`: si, `10 shared_steps` y `17 decision_rules`
- `author_variants_preserved_if_expected`: parcialmente; el extracto se concentra mas en ramas procedurales que en disputa autoral compacta
- `major_contamination_absent`: si
- `evidence_present`: si
- `score_0_to_3`: `3`
- `notes`: este caso confirma que el sistema ya puede absorber candidatos alternativos dentro de un procedimiento de seleccion complejo. `Prenatal Lunation` no emerge como frame separado, pero si queda recogido correctamente dentro del arbol de `determine_predominator`, que en este caso es el comportamiento adecuado.

### Resultado provisional de los 4 casos iniciales

- promedio provisional: `2.75`
- casos en `0`: `0`
- caso fuerte en `evaluation`: si
- caso fuerte en `timing`: si
- caso fuerte en `selection`: si

Lectura:

- la arquitectura ya paso de viable a util
- `timing` y `evaluation` ya muestran fuerza real
- `selection` ya tiene al menos un caso fuerte y otro caso util
- aun conviene medir 2 o 3 casos extra de `selection` antes de justificar una corrida completa con confianza alta

## Estado tras el caso prenatal_lunation

- `selection` ya tiene dos casos fuertes:
  - `determine_predominator`
  - `determine_prenatal_lunation` como rama integrada del arbol de seleccion del Predominador
- el siguiente paso ya no deberia ser otro parche local de aliasing o matching
- el siguiente paso razonable es una validacion de escala intermedia:
  - un tramo mayor de `Vol 2`
  - o directamente una corrida completa de `Vol 2` si aceptas que todavia puede aparecer ruido residual

## Orden recomendado

1. Reusar primero los 4 casos ya trabajados:
   - `determine_predominator`
   - `determine_oikodespotes`
   - `evaluate_oikodespotes`
   - `apply_profections`
2. Añadir luego 2 casos de `timing` mas complejos.
3. Añadir despues 2 casos de `selection` tecnica.
4. Cerrar con 2 casos de `ranking/comparison` o `fallback`.

## Interpretacion

Si el benchmark sale bien, la arquitectura ya no depende de casos especiales y se puede justificar una corrida completa de libro.

Si sale mal, la siguiente iteracion no debe centrarse en viewer ni compendio final, sino en:

- taxonomia de tipos de procedimiento
- reglas de extraccion por clase procedural
- criterios de asignacion de evidencia al frame
- dedupe y limpieza de reglas
