const CHART_THEME = {
    backgroundColor: "transparent",
    textStyle: { color: "#e6edf3" },
    title: { textStyle: { color: "#e6edf3" } },
    legend: { textStyle: { color: "#8b949e" } },
    tooltip: {
        backgroundColor: "rgba(22, 27, 34, 0.95)",
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

echarts.registerTheme("dark", CHART_THEME);

const Charts = {
    instances: {},

    init(containerId) {
        const container = document.getElementById(containerId);
        if (!container) {
            return null;
        }

        if (this.instances[containerId]) {
            this.instances[containerId].dispose();
        }

        const chart = echarts.init(container, "dark");
        this.instances[containerId] = chart;
        window.addEventListener("resize", () => chart.resize());
        return chart;
    },

    get(containerId) {
        return this.instances[containerId];
    },

    showLoading(containerId) {
        const chart = this.get(containerId);
        const container = document.getElementById(containerId);
        if (chart) {
            chart.showLoading({
                text: "Loading...",
                color: "#58a6ff",
                textColor: "#8b949e",
                maskColor: "rgba(13, 17, 23, 0.8)",
            });
        } else if (container) {
            container.innerHTML = '<div class="loading">Loading...</div>';
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

        const chart = this.get(containerId);
        if (chart) {
            chart.clear();
        }

        container.innerHTML = `
            <div class="error-state">
                <div class="error-state-title">Load error</div>
                <div class="error-state-message">${message}</div>
            </div>
        `;
    },

    showEmpty(containerId, message = "No data available.") {
        const container = document.getElementById(containerId);
        if (!container) {
            return;
        }

        const chart = this.get(containerId);
        if (chart) {
            chart.clear();
        }

        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-title">No data</div>
                <div class="empty-state-message">${message}</div>
            </div>
        `;
    },

    renderWordcloud(containerId, data) {
        const chart = this.init(containerId);
        if (!chart || !data || data.length === 0) {
            return null;
        }

        chart.setOption({
            tooltip: {
                show: true,
                formatter: (params) => `<strong>${params.name}</strong><br/>Count: ${params.value}`,
            },
            series: [{
                type: "wordCloud",
                shape: "circle",
                left: "center",
                top: "center",
                width: "90%",
                height: "90%",
                sizeRange: [14, 60],
                rotationRange: [-45, 45],
                rotationStep: 15,
                gridSize: 8,
                drawOutOfBound: false,
                textStyle: {
                    fontFamily: "sans-serif",
                    fontWeight: "bold",
                    color() {
                        const colors = ["#58a6ff", "#79c0ff", "#3fb950", "#56d364", "#d29922", "#e3b341", "#a371f7", "#bc8cff"];
                        return colors[Math.floor(Math.random() * colors.length)];
                    },
                },
                emphasis: {
                    textStyle: {
                        shadowBlur: 10,
                        shadowColor: "rgba(88, 166, 255, 0.5)",
                    },
                },
                data: data.map((item) => ({ name: item.name, value: item.value })),
            }],
        });
        return chart;
    },

    renderBarChart(containerId, data) {
        const chart = this.init(containerId);
        if (!chart || !data || data.length === 0) {
            return null;
        }

        const reversed = [...data].reverse();
        chart.setOption({
            tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
            grid: { left: "3%", right: "10%", bottom: "3%", top: "3%", containLabel: true },
            xAxis: {
                type: "value",
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
                type: "bar",
                data: reversed.map((item) => item.count),
                itemStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                        { offset: 0, color: "#667eea" },
                        { offset: 1, color: "#764ba2" },
                    ]),
                    borderRadius: [0, 4, 4, 0],
                },
                label: { show: true, position: "right", color: "#8b949e", fontSize: 11 },
            }],
        });
        return chart;
    },

    renderTrendChart(containerId, trends) {
        const chart = this.init(containerId);
        if (!chart || !trends || trends.length === 0) {
            return null;
        }

        const allYears = new Set();
        trends.forEach((trend) => trend.years.forEach((year) => allYears.add(year)));
        const years = Array.from(allYears).sort();

        chart.setOption({
            tooltip: { trigger: "axis" },
            legend: {
                data: trends.map((trend) => trend.keyword),
                top: 0,
                textStyle: { color: "#8b949e" },
            },
            grid: { left: "3%", right: "4%", bottom: "3%", top: "50px", containLabel: true },
            xAxis: {
                type: "category",
                data: years,
                axisLine: { lineStyle: { color: "#30363d" } },
                axisLabel: { color: "#8b949e" },
            },
            yAxis: {
                type: "value",
                axisLine: { lineStyle: { color: "#30363d" } },
                axisLabel: { color: "#8b949e" },
                splitLine: { lineStyle: { color: "#21262d" } },
            },
            series: trends.map((trend) => ({
                name: trend.keyword,
                type: "line",
                smooth: true,
                symbol: "circle",
                symbolSize: 8,
                data: years.map((year) => {
                    const index = trend.years.indexOf(year);
                    return index >= 0 ? trend.counts[index] : null;
                }),
                lineStyle: { width: 3 },
                emphasis: { focus: "series" },
            })),
        });
        return chart;
    },

    renderComparisonRadar(containerId, comparison) {
        const chart = this.init(containerId);
        if (!chart || !comparison) {
            return null;
        }

        const venues = Object.keys(comparison.venues);
        const allKeywords = new Set();
        venues.forEach((venue) => {
            comparison.venues[venue].slice(0, 8).forEach((item) => allKeywords.add(item.keyword));
        });
        const keywords = Array.from(allKeywords).slice(0, 8);

        chart.setOption({
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
                    areaStyle: { opacity: 0.2 },
                })),
            }],
        });
        return chart;
    },
};

window.Charts = Charts;
