const state = {
    scope: "mixed",
    venue: "",
    year: "",
    venues: [],
    years: [],
    domains: [],
    topics: [],
    wordcloudLoaded: false,
    wordcloudLoading: false,
    resolveTimer: null,
    latestExplorerResponse: null,
};

const SCOPE_LABEL_KEYS = {
    preprint: "index.scope.preprint",
    accepted: "index.scope.accepted",
    mixed: "index.scope.mixed",
};

const SCOPE_NOTE_KEYS = {
    preprint: "index.scope.note.preprint",
    accepted: "index.scope.note.accepted",
    mixed: "index.scope.note.mixed",
};

async function init() {
    setupScopeSwitcher();
    setupExplorer();
    setupKeywordFilters();
    setupWordcloudObserver();
    setupNavHighlighting();
    setupLanguageRefresh();
    updateScopeText();

    const overviewPromise = loadOverview();
    loadQualityReport();
    loadTaxonomy();
    loadTopKeywords();
    loadTrends();

    try {
        await overviewPromise;
        await loadFilters();
        await loadVenueCards();
        await loadDefaultExplorer();
    } catch (error) {
        console.error("Failed to initialize dashboard", error);
        showInlineError("quality-warning-list", "Dashboard initialization failed. Existing static pages are still available.");
    }
}

async function loadOverview() {
    try {
        const response = await API.getOverviewV01();
        const data = response.data || response;
        setText("stat-papers", formatNumber(data.total_papers));
        setText("stat-keywords", formatNumber(data.total_keywords));
        setText("stat-venues", formatNumber(data.total_venues));
        setText("stat-years", data.year_range || "N/A");
        removeSkeletons(document.querySelector(".stats-grid"));

        state.venues = data.venues || [];
        state.years = data.years || [];
        renderContractWarnings("quality-warning-list", response.warnings || [], "No global quality warnings from overview.");
    } catch (error) {
        console.error("Failed to load overview", error);
        showInlineError("quality-warning-list", "Unable to load overview data.");
    }
}

async function loadQualityReport(scopeOverride = null) {
    const scope = scopeOverride || scopeToQualityQuery(state.scope);
    try {
        const response = await API.getDataQualityReport(scope);
        const metrics = response.data?.metrics || {};
        renderQualityWarnings(response.warnings || []);
        renderQualityMetrics(metrics);
        renderSourceBreakdown(metrics.source_breakdown || {});
    } catch (error) {
        console.error("Failed to load quality report", error);
        showInlineError("quality-warning-list", "Unable to load data quality report.");
        renderQualityMetrics({});
    }
}

async function loadTaxonomy() {
    try {
        const [domainsResponse, topicsResponse] = await Promise.all([
            API.getDomains(),
            API.getTopics(),
        ]);
        state.domains = domainsResponse.data?.domains || [];
        state.topics = topicsResponse.data?.topics || [];
        renderDomains(state.domains, state.topics, domainsResponse.warnings || []);
        renderTopics(state.topics, topicsResponse.warnings || []);
    } catch (error) {
        console.error("Failed to load taxonomy", error);
        showInlineError("domain-grid", "Taxonomy metadata is not available.");
        showInlineError("topic-cards", "Topic taxonomy metadata is not available.");
    }
}

async function loadFilters() {
    const selectedVenue = document.getElementById("filter-venue")?.value || "";
    const selectedYear = document.getElementById("filter-year")?.value || "";
    const explorerVenue = document.getElementById("explorer-venue")?.value || "";
    const explorerYear = document.getElementById("explorer-year")?.value || "";

    populateSelect("filter-venue", state.venues, t("index.keyword.allVenues", "All venues"));
    populateSelect("explorer-venue", state.venues, t("index.explorer.venue", "Select venue"));
    populateSelect("filter-year", state.years, t("index.keyword.allYears", "All years"), true);
    populateSelect("explorer-year", state.years, t("index.explorer.year", "Select year"), true);

    setControlValue("filter-venue", selectedVenue);
    setControlValue("filter-year", selectedYear);
    setControlValue("explorer-venue", explorerVenue);
    setControlValue("explorer-year", explorerYear);
}

function setupScopeSwitcher() {
    document.querySelectorAll(".scope-option").forEach((button) => {
        button.addEventListener("click", () => {
            state.scope = button.dataset.scope || "mixed";
            document.querySelectorAll(".scope-option").forEach((item) => {
                const active = item === button;
                item.classList.toggle("active", active);
                item.setAttribute("aria-pressed", active ? "true" : "false");
            });
            updateScopeText();
            loadQualityReport();
        });
    });
}

function setupLanguageRefresh() {
    document.addEventListener("deeptrender:language-changed", () => {
        updateScopeText();
        if (state.domains.length || state.topics.length) {
            renderDomains(state.domains, state.topics, []);
            renderTopics(state.topics, []);
        }
        if (state.latestExplorerResponse) {
            renderExplorerResponse(state.latestExplorerResponse);
            renderTopicFrequencyFromExplorer(state.latestExplorerResponse);
        }
        loadFilters();
    });
}

function updateScopeText() {
    setText("scope-note", t(SCOPE_NOTE_KEYS[state.scope], ""));
    setText("active-scope-badge", t(SCOPE_LABEL_KEYS[state.scope], "Structured Mixed"));
}

function setupExplorer() {
    const form = document.getElementById("topic-explorer-form");
    const topicInput = document.getElementById("explorer-topic");
    const includeChildren = document.getElementById("explorer-include-children");
    if (form) {
        form.addEventListener("submit", (event) => {
            event.preventDefault();
            runTopicExplorer();
        });
    }
    [topicInput, includeChildren].forEach((control) => {
        control?.addEventListener("input", () => debounceTopicPreview());
        control?.addEventListener("change", () => debounceTopicPreview());
    });
}

function setupKeywordFilters() {
    const venueSelect = document.getElementById("filter-venue");
    const yearSelect = document.getElementById("filter-year");
    venueSelect?.addEventListener("change", () => {
        state.venue = venueSelect.value;
        refreshData();
    });
    yearSelect?.addEventListener("change", () => {
        state.year = yearSelect.value;
        refreshData();
    });
}

function setupWordcloudObserver() {
    const panel = document.getElementById("wordcloud-panel");
    if (!panel) {
        return;
    }
    if (!("IntersectionObserver" in window)) {
        window.setTimeout(() => loadWordcloud(), 1200);
        return;
    }
    const observer = new IntersectionObserver((entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
            observer.disconnect();
            loadWordcloud();
        }
    }, { rootMargin: "160px" });
    observer.observe(panel);
}

function setupNavHighlighting() {
    document.querySelectorAll(".nav-link[href^='#']").forEach((link) => {
        link.addEventListener("click", () => {
            document.querySelectorAll(".nav-link").forEach((item) => item.classList.remove("active"));
            link.classList.add("active");
        });
    });
}

async function loadDefaultExplorer() {
    const venue = state.venues[0];
    const year = [...state.years].sort((a, b) => b - a)[0];
    const preferredTopic = state.topics.find((topic) => topic.topic_id === "transformer")
        || state.topics.find((topic) => topic.topic_id === "large_language_model")
        || state.topics[0];
    if (!venue || !year || !preferredTopic) {
        Charts.showEmpty("chart-topic-frequency", "Select a venue, year, and topic to render relative_frequency.");
        return;
    }

    setControlValue("explorer-venue", venue);
    setControlValue("explorer-year", year);
    setControlValue("explorer-topic", preferredTopic.topic_id || preferredTopic.canonical_name);
    await previewTopicNormalization();
    await runTopicExplorer({ quiet: true });
}

async function runTopicExplorer(options = {}) {
    const venue = document.getElementById("explorer-venue")?.value;
    const year = document.getElementById("explorer-year")?.value;
    const topic = document.getElementById("explorer-topic")?.value.trim();
    const includeChildren = document.getElementById("explorer-include-children")?.checked || false;
    const container = document.getElementById("explorer-results");

    if (!venue || !year || !topic) {
        if (!options.quiet) {
            renderExplorerEmpty("Select a venue, year, and topic before searching.");
        }
        return;
    }

    container.innerHTML = `
        <div class="chart-skeleton">
            <span class="skeleton-line wide"></span>
            <span class="skeleton-line"></span>
            <span class="skeleton-line short"></span>
        </div>
    `;

    try {
        const response = await API.getVenueYearTopic(venue, year, topic, includeChildren, { limit: 20, offset: 0 });
        state.latestExplorerResponse = response;
        renderExplorerResponse(response);
        renderTopicFrequencyFromExplorer(response);
    } catch (error) {
        console.error("Failed to load venue-year-topic response", error);
        renderExplorerEmpty("Venue-year-topic data is not available for this query.");
        Charts.showError("chart-topic-frequency", "Failed to load relative_frequency data.");
    }
}

async function debounceTopicPreview() {
    window.clearTimeout(state.resolveTimer);
    state.resolveTimer = window.setTimeout(() => previewTopicNormalization(), 320);
}

async function previewTopicNormalization() {
    const topic = document.getElementById("explorer-topic")?.value.trim();
    const includeChildren = document.getElementById("explorer-include-children")?.checked || false;
    const preview = document.getElementById("topic-preview");
    if (!preview) {
        return;
    }
    if (!topic) {
        preview.textContent = t("index.explorer.previewEmpty", "Enter a topic query to preview canonical normalization.");
        return;
    }
    preview.innerHTML = '<span class="badge badge-unknown">Resolving</span> Normalizing topic query...';
    try {
        const response = await API.resolveTopic(topic, includeChildren);
        const query = response.data?.normalized_query || {};
        const warningBadges = renderBadgeList(response.warnings || []);
        preview.innerHTML = `
            <span class="badge badge-accepted">Canonical</span>
            <strong>${escapeHtml(query.canonical_topic || "unresolved")}</strong>
            <span class="meta-inline">topic_id: ${escapeHtml(query.topic_id || "n/a")}</span>
            <span class="meta-inline">aliases used: ${escapeHtml((query.aliases_used || []).join(", ") || "none")}</span>
            <span class="badge ${includeChildren ? "badge-warning" : "badge-unknown"}">include_children=${includeChildren}</span>
            ${warningBadges}
        `;
    } catch (error) {
        console.error("Failed to resolve topic", error);
        preview.innerHTML = '<span class="badge badge-warning">Unavailable</span> Topic normalization is not available in this mode.';
    }
}

function renderExplorerResponse(response) {
    const data = response.data || {};
    if (data.unavailable) {
        renderExplorerEmpty(data.message || "Not available in static export yet.");
        return;
    }

    const query = data.normalized_query || {};
    const items = data.items || [];
    const warnings = response.warnings || [];
    const sourceBreakdown = data.source_breakdown || {};
    const qualityScope = data.quality_scope || {};
    const sourceLayer = response.meta?.source_layer || "unknown";
    const count = data.matched_papers || 0;
    const total = data.total_venue_papers || 0;
    const relative = data.relative_frequency || 0;

    document.getElementById("explorer-results").innerHTML = `
        <div class="result-block">
            <div class="section-header compact">
                <div>
                    <p class="section-kicker">Normalized Query</p>
                    <h3>${escapeHtml(query.canonical_topic || query.input_topic || "Topic")}</h3>
                    <p>
                        ${escapeHtml(query.venue || "")} ${escapeHtml(query.year || "")}
                        <span class="badge badge-mixed">${escapeHtml(sourceLayer)}</span>
                        <span class="badge ${query.include_children ? "badge-warning" : "badge-unknown"}">include_children=${Boolean(query.include_children)}</span>
                    </p>
                </div>
                <div class="badge-stack">
                    ${renderSampleBadges(count, total, warnings)}
                </div>
            </div>

            <div class="metric-strip">
                ${metricTile("relative_frequency", formatPercent(relative), "primary metric")}
                ${metricTile("count", formatNumber(count), "matched_papers")}
                ${metricTile("total venue papers", formatNumber(total), "denominator")}
                ${metricTile("warnings", formatNumber(warnings.length), "visible")}
            </div>

            <div class="query-grid">
                <div>
                    <h4>Aliases Used</h4>
                    <p>${escapeHtml((query.aliases_used || []).join(", ") || "none")}</p>
                </div>
                <div>
                    <h4>${escapeHtml(t("index.quality.sourceBreakdown", "Source Breakdown"))}</h4>
                    ${renderKeyValueList(sourceBreakdown)}
                </div>
                <div>
                    <h4>Quality Scope</h4>
                    ${renderKeyValueList(qualityScope)}
                </div>
            </div>

            ${renderWarningsBlock(warnings)}
            ${renderEvidenceTable(items)}
        </div>
    `;
}

function renderTopicFrequencyFromExplorer(response) {
    const data = response.data || {};
    if (data.unavailable) {
        Charts.showEmpty("chart-topic-frequency", "Not available in static export yet.");
        return;
    }
    const query = data.normalized_query || {};
    Charts.renderRelativeFrequencyBars("chart-topic-frequency", [{
        name: query.canonical_topic || query.input_topic || "topic",
        relative_frequency: data.relative_frequency || 0,
        count: data.matched_papers || 0,
        total: data.total_venue_papers || 0,
        source_scope: response.meta?.source_layer || "unknown",
        warnings: (response.warnings || []).length,
    }]);
}

function renderExplorerEmpty(message) {
    document.getElementById("explorer-results").innerHTML = `
        <div class="empty-state">
            <div class="empty-state-title">No evidence table</div>
            <div class="empty-state-message">${escapeHtml(message)}</div>
        </div>
    `;
}

function renderEvidenceTable(items) {
    if (!items.length) {
        return `
            <div class="empty-state">
                <div class="empty-state-title">No matched papers</div>
                <div class="empty-state-message">The response shape is stable, but this query has no paper evidence.</div>
            </div>
        `;
    }

    const rows = items.map((item) => {
        const match = item.topic_match || {};
        const sources = item.source_evidence || [];
        return `
            <tr>
                <td>${escapeHtml(item.title || "Untitled")}</td>
                <td>${escapeHtml(item.year || "")}</td>
                <td>${escapeHtml(item.venue || "")}</td>
                <td>${statusBadge(item.status)}</td>
                <td>${sourceBadges(sources)}</td>
                <td>${escapeHtml(match.match_method || "unknown")}</td>
                <td>${confidenceBadge(match.confidence)}</td>
            </tr>
        `;
    }).join("");

    return `
        <div class="evidence-table-wrap">
            <table class="evidence-table">
                <thead>
                    <tr>
                        <th>Paper title</th>
                        <th>Year</th>
                        <th>Venue</th>
                        <th>Status</th>
                        <th>Sources</th>
                        <th>Match method</th>
                        <th>Confidence</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;
}

function renderQualityWarnings(warnings) {
    renderContractWarnings("quality-warning-list", warnings, "No scoped warnings for the current quality report.");
}

function renderContractWarnings(containerId, warnings, emptyMessage) {
    const container = document.getElementById(containerId);
    if (!container) {
        return;
    }
    if (!warnings.length) {
        container.innerHTML = `<div class="warning-item muted">${escapeHtml(emptyMessage)}</div>`;
        return;
    }
    container.innerHTML = warnings.map((warning) => `
        <div class="warning-item ${escapeHtml(warning.severity || "low")}">
            <span class="badge badge-warning">${escapeHtml(warning.severity || "warning")}</span>
            <strong>${escapeHtml(warning.code || "warning")}</strong>
            <span>${escapeHtml(warning.message || "")}</span>
        </div>
    `).join("");
}

function renderQualityMetrics(metrics) {
    const container = document.getElementById("quality-grid");
    if (!container) {
        return;
    }
    const rows = [
        ["structured_paper_count", formatNumber(metrics.structured_paper_count)],
        ["unknown_quality_ratio", formatNullablePercent(metrics.unknown_quality_ratio)],
        ["empty_abstract_ratio", formatNullablePercent(metrics.empty_abstract_ratio)],
        ["single_source_ratio", formatNullablePercent(metrics.single_source_ratio)],
        ["last_ingestion_time", metrics.last_ingestion_time || "n/a"],
        ["last_analysis_time", metrics.last_analysis_time || "n/a"],
    ];
    container.innerHTML = rows.map(([label, value]) => `
        <div class="quality-card">
            <div class="metric-label">${escapeHtml(label)}</div>
            <div class="metric-value">${escapeHtml(value)}</div>
        </div>
    `).join("");
}

function renderSourceBreakdown(sourceBreakdown) {
    const container = document.getElementById("quality-source-breakdown");
    if (!container) {
        return;
    }
    container.innerHTML = `
        <h3>${escapeHtml(t("index.quality.sourceBreakdown", "Source Breakdown"))}</h3>
        ${renderKeyValueList(sourceBreakdown)}
    `;
}

function renderDomains(domains, topics, warnings) {
    const container = document.getElementById("domain-grid");
    if (!container) {
        return;
    }
    if (!domains.length) {
        container.innerHTML = emptyBlock("Domain metadata", warnings[0]?.message || "Not available in static export yet.");
        return;
    }
    const topicsByDomain = topics.reduce((acc, topic) => {
        const key = (topic.domain || "unknown").toUpperCase();
        acc[key] = acc[key] || [];
        acc[key].push(topic);
        return acc;
    }, {});
    container.innerHTML = domains.map((domain) => {
        const domainId = domain.domain || domain.id || domain.name;
        const domainTopics = topicsByDomain[String(domainId).toUpperCase()] || [];
        return `
            <article class="domain-card">
                <div class="domain-card-header">
                    <h3>${escapeHtml(domain.name || domainId)}</h3>
                    <span class="badge badge-mixed">${escapeHtml(domainId)}</span>
                </div>
                <p>arXiv categories: ${escapeHtml((domain.arxiv_categories || []).join(", ") || "n/a")}</p>
                <p>Canonical topics: ${formatNumber(domainTopics.length)}</p>
                <div class="topic-chip-row">
                    ${domainTopics.slice(0, 5).map((topic) => `<button class="topic-chip" type="button" onclick="selectTopic('${escapeAttr(topic.topic_id)}')">${escapeHtml(topic.canonical_name || topic.topic_id)}</button>`).join("")}
                </div>
            </article>
        `;
    }).join("");
}

function renderTopics(topics, warnings) {
    const container = document.getElementById("topic-cards");
    if (!container) {
        return;
    }
    if (!topics.length) {
        container.innerHTML = emptyBlock("Topic metadata", warnings[0]?.message || "Not available in static export yet.");
        return;
    }
    const preferred = rankTopics(topics).slice(0, 6);
    container.innerHTML = preferred.map((topic) => `
        <article class="topic-card">
            <div class="topic-card-top">
                <span class="badge badge-accepted">${escapeHtml(topic.domain || "domain")}</span>
                <button class="topic-chip action" type="button" onclick="selectTopic('${escapeAttr(topic.topic_id)}')">${escapeHtml(t("index.topics.use", "Use in explorer"))}</button>
            </div>
            <h3>${escapeHtml(topic.canonical_name || topic.topic_id)}</h3>
            <p>${escapeHtml(compactText(topic.definition || "Canonical topic metadata from the DeepTrender taxonomy.", 160))}</p>
            <div class="topic-meta-grid">
                <span><strong>relative_frequency</strong><br>${escapeHtml(t("index.topics.queryScoped", "query-scoped"))}</span>
                <span><strong>count</strong><br>${escapeHtml(t("index.topics.shownExplorer", "shown in explorer"))}</span>
            </div>
            <div class="topic-chip-row">
                ${(topic.aliases || []).slice(0, 3).map((alias) => `<span class="keyword-tag">${escapeHtml(alias)}</span>`).join("")}
            </div>
        </article>
    `).join("");
}

function rankTopics(topics) {
    const preferred = ["large_language_model", "transformer", "diffusion_model", "retrieval_augmented_generation", "semantic_segmentation"];
    return [...topics].sort((a, b) => {
        const aIndex = preferred.indexOf(a.topic_id);
        const bIndex = preferred.indexOf(b.topic_id);
        if (aIndex >= 0 || bIndex >= 0) {
            return (aIndex >= 0 ? aIndex : 999) - (bIndex >= 0 ? bIndex : 999);
        }
        return String(a.topic_id).localeCompare(String(b.topic_id));
    });
}

async function loadVenueCards() {
    const container = document.getElementById("venues-grid");
    if (!container) {
        return;
    }
    try {
        const venues = await API.getVenues();
        if (!venues.length) {
            container.innerHTML = emptyBlock("Venue metadata", "No venue data available.");
            return;
        }
        container.innerHTML = venues.map((venue) => `
            <div class="venue-card" onclick="goToVenue('${escapeAttr(venue.name)}')" role="button" tabindex="0">
                <div class="venue-card-header">
                    <span class="venue-name">${escapeHtml(venue.name)}</span>
                    <span class="venue-count">${formatNumber(venue.paper_count)} papers</span>
                </div>
                <div class="venue-keywords">
                    ${(venue.top_keywords || []).slice(0, 5).map((item) => `<span class="keyword-tag">${escapeHtml(item.keyword)}</span>`).join("") || '<span class="keyword-tag muted">Use explorer for topic facts</span>'}
                </div>
            </div>
        `).join("");
    } catch (error) {
        console.error("Failed to load venue cards", error);
        container.innerHTML = emptyBlock("Venue metadata", "Unable to load venue cards.");
    }
}

async function refreshData() {
    await Promise.allSettled([loadTopKeywords(), loadTrends()]);
    if (state.wordcloudLoaded) {
        await loadWordcloud({ forceRefresh: true });
    }
}

async function loadTopKeywords() {
    const containerId = "chart-top-keywords";
    Charts.showLoading(containerId);
    try {
        const data = await API.getTopKeywords({
            venue: state.venue || null,
            year: state.year || null,
            limit: 20,
        });
        Charts.renderBarChart(containerId, data || []);
    } catch (error) {
        console.error("Failed to load top keywords", error);
        Charts.showError(containerId, "Failed to load top keywords.");
    }
}

async function loadTrends() {
    const containerId = "chart-trends";
    Charts.showLoading(containerId);
    try {
        const trends = await API.getKeywordTrends([], state.venue || null);
        Charts.renderCountTrendChart(containerId, trends || []);
    } catch (error) {
        console.error("Failed to load keyword trends", error);
        Charts.showError(containerId, "Failed to load keyword trend data.");
    }
}

async function loadWordcloud(options = {}) {
    if (state.wordcloudLoading) {
        return;
    }
    state.wordcloudLoading = true;
    const containerId = "chart-wordcloud";
    Charts.showLoading(containerId);
    try {
        await ensureWordcloudPlugin();
        const data = await API.getWordcloudData(state.venue || null, state.year || null, 50, options);
        Charts.renderWordcloud(containerId, data || []);
        state.wordcloudLoaded = true;
    } catch (error) {
        console.error("Failed to load word cloud", error);
        Charts.showError(containerId, "Failed to load the deferred keyword cloud.");
    } finally {
        state.wordcloudLoading = false;
    }
}

function ensureWordcloudPlugin() {
    if (state.wordcloudPluginLoaded) {
        return Promise.resolve();
    }
    const existing = document.getElementById("echarts-wordcloud-script");
    if (existing) {
        return new Promise((resolve, reject) => {
            existing.addEventListener("load", resolve, { once: true });
            existing.addEventListener("error", reject, { once: true });
        });
    }
    return new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.id = "echarts-wordcloud-script";
        script.src = "https://cdn.jsdelivr.net/npm/echarts-wordcloud@2.1.0/dist/echarts-wordcloud.min.js";
        script.async = true;
        script.onload = () => {
            state.wordcloudPluginLoaded = true;
            resolve();
        };
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

function selectTopic(topicId) {
    setControlValue("explorer-topic", topicId);
    previewTopicNormalization();
    document.getElementById("explorer")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function goToVenue(venueName) {
    window.location.href = `./venue.html?venue=${encodeURIComponent(venueName)}`;
}

function scopeToQualityQuery(scope) {
    if (scope === "preprint") {
        return { source: "arxiv" };
    }
    return {};
}

function populateSelect(id, values, placeholder, descending = false) {
    const select = document.getElementById(id);
    if (!select) {
        return;
    }
    const sorted = [...new Set(values || [])].sort((a, b) => descending ? Number(b) - Number(a) : String(a).localeCompare(String(b)));
    select.innerHTML = `<option value="">${escapeHtml(placeholder)}</option>${sorted.map((value) => `<option value="${escapeAttr(value)}">${escapeHtml(value)}</option>`).join("")}`;
}

function setControlValue(id, value) {
    const control = document.getElementById(id);
    if (control) {
        control.value = value;
    }
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) {
        el.textContent = value;
    }
}

function removeSkeletons(root) {
    root?.querySelectorAll(".skeleton-text").forEach((el) => el.classList.remove("skeleton-text"));
}

function metricTile(label, value, hint) {
    return `
        <div class="metric-tile">
            <span class="metric-label">${escapeHtml(label)}</span>
            <strong>${escapeHtml(value)}</strong>
            <span>${escapeHtml(hint)}</span>
        </div>
    `;
}

function renderSampleBadges(count, total, warnings) {
    const badges = [];
    if (count < 5) {
        badges.push('<span class="badge badge-small-sample">small sample</span>');
    }
    if ((warnings || []).length) {
        badges.push('<span class="badge badge-warning">warning</span>');
    }
    if (total === 0) {
        badges.push('<span class="badge badge-unknown">unknown denominator</span>');
    }
    return badges.join("");
}

function renderBadgeList(warnings) {
    return warnings.map((warning) => `<span class="badge badge-warning">${escapeHtml(warning.code || "warning")}</span>`).join("");
}

function statusBadge(status) {
    const normalized = String(status || "unknown").toLowerCase();
    const cls = ["accepted", "submitted", "filtered", "published"].includes(normalized)
        ? "badge-accepted"
        : normalized === "preprint"
            ? "badge-preprint"
            : normalized === "mixed"
                ? "badge-mixed"
                : "badge-unknown";
    return `<span class="badge ${cls}">${escapeHtml(normalized)}</span>`;
}

function sourceBadges(sources) {
    if (!sources || sources.length === 0) {
        return '<span class="badge badge-unknown">unknown</span>';
    }
    return sources.map((source) => {
        const normalized = String(source || "unknown").toLowerCase();
        const cls = normalized === "arxiv" ? "badge-arxiv-only" : normalized === "unknown" ? "badge-unknown" : "badge-mixed";
        return `<span class="badge ${cls}">${escapeHtml(normalized)}</span>`;
    }).join(" ");
}

function confidenceBadge(confidence) {
    if (typeof confidence !== "number") {
        return '<span class="badge badge-unknown">n/a</span>';
    }
    const cls = confidence < 0.7 ? "badge-low-confidence" : "badge-accepted";
    return `<span class="badge ${cls}">${confidence.toFixed(2)}</span>`;
}

function renderWarningsBlock(warnings) {
    if (!warnings.length) {
        return '<div class="warning-list compact"><div class="warning-item muted">No warnings for this response.</div></div>';
    }
    return `
        <div class="warning-list compact">
            ${warnings.map((warning) => `
                <div class="warning-item ${escapeHtml(warning.severity || "low")}">
                    <span class="badge badge-warning">${escapeHtml(warning.severity || "warning")}</span>
                    <strong>${escapeHtml(warning.code || "warning")}</strong>
                    <span>${escapeHtml(warning.message || "")}</span>
                </div>
            `).join("")}
        </div>
    `;
}

function renderKeyValueList(values) {
    const entries = Object.entries(values || {});
    if (!entries.length) {
        return '<p class="muted-text">n/a</p>';
    }
    return `
        <dl class="kv-list">
            ${entries.map(([key, value]) => `
                <div>
                    <dt>${escapeHtml(key)}</dt>
                    <dd>${escapeHtml(formatValue(value))}</dd>
                </div>
            `).join("")}
        </dl>
    `;
}

function emptyBlock(title, message) {
    return `
        <div class="empty-state">
            <div class="empty-state-title">${escapeHtml(title)}</div>
            <div class="empty-state-message">${escapeHtml(message)}</div>
        </div>
    `;
}

function showInlineError(containerId, message) {
    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = `<div class="error-state"><div class="error-state-message">${escapeHtml(message)}</div></div>`;
    }
}

function compactText(text, limit) {
    const clean = String(text || "").replace(/\s+/g, " ").trim();
    return clean.length > limit ? `${clean.slice(0, limit - 1)}...` : clean;
}

function formatNumber(value) {
    if (value === null || value === undefined || value === "N/A") {
        return "N/A";
    }
    const number = Number(value);
    return Number.isFinite(number) ? number.toLocaleString() : String(value);
}

function formatPercent(value) {
    const number = Number(value || 0);
    return `${(number * 100).toFixed(number > 0 && number < 0.01 ? 2 : 1)}%`;
}

function formatNullablePercent(value) {
    return value === null || value === undefined ? "n/a" : formatPercent(value);
}

function formatValue(value) {
    if (typeof value === "number") {
        return Number.isInteger(value) ? formatNumber(value) : value.toFixed(3);
    }
    return value ?? "n/a";
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function escapeAttr(value) {
    return escapeHtml(value).replace(/`/g, "&#096;");
}

function t(key, fallback) {
    return window.SiteI18n?.t(key, fallback) || fallback || key;
}

window.refreshData = refreshData;
window.runTopicExplorer = runTopicExplorer;
window.selectTopic = selectTopic;
window.goToVenue = goToVenue;

document.addEventListener("DOMContentLoaded", init);
