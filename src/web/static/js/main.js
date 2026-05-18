const state = {
    venue: "",
    year: "",
    venues: [],
    years: [],
    wordcloudLoaded: false,
    wordcloudLoading: false,
    wordcloudPluginLoaded: false,
    venueKeywordObserver: null,
};

async function init() {
    try {
        await loadOverview();
        await loadFilters();
        await Promise.allSettled([loadTopKeywords(), loadTrends()]);
        scheduleWordcloudLoad();
        await loadVenueCards();
    } catch (error) {
        console.error("Failed to initialize dashboard", error);
    }
}

async function loadOverview() {
    const overview = await API.getOverview();
    document.getElementById("stat-papers").textContent = overview.total_papers.toLocaleString();
    document.getElementById("stat-keywords").textContent = overview.total_keywords.toLocaleString();
    document.getElementById("stat-venues").textContent = overview.total_venues;
    document.getElementById("stat-years").textContent = overview.year_range;
    state.venues = overview.venues;
    state.years = overview.years;
}

async function loadFilters() {
    const venueSelect = document.getElementById("filter-venue");
    const yearSelect = document.getElementById("filter-year");

    state.venues.forEach((venue) => {
        const option = document.createElement("option");
        option.value = venue;
        option.textContent = venue;
        venueSelect.appendChild(option);
    });

    [...state.years].sort((a, b) => b - a).forEach((year) => {
        const option = document.createElement("option");
        option.value = year;
        option.textContent = year;
        yearSelect.appendChild(option);
    });

    venueSelect.addEventListener("change", () => {
        state.venue = venueSelect.value;
        refreshData();
    });

    yearSelect.addEventListener("change", () => {
        state.year = yearSelect.value;
        refreshData();
    });
}

async function refreshData() {
    await Promise.allSettled([loadTopKeywords(), loadTrends()]);
    if (state.wordcloudLoaded) {
        await loadWordcloud();
    } else {
        scheduleWordcloudLoad();
    }
}

function scheduleWordcloudLoad() {
    const target = document.getElementById("chart-wordcloud");
    if (!target || state.wordcloudLoaded || state.wordcloudLoading) {
        return;
    }

    if (!("IntersectionObserver" in window)) {
        window.setTimeout(() => loadWordcloud(), 600);
        return;
    }

    const observer = new IntersectionObserver((entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
            observer.disconnect();
            window.setTimeout(() => loadWordcloud(), 200);
        }
    }, { rootMargin: "120px" });
    observer.observe(target);
}

function ensureWordcloudPlugin() {
    if (state.wordcloudPluginLoaded) {
        return Promise.resolve();
    }

    const existing = document.getElementById("echarts-wordcloud-script");
    if (existing) {
        return new Promise((resolve, reject) => {
            existing.addEventListener("load", () => {
                state.wordcloudPluginLoaded = true;
                resolve();
            }, { once: true });
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

async function loadWordcloud() {
    if (state.wordcloudLoading) {
        return;
    }
    state.wordcloudLoading = true;
    const containerId = "chart-wordcloud";
    Charts.showLoading(containerId);

    try {
        await ensureWordcloudPlugin();
        const data = await API.getWordcloudData(state.venue || null, state.year || null, 50);
        if (!data || data.length === 0) {
            Charts.showEmpty(containerId, "No keyword data available.");
            return;
        }
        Charts.renderWordcloud(containerId, data);
        state.wordcloudLoaded = true;
    } catch (error) {
        console.error("Failed to load word cloud", error);
        Charts.showError(containerId, "Failed to load the word cloud.");
    } finally {
        state.wordcloudLoading = false;
        Charts.hideLoading(containerId);
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

        if (!data || data.length === 0) {
            Charts.showEmpty(containerId, "No keyword data available.");
            return;
        }

        Charts.renderBarChart(containerId, data);
    } catch (error) {
        console.error("Failed to load top keywords", error);
        Charts.showError(containerId, "Failed to load top keywords.");
    } finally {
        Charts.hideLoading(containerId);
    }
}

async function loadTrends() {
    const containerId = "chart-trends";
    Charts.showLoading(containerId);

    try {
        const trends = await API.getKeywordTrends([], state.venue || null);
        if (!trends || trends.length === 0) {
            Charts.showEmpty(containerId, "No trend data available.");
            return;
        }

        Charts.renderTrendChart(containerId, trends);
    } catch (error) {
        console.error("Failed to load trends", error);
        Charts.showError(containerId, "Failed to load trend data.");
    } finally {
        Charts.hideLoading(containerId);
    }
}

async function loadVenueCards() {
    const container = document.getElementById("venues-grid");
    if (!container) {
        return;
    }

    try {
        const venues = await API.getVenues();
        container.innerHTML = venues.map((venue) => `
            <div class="venue-card" onclick="goToVenue('${venue.name}')">
                <div class="venue-card-header">
                    <span class="venue-name">${venue.name}</span>
                    <span class="venue-count">${venue.paper_count} papers</span>
                </div>
                <div class="venue-keywords" id="${venueKeywordId(venue.name)}" data-venue="${venue.name}">
                    ${
                        venue.top_keywords && venue.top_keywords.length > 0
                            ? venue.top_keywords.slice(0, 5).map((item) => `<span class="keyword-tag">${item.keyword}</span>`).join("")
                            : '<span class="keyword-tag">Keywords on view</span>'
                    }
                </div>
            </div>
        `).join("");

        setupVenueKeywordObserver();
    } catch (error) {
        console.error("Failed to load venue cards", error);
    }
}

async function loadVenueKeywords(venueName) {
    try {
        const keywords = await API.getTopKeywords({ venue: venueName, limit: 5 });
        const container = document.getElementById(venueKeywordId(venueName));
        if (container && keywords.length > 0) {
            container.innerHTML = keywords.map((item) => `<span class="keyword-tag">${item.keyword}</span>`).join("");
        }
    } catch (error) {
        console.error(`Failed to load keywords for ${venueName}`, error);
    }
}

function setupVenueKeywordObserver() {
    const nodes = Array.from(document.querySelectorAll(".venue-keywords[data-venue]"))
        .filter((node) => node.textContent.includes("Keywords on view"));
    if (!nodes.length) {
        return;
    }

    if (!("IntersectionObserver" in window)) {
        nodes.slice(0, 6).forEach((node) => loadVenueKeywords(node.dataset.venue));
        return;
    }

    state.venueKeywordObserver?.disconnect();
    state.venueKeywordObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) {
                return;
            }
            const node = entry.target;
            state.venueKeywordObserver.unobserve(node);
            loadVenueKeywords(node.dataset.venue);
        });
    }, { rootMargin: "180px" });

    nodes.forEach((node) => state.venueKeywordObserver.observe(node));
}

function venueKeywordId(venueName) {
    return `venue-kw-${String(venueName).replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

function goToVenue(venueName) {
    window.location.href = `./venue.html?venue=${encodeURIComponent(venueName)}`;
}

document.addEventListener("DOMContentLoaded", init);
