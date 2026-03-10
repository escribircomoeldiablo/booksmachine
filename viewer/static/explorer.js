const state = {
  books: [],
  book: null,
  overview: null,
  family: null,
  concept: null,
  tree: null,
};

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

async function init() {
  const data = await fetchJson("/api/books");
  state.books = data.books || [];
  renderBookOptions();
  const initialBook = data.default_book || state.books[0]?.slug;
  if (initialBook) {
    document.getElementById("book-select").value = initialBook;
    await loadBook(initialBook);
  }
  bindEvents();
}

function bindEvents() {
  document.getElementById("book-select").addEventListener("change", async (event) => {
    await loadBook(event.target.value);
  });

  document.getElementById("search-input").addEventListener("input", debounce(handleSearch, 150));
  document.addEventListener("click", (event) => {
    const results = document.getElementById("search-results");
    if (!results.contains(event.target) && event.target.id !== "search-input") {
      results.classList.add("hidden");
    }
  });
}

function renderBookOptions() {
  const select = document.getElementById("book-select");
  select.innerHTML = state.books
    .map((book) => `<option value="${escapeHtml(book.slug)}">${escapeHtml(book.title)}</option>`)
    .join("");
}

async function loadBook(bookSlug) {
  state.book = bookSlug;
  state.overview = await fetchJson(`/api/books/${encodeURIComponent(bookSlug)}/overview`);
  state.family = state.overview.initial_family;
  renderOverview();
  renderFamilies();
  await loadFamily(state.family, state.overview.initial_concept);
}

async function loadFamily(familyLabel, conceptKey = null) {
  state.family = familyLabel;
  state.tree = await fetchJson(
    `/api/books/${encodeURIComponent(state.book)}/tree?family=${encodeURIComponent(familyLabel)}`
  );
  renderFamilies();
  renderTree();
  const nextConcept = conceptKey || state.tree.selected_concept;
  if (nextConcept) {
    await loadConcept(nextConcept);
  } else {
    renderConcept(null);
    renderEvidence([]);
  }
}

async function loadConcept(conceptKey) {
  state.concept = await fetchJson(
    `/api/books/${encodeURIComponent(state.book)}/concept/${encodeURIComponent(conceptKey)}`
  );
  if (state.concept.family && state.concept.family !== "Unassigned") {
    state.family = state.concept.family;
  }
  renderFamilies();
  renderTree();
  renderConcept(state.concept);
  renderEvidence(state.concept.summary_blocks || []);
}

function renderOverview() {
  const { book, stats } = state.overview;
  document.getElementById("book-meta").textContent =
    `${book.title} · ${stats.concept_count} conceptos · ${stats.family_count} familias · ${stats.block_count} bloques`;
}

function renderFamilies() {
  const list = document.getElementById("family-list");
  const families = state.overview?.families || [];
  document.getElementById("family-count").textContent = `${families.length} familias`;
  list.innerHTML = families
    .map((family) => {
      const active = family.label === state.family ? "active" : "";
      return `
        <button class="family-item ${active}" data-family="${escapeHtml(family.label)}">
          <span>${escapeHtml(family.label)}</span>
          <strong>${family.concept_count}</strong>
        </button>
      `;
    })
    .join("");
  list.querySelectorAll(".family-item").forEach((node) => {
    node.addEventListener("click", async () => {
      await loadFamily(node.dataset.family);
    });
  });
}

function renderTree() {
  const container = document.getElementById("tree-view");
  document.getElementById("tree-family").textContent = state.family || "sin familia";
  if (!state.tree?.tree) {
    container.innerHTML = `<p class="muted">No ontology available.</p>`;
    return;
  }
  const markup = renderTreeNode(state.tree.tree, true);
  container.innerHTML = markup;
  container.querySelectorAll("[data-concept]").forEach((node) => {
    node.addEventListener("click", async () => {
      await loadConcept(node.dataset.concept);
    });
  });
}

function renderTreeNode(node, isRoot = false) {
  const conceptKey = node.kind === "family_root" ? "" : node.id;
  const isActive = state.concept?.concept_key === conceptKey ? "active" : "";
  const button = isRoot
    ? ""
    : `<button class="tree-node ${isActive}" data-concept="${escapeHtml(conceptKey)}">
         <span>${escapeHtml(node.label)}</span>
         <small>${escapeHtml(node.kind)}</small>
       </button>`;
  const children = (node.children || []).map((child) => renderTreeNode(child)).join("");
  if (isRoot) {
    return `<div class="tree-root">${children || `<p class="muted">No concepts for this family.</p>`}</div>`;
  }
  return `<div class="tree-branch">${button}${children ? `<div class="tree-children">${children}</div>` : ""}</div>`;
}

function renderConcept(concept) {
  const container = document.getElementById("concept-card");
  if (!concept) {
    container.innerHTML = `<p class="muted">Selecciona un concepto.</p>`;
    return;
  }
  container.innerHTML = `
    <div class="concept-header">
      <p class="eyebrow">${escapeHtml(concept.family)}</p>
      <h2>${escapeHtml(concept.concept_name)}</h2>
      <p class="breadcrumb">${escapeHtml((concept.breadcrumb || []).join(" → "))}</p>
    </div>

    <section class="card-section">
      <h3>Definicion</h3>
      <p>${escapeHtml(concept.definition_primary || "No consolidated definition available.")}</p>
      ${renderList("Variantes", concept.definition_variants)}
    </section>

    <section class="card-section metrics">
      ${metricChip("Source chunks", concept.metrics.source_chunks_count)}
      ${metricChip("Summary blocks", concept.metrics.summary_blocks_count)}
      ${metricChip("Direct relations", concept.metrics.direct_relations_count)}
    </section>

    <section class="card-section">
      <h3>Procedure</h3>
      ${renderProcedureFrame(concept.procedure_frame)}
      ${renderProcedureSection(concept)}
    </section>

    <section class="card-section">
      <h3>Relaciones</h3>
      ${renderRelationGrid(concept.relations)}
    </section>

    <section class="card-section">
      <h3>Related concepts</h3>
      ${renderRelatedConcepts(concept.related_concepts)}
    </section>

    <section class="card-section">
      <h3>Terminologia asociada</h3>
      ${renderTagGroup("Terminology", concept.terminology)}
      ${renderTagGroup("Synonyms", concept.synonyms)}
      ${renderTagGroup("Variants", concept.variants)}
    </section>

    <section class="card-section">
      <h3>Evidencia del manual</h3>
      ${renderEvidenceCards(concept.summary_blocks)}
      ${renderChunkEvidence(concept.source_chunks)}
    </section>
  `;
  container.querySelectorAll("[data-related-concept]").forEach((node) => {
    node.addEventListener("click", async () => {
      await loadConcept(node.dataset.relatedConcept);
    });
  });
}

function renderRelationGrid(relations) {
  return `
    <div class="relation-grid">
      ${relationColumn("belongs_to", relations.belongs_to)}
      ${relationColumn("parent", relations.parent)}
      ${relationColumn("children", relations.children)}
      ${relationColumn("related_to", relations.related_to)}
      ${relationColumn("contrasts_with", relations.contrasts_with)}
      ${relationColumn("depends_on", relations.depends_on)}
      ${relationColumn("used_in", relations.used_in)}
    </div>
  `;
}

function relationColumn(label, values) {
  const items = values?.length ? values.map((value) => `<li>${escapeHtml(value)}</li>`).join("") : `<li class="muted">—</li>`;
  return `<div class="relation-column"><h4>${escapeHtml(label)}</h4><ul>${items}</ul></div>`;
}

function renderTagGroup(label, values) {
  if (!values?.length) {
    return "";
  }
  return `
    <div class="tag-group">
      <h4>${escapeHtml(label)}</h4>
      <div class="tags">${values.map((value) => `<span class="tag">${escapeHtml(value)}</span>`).join("")}</div>
    </div>
  `;
}

function renderList(label, values) {
  if (!values?.length) {
    return "";
  }
  return `
    <div class="sublist">
      <h4>${escapeHtml(label)}</h4>
      <ul>${values.map((value) => `<li>${escapeHtml(value)}</li>`).join("")}</ul>
    </div>
  `;
}

function renderRelatedConcepts(values) {
  if (!values?.length) {
    return `<p class="muted">No related concepts found from existing artifacts.</p>`;
  }
  return `
    <div class="related-concepts">
      ${values
        .map(
          (value) => `
            <button class="related-concept" data-related-concept="${escapeHtml(normalizeKey(value))}">
              ${escapeHtml(value)}
            </button>
          `
        )
        .join("")}
    </div>
  `;
}

function renderProcedureSection(concept) {
  const parts = [
    renderProcedureSteps(concept.shared_procedure),
    renderDecisionRules(concept.decision_rules),
    renderConditions("Preconditions", concept.preconditions),
    renderConditions("Exceptions", concept.exceptions),
    renderAuthorVariants(concept.author_variant_overrides),
    renderProcedureOutputs(concept.procedure_outputs),
  ].filter(Boolean);
  if (!parts.length) {
    return `<p class="muted">No procedural structure extracted for this concept.</p>`;
  }
  return parts.join("");
}

function renderProcedureFrame(frame) {
  if (!frame) return "";
  const parts = [
    frame.goal ? `<p class="procedure-goal">${escapeHtml(frame.goal)}</p>` : "",
    renderInlineLinks("Anchor concepts", frame.anchor_concepts),
    renderInlineLinks("Supporting concepts", frame.supporting_concepts),
    renderProcedureSteps(frame.shared_steps),
    renderDecisionRules(frame.decision_rules),
    renderConditions("Preconditions", frame.preconditions),
    renderConditions("Exceptions", frame.exceptions),
    renderAuthorVariants(frame.author_variant_overrides),
    renderProcedureOutputs(frame.procedure_outputs),
    renderInlineLinks("Related concepts", frame.related_concepts),
  ].filter(Boolean);
  return `
    <div class="procedure-frame">
      <h4>Procedure frame: ${escapeHtml(frame.label)}</h4>
      ${parts.join("")}
    </div>
  `;
}

function renderInlineLinks(label, values) {
  if (!values?.length) return "";
  return `
    <div class="tag-group">
      <h4>${escapeHtml(label)}</h4>
      <div class="related-concepts">
        ${values
          .map(
            (value) => `
              <button class="related-concept" data-related-concept="${escapeHtml(normalizeKey(value))}">
                ${escapeHtml(value)}
              </button>
            `
          )
          .join("")}
      </div>
    </div>
  `;
}

function renderProcedureSteps(steps) {
  if (!steps?.length) return "";
  return `
    <div class="procedure-block">
      <h4>Shared procedure</h4>
      <ol class="procedure-list">
        ${steps.map((step) => `<li><strong>${escapeHtml(step.id)}</strong> ${escapeHtml(step.text)}</li>`).join("")}
      </ol>
    </div>
  `;
}

function renderDecisionRules(rules) {
  if (!rules?.length) return "";
  return `
    <div class="procedure-block">
      <h4>Decision rules</h4>
      <ul class="sublist">${rules
        .map(
          (item) =>
            `<li>if ${escapeHtml(item.condition)} -> ${escapeHtml(item.outcome)}${renderRelatedSteps(item.related_steps)}</li>`
        )
        .join("")}</ul>
    </div>
  `;
}

function renderConditions(label, items) {
  if (!items?.length) return "";
  return `
    <div class="procedure-block">
      <h4>${escapeHtml(label)}</h4>
      <ul class="sublist">${items
        .map((item) => `<li>${escapeHtml(item.text)}${item.scope ? ` <small>${escapeHtml(item.scope)}</small>` : ""}${renderRelatedSteps(item.related_steps)}</li>`)
        .join("")}</ul>
    </div>
  `;
}

function renderAuthorVariants(items) {
  if (!items?.length) return "";
  return `
    <div class="procedure-block">
      <h4>Author variants</h4>
      <ul class="sublist">${items
        .map(
          (item) =>
            `<li><strong>${escapeHtml(item.author)}</strong> <span class="variant-op">${escapeHtml(
              item.operation || item.kind
            )}</span> ${escapeHtml(item.text)}${renderRelatedSteps(item.related_steps)}</li>`
        )
        .join("")}</ul>
    </div>
  `;
}

function renderProcedureOutputs(items) {
  if (!items?.length) return "";
  return `
    <div class="procedure-block">
      <h4>Procedure outputs</h4>
      <ul class="sublist">${items.map((item) => `<li>${escapeHtml(item.text)}</li>`).join("")}</ul>
    </div>
  `;
}

function renderRelatedSteps(values) {
  if (!values?.length) return "";
  return ` <small>[steps: ${escapeHtml(values.join(", "))}]</small>`;
}

function renderEvidenceCards(blocks) {
  if (!blocks?.length) {
    return `<p class="muted">No related summary blocks found.</p>`;
  }
  return blocks
    .map(
      (block) => `
        <article class="evidence-card">
          <div class="evidence-head">
            <strong>${escapeHtml(block.block_id)}</strong>
            <span>${escapeHtml((block.related_concepts || []).join(", "))}</span>
          </div>
          <p>${escapeHtml(block.block_text)}</p>
        </article>
      `
    )
    .join("");
}

function renderChunkEvidence(chunks) {
  if (!chunks?.length) {
    return `<p class="muted">No source chunks linked to this concept.</p>`;
  }
  return `
    <div class="chunk-evidence">
      ${chunks
        .map(
          (chunk) => `
            <article class="chunk-card">
              <strong>Chunk ${chunk.chunk_id}</strong>
              <pre>${escapeHtml(chunk.chunk_text)}</pre>
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

function renderEvidence(blocks) {
  const container = document.getElementById("evidence-view");
  document.getElementById("evidence-count").textContent = `${blocks.length} bloques`;
  if (!blocks.length) {
    container.innerHTML = `<p class="muted">No related blocks.</p>`;
    return;
  }
  const highlightContext = buildHighlightContext(state.concept);
  container.innerHTML = blocks
    .map(
      (block) => `
        <article class="block-card">
          <div class="evidence-head">
            <strong>${escapeHtml(block.block_id)}</strong>
            <span>${escapeHtml((block.related_concepts || []).join(", "))}</span>
          </div>
          <p>${highlightBlockText(block.block_text, highlightContext)}</p>
        </article>
      `
    )
    .join("");
}

function buildHighlightContext(concept) {
  if (!concept) {
    return { active: [], terminology: [], related: [] };
  }
  return {
    active: dedupeTerms([concept.concept_name]),
    terminology: dedupeTerms([...(concept.terminology || []), ...(concept.synonyms || []), ...(concept.variants || [])]).filter(
      (term) => term.toLowerCase() !== concept.concept_name.toLowerCase()
    ),
    related: dedupeTerms(concept.related_concepts || []).filter(
      (term) => term.toLowerCase() !== concept.concept_name.toLowerCase()
    ),
  };
}

function highlightBlockText(text, context) {
  const matches = [
    ...collectMatches(text, context.related, "related", 3),
    ...collectMatches(text, context.terminology, "term", 2),
    ...collectMatches(text, context.active, "active", 1),
  ];
  if (!matches.length) {
    return escapeHtml(text);
  }

  matches.sort((left, right) => {
    if (left.priority !== right.priority) {
      return left.priority - right.priority;
    }
    if (right.end - right.start !== left.end - left.start) {
      return right.end - right.start - (left.end - left.start);
    }
    return left.start - right.start;
  });

  const accepted = [];
  for (const match of matches) {
    if (accepted.some((item) => rangesOverlap(item, match))) {
      continue;
    }
    accepted.push(match);
  }
  accepted.sort((left, right) => left.start - right.start);

  let cursor = 0;
  let html = "";
  for (const match of accepted) {
    html += escapeHtml(text.slice(cursor, match.start));
    html += `<mark class="hl hl-${match.kind}">${escapeHtml(text.slice(match.start, match.end))}</mark>`;
    cursor = match.end;
  }
  html += escapeHtml(text.slice(cursor));
  return html;
}

function collectMatches(text, terms, kind, priority) {
  const lowered = text.toLowerCase();
  const matches = [];
  const orderedTerms = [...terms].sort((left, right) => right.length - left.length);
  for (const term of orderedTerms) {
    const raw = String(term || "").trim();
    if (!raw) {
      continue;
    }
    const needle = raw.toLowerCase();
    let fromIndex = 0;
    while (fromIndex < lowered.length) {
      const start = lowered.indexOf(needle, fromIndex);
      if (start === -1) {
        break;
      }
      const end = start + needle.length;
      if (hasTermBoundaries(text, start, end, raw)) {
        matches.push({ start, end, kind, priority });
      }
      fromIndex = start + 1;
    }
  }
  return matches;
}

function hasTermBoundaries(text, start, end, term) {
  const first = term[0];
  const last = term[term.length - 1];
  const leftChar = start > 0 ? text[start - 1] : "";
  const rightChar = end < text.length ? text[end] : "";
  const needsLeftBoundary = /\w/.test(first);
  const needsRightBoundary = /\w/.test(last);
  if (needsLeftBoundary && /\w/.test(leftChar)) {
    return false;
  }
  if (needsRightBoundary && /\w/.test(rightChar)) {
    return false;
  }
  return true;
}

function rangesOverlap(left, right) {
  return left.start < right.end && right.start < left.end;
}

function dedupeTerms(values) {
  const seen = new Set();
  const output = [];
  for (const value of values) {
    const text = String(value || "").trim();
    const key = text.toLowerCase();
    if (!text || seen.has(key)) {
      continue;
    }
    seen.add(key);
    output.push(text);
  }
  return output;
}

function normalizeKey(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

async function handleSearch(event) {
  const query = event.target.value.trim();
  const panel = document.getElementById("search-results");
  if (!query) {
    panel.classList.add("hidden");
    panel.innerHTML = "";
    return;
  }
  const data = await fetchJson(
    `/api/books/${encodeURIComponent(state.book)}/search?q=${encodeURIComponent(query)}`
  );
  if (!data.results.length) {
    panel.innerHTML = `<div class="search-item muted">Sin resultados</div>`;
    panel.classList.remove("hidden");
    return;
  }
  panel.innerHTML = data.results
    .map((result) => {
      if (result.type === "family") {
        return `<button class="search-item" data-result-type="family" data-family="${escapeHtml(result.family)}">${escapeHtml(
          result.family
        )} <small>${result.concept_count} conceptos</small></button>`;
      }
      return `<button class="search-item" data-result-type="concept" data-concept="${escapeHtml(result.concept_key)}" data-family="${escapeHtml(
        result.family
      )}">${escapeHtml(result.concept_name)} <small>${escapeHtml(result.family)}</small></button>`;
    })
    .join("");
  panel.classList.remove("hidden");
  panel.querySelectorAll('[data-result-type="family"]').forEach((node) => {
    node.addEventListener("click", async () => {
      panel.classList.add("hidden");
      await loadFamily(node.dataset.family);
    });
  });
  panel.querySelectorAll('[data-result-type="concept"]').forEach((node) => {
    node.addEventListener("click", async () => {
      panel.classList.add("hidden");
      if (node.dataset.family && node.dataset.family !== "Unassigned") {
        await loadFamily(node.dataset.family, node.dataset.concept);
      } else {
        await loadConcept(node.dataset.concept);
      }
    });
  });
}

function metricChip(label, value) {
  return `<div class="metric-chip"><span>${escapeHtml(label)}</span><strong>${value}</strong></div>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function debounce(fn, wait) {
  let timer = null;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), wait);
  };
}

init().catch((error) => {
  document.getElementById("concept-card").innerHTML = `<p class="muted">Error loading explorer: ${escapeHtml(
    error.message
  )}</p>`;
});
