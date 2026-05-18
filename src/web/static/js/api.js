const API = {
    isStatic: false,
    staticDetected: false,
    cache: new Map(),
    inFlight: new Map(),
    ttl: {
        overview: 60 * 1000,
        taxonomy: 5 * 60 * 1000,
        static: Number.POSITIVE_INFINITY,
        chart: 60 * 1000,
        default: 60 * 1000,
    },

    async detectMode() {
        if (this.staticDetected) {
            return this.isStatic;
        }

        try {
            const response = await fetch("./api/health", { method: "HEAD", cache: "no-cache" });
            this.isStatic = !response.ok;
        } catch (error) {
            this.isStatic = true;
        }

        this.staticDetected = true;
        return this.isStatic;
    },

    cacheKey(url) {
        return url.toString();
    },

    makeUrl(endpoint, params = {}) {
        const url = new URL(endpoint, window.location.href);
        Object.entries(params).forEach(([key, value]) => {
            if (value === null || value === undefined || value === "") {
                return;
            }
            if (Array.isArray(value)) {
                value.forEach((item) => url.searchParams.append(key, item));
                return;
            }
            url.searchParams.set(key, value);
        });
        return url;
    },

    getCached(key) {
        const cached = this.cache.get(key);
        if (!cached) {
            return null;
        }
        if (cached.expiresAt !== Number.POSITIVE_INFINITY && cached.expiresAt < Date.now()) {
            this.cache.delete(key);
            return null;
        }
        return cached.value;
    },

    setCached(key, value, ttlMs) {
        this.cache.set(key, {
            value,
            expiresAt: ttlMs === Number.POSITIVE_INFINITY ? Number.POSITIVE_INFINITY : Date.now() + ttlMs,
        });
    },

    async get(endpoint, params = {}, options = {}) {
        const url = this.makeUrl(endpoint, params);
        const key = this.cacheKey(url);
        const ttlMs = options.ttl ?? this.ttl.default;

        if (!options.forceRefresh) {
            const cached = this.getCached(key);
            if (cached !== null) {
                return cached;
            }
            if (this.inFlight.has(key)) {
                return this.inFlight.get(key);
            }
        }

        const request = fetch(url)
            .then(async (response) => {
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then((data) => {
                this.setCached(key, data, ttlMs);
                return data;
            })
            .finally(() => {
                this.inFlight.delete(key);
            });

        this.inFlight.set(key, request);
        return request;
    },

    async getStatic(path, options = {}) {
        const url = new URL(path, window.location.href);
        const key = this.cacheKey(url);
        if (!options.forceRefresh) {
            const cached = this.getCached(key);
            if (cached !== null) {
                return cached;
            }
            if (this.inFlight.has(key)) {
                return this.inFlight.get(key);
            }
        }

        const request = fetch(path)
            .then((response) => {
                if (!response.ok) {
                    throw new Error(`Failed to load ${path}`);
                }
                return response.json();
            })
            .then((data) => {
                this.setCached(key, data, this.ttl.static);
                return data;
            })
            .finally(() => this.inFlight.delete(key));

        this.inFlight.set(key, request);
        return request;
    },

    staticUnavailable(label) {
        return {
            data: {
                normalized_query: {},
                unavailable: true,
                message: `${label} is not available in static export yet.`,
            },
            meta: {
                taxonomy_version: "taxonomy_v0.1",
                data_policy_version: "data_policy_v0.1",
                generated_at: new Date().toISOString(),
                source_layer: "static_export",
                limit: 0,
                offset: 0,
                has_more: false,
            },
            warnings: [{
                code: "static_export_unavailable",
                message: `${label} is not available in static export yet.`,
                severity: "low",
            }],
            evidence: [],
        };
    },

    async getOverview(options = {}) {
        await this.detectMode();
        if (!this.isStatic) {
            return this.get("./api/stats/overview", {}, { ttl: this.ttl.overview, ...options });
        }

        const venues = await this.getStatic("./data/venues/venues_index.json");
        const totalPapers = venues.reduce((sum, venue) => sum + venue.paper_count, 0);
        const totalKeywords = new Set();
        venues.forEach((venue) => (venue.top_keywords || []).forEach((keyword) => totalKeywords.add(keyword.keyword)));
        const years = [...new Set(venues.flatMap((venue) => venue.years_available || []))].sort();

        return {
            total_papers: totalPapers,
            total_keywords: totalKeywords.size,
            total_venues: venues.length,
            venues: venues.map((venue) => venue.name),
            years,
            year_range: years.length > 0 ? `${Math.min(...years)}-${Math.max(...years)}` : "N/A",
        };
    },

    async getOverviewV01(options = {}) {
        await this.detectMode();
        if (this.isStatic) {
            const overview = await this.getOverview(options);
            return {
                data: { normalized_query: {}, ...overview },
                meta: {
                    taxonomy_version: "taxonomy_v0.1",
                    data_policy_version: "data_policy_v0.1",
                    generated_at: new Date().toISOString(),
                    source_layer: "static_json",
                    limit: 1,
                    offset: 0,
                    has_more: false,
                },
                warnings: [],
                evidence: [{ type: "static_json", path: "./data/venues/venues_index.json" }],
            };
        }
        return this.get("./api/v01/overview", {}, { ttl: this.ttl.overview, ...options });
    },

    async getVenues(options = {}) {
        await this.detectMode();
        if (!this.isStatic) {
            return this.get("./api/stats/venues", {}, { ttl: this.ttl.overview, ...options });
        }

        const venues = await this.getStatic("./data/venues/venues_index.json");
        return venues.map((venue) => ({
            name: venue.name,
            full_name: venue.full_name,
            domain: venue.domain,
            tier: venue.tier,
            top_keywords: venue.top_keywords || [],
            paper_count: venue.paper_count,
            years: venue.years_available || [],
        }));
    },

    async getVenueDetail(venue, options = {}) {
        await this.detectMode();
        if (!this.isStatic) {
            return this.get(`./api/stats/venue/${venue}`, {}, { ttl: this.ttl.overview, ...options });
        }

        const venuesIndex = await this.getStatic("./data/venues/venues_index.json");
        const venueInfo = venuesIndex.find((item) => item.name === venue);
        if (!venueInfo) {
            throw new Error(`Venue ${venue} not found`);
        }

        const topKeywords = await this.getStatic(`./data/venues/venue_${venue}_top_keywords.json`);
        const yearlyStats = Object.entries(topKeywords).map(([year, keywords]) => ({
            year: parseInt(year, 10),
            paper_count: keywords.reduce((sum, keyword) => sum + keyword.count, 0),
            top_keywords: keywords.slice(0, 10),
        })).sort((a, b) => b.year - a.year);

        return {
            venue,
            total_papers: venueInfo.paper_count,
            years: venueInfo.years_available || [],
            yearly_stats: yearlyStats,
        };
    },

    async getTopKeywords(params = {}, options = {}) {
        await this.detectMode();

        if (this.isStatic && !params.venue) {
            const venues = await this.getStatic("./data/venues/venues_index.json");
            const allKeywords = {};
            venues.forEach((venue) => {
                (venue.top_keywords || []).forEach((item) => {
                    allKeywords[item.keyword] = (allKeywords[item.keyword] || 0) + item.count;
                });
            });
            return Object.entries(allKeywords)
                .map(([keyword, count]) => ({ keyword, count }))
                .sort((a, b) => b.count - a.count)
                .slice(0, params.limit || 50);
        }

        if (this.isStatic && params.venue) {
            const topKeywords = await this.getStatic(`./data/venues/venue_${params.venue}_top_keywords.json`);
            if (params.year) {
                return topKeywords[params.year] || [];
            }

            const allKeywords = {};
            Object.values(topKeywords).forEach((yearData) => {
                yearData.forEach((item) => {
                    allKeywords[item.keyword] = (allKeywords[item.keyword] || 0) + item.count;
                });
            });

            return Object.entries(allKeywords)
                .map(([keyword, count]) => ({ keyword, count }))
                .sort((a, b) => b.count - a.count)
                .slice(0, params.limit || 50);
        }

        return this.get("./api/keywords/top", params, { ttl: this.ttl.chart, ...options });
    },

    async getKeywordTrends(keywords = [], venue = null, options = {}) {
        await this.detectMode();

        if (this.isStatic && !venue) {
            return [];
        }

        if (this.isStatic && venue) {
            const trends = await this.getStatic(`./data/venues/venue_${venue}_keyword_trends.json`);
            return keywords.flatMap((keyword) => {
                if (!trends[keyword]) {
                    return [];
                }

                return [{
                    keyword,
                    years: trends[keyword].map((point) => point.year),
                    counts: trends[keyword].map((point) => point.count),
                }];
            });
        }

        return this.get("./api/keywords/trends", { keyword: keywords, venue }, { ttl: this.ttl.chart, ...options });
    },

    async getComparison(year = null, limit = 10, options = {}) {
        await this.detectMode();

        if (this.isStatic) {
            const venuesIndex = await this.getStatic("./data/venues/venues_index.json");
            const result = { year, venues: {} };
            venuesIndex.slice(0, 8).forEach((venueInfo) => {
                const targetYear = year || Math.max(...(venueInfo.years_available || [0]));
                result.venues[venueInfo.name] = (venueInfo.top_keywords || []).slice(0, limit).map((item) => ({
                    ...item,
                    year: targetYear,
                }));
            });
            return result;
        }

        return this.get("./api/keywords/comparison", { year, limit }, { ttl: this.ttl.chart, ...options });
    },

    async getWordcloudData(venue = null, year = null, limit = 50, options = {}) {
        await this.detectMode();

        if (this.isStatic && !venue) {
            const venues = await this.getStatic("./data/venues/venues_index.json");
            const allKeywords = {};
            venues.forEach((venueInfo) => {
                (venueInfo.top_keywords || []).forEach((item) => {
                    allKeywords[item.keyword] = (allKeywords[item.keyword] || 0) + item.count;
                });
            });
            return Object.entries(allKeywords)
                .map(([name, value]) => ({ name, value }))
                .sort((a, b) => b.value - a.value)
                .slice(0, limit);
        }

        if (this.isStatic && venue) {
            const topKeywords = await this.getStatic(`./data/venues/venue_${venue}_top_keywords.json`);
            let data = [];

            if (year && topKeywords[year]) {
                data = topKeywords[year];
            } else {
                const allKeywords = {};
                Object.values(topKeywords).forEach((yearData) => {
                    yearData.forEach((item) => {
                        allKeywords[item.keyword] = (allKeywords[item.keyword] || 0) + item.count;
                    });
                });
                data = Object.entries(allKeywords).map(([keyword, count]) => ({ keyword, count }));
            }

            return data
                .sort((a, b) => b.count - a.count)
                .slice(0, limit)
                .map((item) => ({ name: item.keyword, value: item.count }));
        }

        return this.get("./api/keywords/wordcloud", { venue, year, limit }, { ttl: this.ttl.chart, ...options });
    },

    async getEmergingKeywords(options = {}) {
        await this.detectMode();
        if (this.isStatic) {
            return [];
        }
        return this.get("./api/keywords/emerging", {}, { ttl: this.ttl.chart, ...options });
    },

    async getDomains(options = {}) {
        await this.detectMode();
        if (this.isStatic) {
            return this.staticUnavailable("Domain taxonomy metadata");
        }
        return this.get("./api/v01/domains", {}, { ttl: this.ttl.taxonomy, ...options });
    },

    async getTopics(domain = null, options = {}) {
        await this.detectMode();
        if (this.isStatic) {
            return this.staticUnavailable("Topic taxonomy metadata");
        }
        return this.get("./api/v01/topics", { domain }, { ttl: this.ttl.taxonomy, ...options });
    },

    async resolveTopic(query, includeChildren = false, options = {}) {
        await this.detectMode();
        if (this.isStatic || !query) {
            return this.staticUnavailable("Topic resolution");
        }
        return this.get(
            "./api/v01/topics/resolve",
            { query, include_children: includeChildren },
            { ttl: this.ttl.taxonomy, ...options },
        );
    },

    async getVenueYearTopic(venue, year, topic, includeChildren = false, options = {}) {
        await this.detectMode();
        if (this.isStatic) {
            return this.staticUnavailable("Venue-year-topic explorer");
        }
        return this.get(
            "./api/v01/venue-year-topic",
            { venue, year, topic, include_children: includeChildren, limit: options.limit || 20, offset: options.offset || 0 },
            { ttl: this.ttl.chart, ...options },
        );
    },

    async getDataQualityReport(scope = {}, options = {}) {
        await this.detectMode();
        if (this.isStatic) {
            return this.staticUnavailable("Data quality report");
        }
        return this.get("./api/v01/data-quality", scope, { ttl: this.ttl.overview, ...options });
    },

    async getPaperProvenance(paperId, options = {}) {
        await this.detectMode();
        if (this.isStatic) {
            return this.staticUnavailable("Paper provenance");
        }
        return this.get(`./api/v01/papers/${paperId}/provenance`, {}, { ttl: this.ttl.taxonomy, ...options });
    },

    async getTopicSourceCoverage(topic, venue = null, year = null, options = {}) {
        await this.detectMode();
        if (this.isStatic) {
            return this.staticUnavailable("Topic source coverage");
        }
        return this.get("./api/v01/topic-source-coverage", { topic, venue, year }, { ttl: this.ttl.chart, ...options });
    },

    async getVenueYearSourceCoverage(venue, year, options = {}) {
        await this.detectMode();
        if (this.isStatic) {
            return this.staticUnavailable("Venue-year source coverage");
        }
        return this.get("./api/v01/venue-year-source-coverage", { venue, year }, { ttl: this.ttl.chart, ...options });
    },
};

window.API = API;
