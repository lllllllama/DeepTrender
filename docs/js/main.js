const state = {
    venue: "",
    year: "",
    venues: [],
    years: [],
};

async function init() {
    try {
        await loadOverview();
        await loadFilters();
        await refreshData();
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
    await Promise.all([loadWordcloud(), loadTopKeywords(), loadTrends()]);
}

async function loadWordcloud() {
    const containerId = "chart-wordcloud";
    Charts.showLoading(containerId);

    try {
        const data = await API.getWordcloudData(state.venue || null, state.year || null, 100);
        if (!data || data.length === 0) {
            Charts.showEmpty(containerId, "No keyword data available.");
            return;
        }
        Charts.renderWordcloud(containerId, data);
    } catch (error) {
        console.error("Failed to load word cloud", error);
        Charts.showError(containerId, "Failed to load the word cloud.");
    } finally {
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
                <div class="venue-keywords" id="venue-kw-${venue.name}">
                    <span class="keyword-tag">Loading...</span>
                </div>
            </div>
        `).join("");

        for (const venue of venues) {
            loadVenueKeywords(venue.name);
        }
    } catch (error) {
        console.error("Failed to load venue cards", error);
    }
}

async function loadVenueKeywords(venueName) {
    try {
        const keywords = await API.getTopKeywords({ venue: venueName, limit: 5 });
        const container = document.getElementById(`venue-kw-${venueName}`);
        if (container && keywords.length > 0) {
            container.innerHTML = keywords.map((item) => `<span class="keyword-tag">${item.keyword}</span>`).join("");
        }
    } catch (error) {
        console.error(`Failed to load keywords for ${venueName}`, error);
    }
}

function goToVenue(venueName) {
    window.location.href = `./venue.html?venue=${encodeURIComponent(venueName)}`;
}

document.addEventListener("DOMContentLoaded", init);
