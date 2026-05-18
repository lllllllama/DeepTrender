const CHART_THEME = {
    backgroundColor: "transparent",
    textStyle: { color: "#e6edf3" },
    title: { textStyle: { color: "#e6edf3" } },
    legend: { textStyle: { color: "#8b949e" } },
    tooltip: {
        backgroundColor: "rgba(22, 27, 34, 0.96)",
        borderColor: "#30363d",
        textStyle: { color: "#e6edf3" },
    },
    color: [
        "#58a6ff",
        "#3fb950",
        "#d29922",
        "#f85149",
        "#a371f7",
        "#79c0ff",
        "#56d364",
        "#e3b341",
        "#ff7b72",
        "#bc8cff",
    ],
};

if (window.echarts) {
    echarts.registerTheme("dark", CHART_THEME);
}

const Charts = {
    instances: {},
    resizeListenerBound: false,
    resizeTimer: null,

    ensureResizeListener() {
        if (this.resizeListenerBound) {
            return;
        }
        window.addEventListener("resize", () => {
            window.clearTimeout(this.resizeTimer);
            this.resizeTimer = window.setTimeout(() => this.resizeAll(), 120);
        });
        this.resizeListenerBound = true;
    },

    init(containerId) {
        const container = document.getElementById(containerId);
        if (!container || !window.echarts) {
            return null;
        }

        const existing = this.instances[containerId];
        if (existing && !existing.isDisposed?.()) {
            this.ensureResizeListener();
            return existing;
        }

        container.innerHTML = "";
        const chart = echarts.init(container, "dark");
        this.instances[containerId] = chart;
        this.ensureResizeListener();
        return chart;
    },

    get(containerId) {
        const chart = this.instances[containerId];
        if (!chart || chart.isDisposed?.()) {
            return null;
        }
        return chart;
    },

    render(containerId, option, emptyMessage = "No data available.") {
        if (!option) {
            this.showEmpty(containerId, emptyMessage);
            return null;
        }
        const chart = this.init(containerId);
        if (!chart) {
            this.showEmpty(containerId, emptyMessage);
            return null;
        }
        chart.hideLoading();
        chart.setOption(option, true);
        return chart;
    },

    destroy(containerId) {
        const chart = this.get(containerId);
        if (chart) {
            chart.dispose();
        }
        delete this.instances[containerId];
    },

    resizeAll() {
        Object.values(this.instances).forEach((chart) => {
            if (chart && !chart.isDisposed?.()) {
                chart.resize();
            }
        });
    },

    showLoading(containerId, message = "Loading...") {
        const chart = this.get(containerId);
        const container = document.getElementById(containerId);
        if (chart) {
            chart.showLoading({
                text: message,
                color: "#58a6ff",
                textColor: "#8b949e",
                maskColor: "rgba(13, 17, 23, 0.72)",
            });
        } else if (container) {
            container.innerHTML = `
                <div class="chart-skeleton" aria-live="polite">
                    <span class="skeleton-line wide"></span>
                    <span class="skeleton-line"></span>
                    <span class="skeleton-line short"></span>
                </div>
            `;
        }
    },

    hideLoading(containerId) {
        const chart = this.get(containerId);
        if (chart) {
            chart.hideLoading();
        }
    },

    showError(containerId, message = "Failed to load data.") {
        const container = document.getElementById(containerId);
        if (!container) {
            return;
        }
        this.destroy(containerId);
        container.innerHTML = `
            <div class="error-state" role="status">
                <div class="error-state-title">Load error</div>
                <div class="error-state-message">${escapeHtml(message)}</div>
            </div>
        `;
    },

    showEmpty(containerId, message = "No data available.") {
        const container = document.getElementById(containerId);
        if (!container) {
            return;
        }
        this.destroy(containerId);
        container.innerHTML = `
            <div class="empty-state" role="status">
                <div class="empty-state-title">No data</div>
                <div class="empty-state-message">${escapeHtml(message)}</div>
            </div>
        `;
    },

    renderWordcloud(containerId, data) {
        const limited = (data || []).slice(0, 50);
        if (!limited.length || !window.echarts) {
            this.showEmpty(containerId, "No keyword data available.");
            return null;
        }
        if (!echarts.graphic) {
            this.showError(containerId, "Chart runtime is unavailable.");
            return null;
        }

        return this.render(containerId, {
            tooltip: {
                show: true,
                formatter: (params) => `<strong>${escapeHtml(params.name)}</strong><br/>Count: ${params.value}`,
            },
            series: [{
                type: "wordCloud",
                shape: "circle",
                left: "center",
                top: "center",
                width: "90%",
                height: "90%",
                sizeRange: [12, 46],
                rotationRange: [-20, 20],
                rotationStep: 10,
                gridSize: 10,
                drawOutOfBound: false,
                textStyle: {
                    fontFamily: "Inter, sans-serif",
                    fontWeight: 700,
                    color() {
                        const colors = ["#58a6ff", "#79c0ff", "#3fb950", "#d29922", "#a371f7"];
                        return colors[Math.floor(Math.random() * colors.length)];
                    },
                },
                emphasis: {
                    focus: "self",
                    textStyle: { shadowBlur: 8, shadowColor: "rgba(88, 166, 255, 0.35)" },
                },
                data: limited.map((item) => ({ name: item.name, value: item.value })),
            }],
        });
    },

    renderBarChart(containerId, data) {
        if (!data || data.length === 0) {
            this.showEmpty(containerId, "No keyword count data available.");
            return null;
        }

        const reversed = [...data].slice(0, 20).reverse();
        return this.render(containerId, {
            tooltip: {
                trigger: "axis",
                axisPointer: { type: "shadow" },
                formatter(params) {
                    const item = params[0];
                    return `<strong>${escapeHtml(item.name)}</strong><br/>Keyword count: ${item.value}`;
                },
            },
            grid: { left: "3%", right: "12%", bottom: "3%", top: "3%", containLabel: true },
            xAxis: {
                type: "value",
                name: "count",
                axisLine: { lineStyle: { color: "#30363d" } },
                axisLabel: { color: "#8b949e" },
                splitLine: { lineStyle: { color: "#21262d" } },
            },
            yAxis: {
                type: "category",
                data: reversed.map((item) => item.keyword),
                axisLine: { lineStyle: { color: "#30363d" } },
                axisLabel: { color: "#e6edf3", fontSize: 12 },
            },
            series: [{
                name: "Keyword count",
                type: "bar",
                data: reversed.map((item) => item.count),
                itemStyle: {
                    color: "#58a6ff",
                    borderRadius: [0, 4, 4, 0],
                },
                label: { show: true, position: "right", color: "#8b949e", fontSize: 11 },
            }],
        });
    },

    renderTrendChart(containerId, trends) {
        if (!trends || trends.length === 0) {
            this.showEmpty(containerId, "No relative frequency trend data available.");
            return null;
        }

        const normalized = trends.slice(0, 5).map((trend) => ({
            name: trend.topic || trend.keyword || trend.name,
            years: trend.years || [],
            relativeFrequencies: trend.relative_frequencies || trend.relativeFrequency || trend.frequency || [],
            counts: trend.counts || trend.matched_papers || [],
            totals: trend.total_papers || trend.total_venue_papers || [],
            sourceScope: trend.source_scope || trend.sourceScope || "structured mixed",
            warningCounts: trend.warning_counts || trend.warningCounts || [],
        }));
        const allYears = new Set();
        normalized.forEach((trend) => trend.years.forEach((year) => allYears.add(year)));
        const years = Array.from(allYears).sort();

        return this.render(containerId, {
            tooltip: {
                trigger: "axis",
                formatter(params) {
                    const year = params?.[0]?.axisValue ?? "";
                    const rows = params.map((param) => {
                        const trend = normalized.find((item) => item.name === param.seriesName);
                        const yearIndex = trend?.years.indexOf(Number(year)) ?? -1;
                        const count = trend?.counts?.[yearIndex] ?? param.data?.count ?? "n/a";
                        const total = trend?.totals?.[yearIndex] ?? param.data?.total ?? "n/a";
                        const warnings = trend?.warningCounts?.[yearIndex] ?? param.data?.warnings ?? 0;
                        const rel = Number(param.value || 0);
                        return `${param.marker}<strong>${escapeHtml(param.seriesName)}</strong><br/>
                            relative_frequency: ${formatPercent(rel)}<br/>
                            matched_papers: ${count}<br/>
                            total_papers: ${total}<br/>
                            source scope: ${escapeHtml(trend?.sourceScope || "structured mixed")}<br/>
                            warnings: ${warnings}`;
                    });
                    return `<strong>${year}</strong><br/>${rows.join("<br/>")}`;
                },
            },
            legend: {
                data: normalized.map((trend) => trend.name),
                top: 0,
                textStyle: { color: "#8b949e" },
            },
            grid: { left: "3%", right: "4%", bottom: "3%", top: "54px", containLabel: true },
            xAxis: {
                type: "category",
                data: years,
                axisLine: { lineStyle: { color: "#30363d" } },
                axisLabel: { color: "#8b949e" },
            },
            yAxis: {
                type: "value",
                name: "relative_frequency",
                min: 0,
                axisLine: { lineStyle: { color: "#30363d" } },
                axisLabel: { color: "#8b949e", formatter: (value) => formatPercent(value) },
                splitLine: { lineStyle: { color: "#21262d" } },
            },
            series: normalized.map((trend) => ({
                name: trend.name,
                type: "line",
                smooth: true,
                symbol: "circle",
                symbolSize: 7,
                data: years.map((year) => {
                    const index = trend.years.indexOf(Number(year));
                    if (index < 0) {
                        return null;
                    }
                    const relative = trend.relativeFrequencies[index];
                    const count = trend.counts[index] || 0;
                    const total = trend.totals[index] || 0;
                    return typeof relative === "number" ? relative : (total ? count / total : 0);
                }),
                lineStyle: { width: 2 },
                emphasis: { focus: "series" },
            })),
        });
    },

    renderRelativeFrequencyBars(containerId, items) {
        if (!items || items.length === 0) {
            this.showEmpty(containerId, "No topic frequency data available.");
            return null;
        }
        const rows = items.slice(0, 8).reverse();
        return this.render(containerId, {
            tooltip: {
                trigger: "axis",
                axisPointer: { type: "shadow" },
                formatter(params) {
                    const item = rows[params[0].dataIndex];
                    return `<strong>${escapeHtml(item.name)}</strong><br/>
                        relative_frequency: ${formatPercent(item.relative_frequency || 0)}<br/>
                        matched_papers: ${item.count || 0}<br/>
                        total_papers: ${item.total || 0}<br/>
                        source scope: ${escapeHtml(item.source_scope || "structured mixed")}<br/>
                        warnings: ${item.warnings || 0}`;
                },
            },
            grid: { left: "3%", right: "10%", bottom: "4%", top: "4%", containLabel: true },
            xAxis: {
                type: "value",
                name: "relative_frequency",
                min: 0,
                axisLabel: { color: "#8b949e", formatter: (value) => formatPercent(value) },
                splitLine: { lineStyle: { color: "#21262d" } },
            },
            yAxis: {
                type: "category",
                data: rows.map((item) => item.name),
                axisLabel: { color: "#e6edf3" },
                axisLine: { lineStyle: { color: "#30363d" } },
            },
            series: [{
                name: "relative_frequency",
                type: "bar",
                data: rows.map((item) => item.relative_frequency || 0),
                itemStyle: { color: "#3fb950", borderRadius: [0, 4, 4, 0] },
                label: {
                    show: true,
                    position: "right",
                    color: "#8b949e",
                    formatter: (params) => formatPercent(params.value),
                },
            }],
        });
    },

    renderCountTrendChart(containerId, trends) {
        if (!trends || trends.length === 0) {
            this.showEmpty(containerId, "No keyword count trend data available.");
            return null;
        }

        const normalized = trends.slice(0, 5).map((trend) => ({
            name: trend.keyword || trend.topic || trend.name,
            years: (trend.years || []).map((year) => Number(year)),
            counts: trend.counts || [],
        }));
        const allYears = new Set();
        normalized.forEach((trend) => trend.years.forEach((year) => allYears.add(year)));
        const years = Array.from(allYears).sort((a, b) => a - b);

        return this.render(containerId, {
            tooltip: {
                trigger: "axis",
                formatter(params) {
                    const year = Number(params?.[0]?.axisValue);
                    const rows = params.map((param) => {
                        const trend = normalized.find((item) => item.name === param.seriesName);
                        const yearIndex = trend?.years.indexOf(year) ?? -1;
                        const count = trend?.counts?.[yearIndex] ?? param.value ?? 0;
                        return `${param.marker}<strong>${escapeHtml(param.seriesName)}</strong><br/>year: ${year}<br/>count: ${count}<br/>metric: keyword count`;
                    });
                    return rows.join("<br/>");
                },
            },
            legend: {
                data: normalized.map((trend) => trend.name),
                top: 0,
                textStyle: { color: "#8b949e" },
            },
            grid: { left: "3%", right: "4%", bottom: "3%", top: "54px", containLabel: true },
            xAxis: {
                type: "category",
                data: years,
                axisLine: { lineStyle: { color: "#30363d" } },
                axisLabel: { color: "#8b949e" },
            },
            yAxis: {
                type: "value",
                name: "keyword count",
                axisLine: { lineStyle: { color: "#30363d" } },
                axisLabel: { color: "#8b949e" },
                splitLine: { lineStyle: { color: "#21262d" } },
            },
            series: normalized.map((trend) => ({
                name: trend.name,
                type: "line",
                smooth: true,
                symbol: "circle",
                symbolSize: 7,
                data: years.map((year) => {
                    const index = trend.years.indexOf(Number(year));
                    return index >= 0 ? trend.counts[index] : null;
                }),
                lineStyle: { width: 2 },
                emphasis: { focus: "series" },
            })),
        });
    },

    renderComparisonRadar(containerId, comparison) {
        const venues = Object.keys(comparison?.venues || {});
        if (!venues.length) {
            this.showEmpty(containerId, "No comparison data available.");
            return null;
        }

        const allKeywords = new Set();
        venues.forEach((venue) => {
            comparison.venues[venue].slice(0, 8).forEach((item) => allKeywords.add(item.keyword));
        });
        const keywords = Array.from(allKeywords).slice(0, 8);

        return this.render(containerId, {
            tooltip: {},
            legend: { data: venues, top: 0, textStyle: { color: "#8b949e" } },
            radar: {
                indicator: keywords.map((keyword) => ({ name: keyword, max: 500 })),
                center: ["50%", "55%"],
                radius: "65%",
                axisName: { color: "#8b949e" },
                splitArea: { areaStyle: { color: ["rgba(88, 166, 255, 0.05)", "transparent"] } },
                splitLine: { lineStyle: { color: "#30363d" } },
                axisLine: { lineStyle: { color: "#30363d" } },
            },
            series: [{
                type: "radar",
                data: venues.map((venue) => ({
                    name: venue,
                    value: keywords.map((keyword) => comparison.venues[venue].find((item) => item.keyword === keyword)?.count || 0),
                    areaStyle: { opacity: 0.16 },
                })),
            }],
        });
    },
};

function formatPercent(value) {
    const number = Number(value || 0);
    return `${(number * 100).toFixed(number > 0 && number < 0.01 ? 2 : 1)}%`;
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

window.Charts = Charts;
