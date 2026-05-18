const API = {
    isStatic: false,
    staticDetected: false,
    modePromise: null,
    cache: new Map(),
    inFlight: new Map(),
    ttl: {
        overview: 60 * 1000,
        chart: 60 * 1000,
        static: Number.POSITIVE_INFINITY,
        default: 60 * 1000,
    },

    async detectMode() {
        if (this.staticDetected) {
            return this.isStatic;
        }
        if (this.modePromise) {
            return this.modePromise;
        }

        this.modePromise = fetch("./api/health", { method: "HEAD", cache: "no-cache" })
            .then((response) => {
                this.isStatic = !response.ok;
                return this.isStatic;
            })
            .catch(() => {
                this.isStatic = true;
                return this.isStatic;
            })
            .finally(() => {
                this.staticDetected = true;
                this.modePromise = null;
            });

        return this.modePromise;
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
        const key = url.toString();
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
            .finally(() => this.inFlight.delete(key));

        this.inFlight.set(key, request);
        return request;
    },

    async getStatic(path) {
        const url = new URL(path, window.location.href);
        const key = url.toString();
        const cached = this.getCached(key);
        if (cached !== null) {
            return cached;
        }
        if (this.inFlight.has(key)) {
            return this.inFlight.get(key);
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

    aggregateVenueIndexKeywords(venues, limit = 50) {
        const allKeywords = {};
        venues.forEach((venue) => {
            (venue.top_keywords || []).forEach((item) => {
                allKeywords[item.keyword] = (allKeywords[item.keyword] || 0) + item.count;
            });
        });
        return Object.entries(allKeywords)
            .map(([keyword, count]) => ({ keyword, count }))
            .sort((a, b) => b.count - a.count)
            .slice(0, limit);
    },

    async getOverview() {
        await this.detectMode();
        if (!this.isStatic) {
            return this.get("./api/stats/overview", {}, { ttl: this.ttl.overview });
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

    async getVenues() {
        await this.detectMode();
        if (!this.isStatic) {
            return this.get("./api/stats/venues", {}, { ttl: this.ttl.overview });
        }

        const venues = await this.getStatic("./data/venues/venues_index.json");
        return venues.map((venue) => ({
            name: venue.name,
            paper_count: venue.paper_count,
            top_keywords: venue.top_keywords || [],
            years: venue.years_available || [],
        }));
    },

    async getVenueDetail(venue) {
        await this.detectMode();
        if (!this.isStatic) {
            return this.get(`./api/stats/venue/${venue}`, {}, { ttl: this.ttl.overview });
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
            years: venueInfo.years_available,
            yearly_stats: yearlyStats,
        };
    },

    async getTopKeywords(params = {}) {
        await this.detectMode();

        if (this.isStatic && !params.venue) {
            const venues = await this.getStatic("./data/venues/venues_index.json");
            return this.aggregateVenueIndexKeywords(venues, params.limit || 50);
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

        return this.get("./api/keywords/top", params, { ttl: this.ttl.chart });
    },

    async getKeywordTrends(keywords = [], venue = null) {
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

        return this.get("./api/keywords/trends", { keyword: keywords, venue }, { ttl: this.ttl.chart });
    },

    async getComparison(year = null, limit = 10) {
        await this.detectMode();

        if (this.isStatic) {
            const venuesIndex = await this.getStatic("./data/venues/venues_index.json");
            const result = { year, venues: {} };

            for (const venueInfo of venuesIndex) {
                try {
                    const topKeywords = await this.getStatic(`./data/venues/venue_${venueInfo.name}_top_keywords.json`);
                    const targetYear = year || Math.max(...Object.keys(topKeywords).map(Number));
                    if (topKeywords[targetYear]) {
                        result.venues[venueInfo.name] = topKeywords[targetYear].slice(0, limit);
                    }
                } catch (error) {
                    console.warn(`Failed to load static data for ${venueInfo.name}`, error);
                }
            }

            return result;
        }

        return this.get("./api/keywords/comparison", { year, limit }, { ttl: this.ttl.chart });
    },

    async getWordcloudData(venue = null, year = null, limit = 100) {
        await this.detectMode();

        if (this.isStatic && !venue) {
            const venues = await this.getStatic("./data/venues/venues_index.json");
            return this.aggregateVenueIndexKeywords(venues, limit)
                .map((item) => ({ name: item.keyword, value: item.count }));
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

        return this.get("./api/keywords/wordcloud", { venue, year, limit }, { ttl: this.ttl.chart });
    },

    async getEmergingKeywords() {
        await this.detectMode();
        if (this.isStatic) {
            return [];
        }
        return this.get("./api/keywords/emerging", {}, { ttl: this.ttl.chart });
    },
};

window.API = API;
