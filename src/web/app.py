"""
Flask application entrypoint.

Serves static assets and REST API endpoints for DeepTrender.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis import get_analyzer
from analysis.arxiv_agent import ArxivAnalysisAgent
from database import DatabaseRepository, get_repository
from scraper.venue_discovery import VenueDiscovery
from services import mcp_views


def create_app(
    repository: Optional[DatabaseRepository] = None,
    analyzer=None,
) -> Flask:
    """Create the Flask app with explicit dependencies."""
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    CORS(app)

    app.config["REPOSITORY"] = repository or get_repository()
    app.config["ANALYZER"] = analyzer or get_analyzer(app.config["REPOSITORY"])

    def current_repo() -> DatabaseRepository:
        return app.config["REPOSITORY"]

    def current_analyzer():
        return app.config["ANALYZER"]

    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/<path:filename>")
    def serve_static(filename):
        return send_from_directory(app.static_folder, filename)

    @app.route("/api/stats/overview")
    def api_overview():
        repo = current_repo()
        venues = repo.get_all_venues()
        years = repo.get_all_years()
        return jsonify(
            {
                "total_papers": repo.get_paper_count(),
                "total_keywords": repo.get_total_keyword_count(),
                "total_venues": len(venues),
                "venues": venues,
                "years": years,
                "year_range": f"{min(years)}-{max(years)}" if years else "N/A",
            }
        )

    @app.route("/api/stats/venues")
    def api_venues():
        repo = current_repo()
        venues = repo.get_all_venues()
        result = []
        for venue in venues:
            result.append(
                {
                    "name": venue,
                    "paper_count": repo.get_paper_count(venue=venue),
                    "years": repo.get_all_years(venue),
                }
            )
        return jsonify(result)

    @app.route("/api/stats/venue/<venue>")
    def api_venue_detail(venue):
        repo = current_repo()
        years = repo.get_all_years(venue)
        yearly_stats = []
        for year in sorted(years, reverse=True):
            top_kw = repo.get_top_keywords(venue=venue, year=year, limit=10)
            yearly_stats.append(
                {
                    "year": year,
                    "paper_count": repo.get_paper_count(venue=venue, year=year),
                    "top_keywords": [{"keyword": kw, "count": count} for kw, count in top_kw],
                }
            )

        return jsonify(
            {
                "venue": venue,
                "total_papers": repo.get_paper_count(venue=venue),
                "years": years,
                "yearly_stats": yearly_stats,
            }
        )

    @app.route("/api/keywords/top")
    def api_top_keywords():
        repo = current_repo()
        venue = request.args.get("venue")
        year = request.args.get("year", type=int)
        limit = request.args.get("limit", 50, type=int)
        keywords = repo.get_top_keywords(venue=venue, year=year, limit=limit)
        return jsonify([{"keyword": kw, "count": count} for kw, count in keywords])

    @app.route("/api/keywords/trends")
    def api_keyword_trends():
        repo = current_repo()
        keywords = request.args.getlist("keyword")
        venue = request.args.get("venue")

        if not keywords:
            keywords = [kw for kw, _ in repo.get_top_keywords(venue=venue, limit=5)]

        result = []
        for keyword in keywords:
            trend = repo.get_keyword_trend(keyword, venue)
            years = sorted(trend.keys())
            result.append(
                {
                    "keyword": keyword,
                    "years": years,
                    "counts": [trend[year] for year in years],
                }
            )
        return jsonify(result)

    @app.route("/api/keywords/comparison")
    def api_comparison():
        repo = current_repo()
        year = request.args.get("year", type=int)
        limit = request.args.get("limit", 10, type=int)
        if not year:
            years = repo.get_all_years()
            year = max(years) if years else 2024

        comparison = repo.get_venue_comparison(year, limit)
        return jsonify(
            {
                "year": year,
                "venues": {
                    venue: [{"keyword": kw, "count": count} for kw, count in keywords]
                    for venue, keywords in comparison.items()
                },
            }
        )

    @app.route("/api/keywords/wordcloud")
    def api_wordcloud():
        repo = current_repo()
        venue = request.args.get("venue")
        year = request.args.get("year", type=int)
        limit = request.args.get("limit", 100, type=int)
        keywords = repo.get_top_keywords(venue=venue, year=year, limit=limit)
        return jsonify([{"name": kw, "value": count} for kw, count in keywords])

    @app.route("/api/keywords/emerging")
    def api_emerging():
        analyzer = current_analyzer()
        return jsonify(analyzer.get_emerging_keywords(top_n=20))

    @app.route("/api/health")
    def api_health():
        return jsonify({"status": "healthy", "service": "deeptrender"})

    @app.route("/api/status")
    def api_status():
        import os

        repo = current_repo()
        db_path = repo.db_path
        years = repo.get_all_years()
        return jsonify(
            {
                "database": {
                    "path": str(db_path),
                    "size_bytes": os.path.getsize(db_path) if os.path.exists(db_path) else 0,
                    "last_modified": (
                        datetime.fromtimestamp(os.path.getmtime(db_path)).isoformat()
                        if os.path.exists(db_path)
                        else None
                    ),
                },
                "data": {
                    "total_papers": repo.get_paper_count(),
                    "total_venues": len(repo.get_all_venues()),
                    "venues": repo.get_all_venues(),
                    "year_range": [min(years), max(years)] if years else None,
                },
                "server_time": datetime.now().isoformat(),
            }
        )

    # ---------- v0.1 contract-aligned read APIs ----------

    @app.route("/api/v01/overview")
    def api_v01_overview():
        return jsonify(mcp_views.get_overview_v01(repo=current_repo()))

    @app.route("/api/v01/status")
    def api_v01_status():
        return jsonify(mcp_views.get_status_v01(repo=current_repo()))

    @app.route("/api/v01/venues")
    def api_v01_venues():
        limit = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int)
        return jsonify(mcp_views.list_venues_v01(limit=limit, offset=offset, repo=current_repo()))

    @app.route("/api/v01/domains")
    def api_v01_domains():
        limit = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int)
        return jsonify(mcp_views.list_domains(limit=limit, offset=offset))

    @app.route("/api/v01/topics")
    def api_v01_topics():
        domain = request.args.get("domain")
        limit = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int)
        return jsonify(mcp_views.list_topics(domain=domain, limit=limit, offset=offset))

    @app.route("/api/v01/topics/resolve")
    def api_v01_resolve_topic():
        query = request.args.get("query", "")
        include_children = request.args.get("include_children", "false").lower() == "true"
        return jsonify(mcp_views.resolve_topic(query, include_children=include_children))

    @app.route("/api/v01/venue-year-topic")
    def api_v01_venue_year_topic():
        venue = request.args.get("venue", "")
        year = request.args.get("year", type=int)
        topic = request.args.get("topic", "")
        include_children = request.args.get("include_children", "false").lower() == "true"
        limit = request.args.get("limit", 20, type=int)
        offset = request.args.get("offset", 0, type=int)
        if not venue or year is None or not topic:
            return jsonify({"error": "venue, year, and topic are required"}), 400
        return jsonify(
            mcp_views.get_venue_year_topic(
                venue=venue,
                year=year,
                topic=topic,
                include_children=include_children,
                limit=limit,
                offset=offset,
                repo=current_repo(),
            )
        )

    @app.route("/api/v01/data-quality")
    def api_v01_data_quality():
        scope = {
            key: value
            for key, value in {
                "venue": request.args.get("venue"),
                "year": request.args.get("year", type=int),
                "topic": request.args.get("topic"),
                "domain": request.args.get("domain"),
                "source": request.args.get("source"),
            }.items()
            if value not in (None, "")
        }
        return jsonify(mcp_views.get_data_quality_report(scope=scope, repo=current_repo()))

    @app.route("/api/v01/papers/<int:paper_id>/provenance")
    def api_v01_paper_provenance(paper_id):
        return jsonify(mcp_views.get_paper_provenance(paper_id=paper_id, repo=current_repo()))

    @app.route("/api/v01/topic-source-coverage")
    def api_v01_topic_source_coverage():
        topic = request.args.get("topic", "")
        venue = request.args.get("venue")
        year = request.args.get("year", type=int)
        if not topic:
            return jsonify({"error": "topic is required"}), 400
        return jsonify(
            mcp_views.get_topic_source_coverage(
                topic=topic,
                venue=venue,
                year=year,
                repo=current_repo(),
            )
        )

    @app.route("/api/v01/venue-year-source-coverage")
    def api_v01_venue_year_source_coverage():
        venue = request.args.get("venue", "")
        year = request.args.get("year", type=int)
        if not venue or year is None:
            return jsonify({"error": "venue and year are required"}), 400
        return jsonify(
            mcp_views.get_venue_year_source_coverage(
                venue=venue,
                year=year,
                repo=current_repo(),
            )
        )

    @app.route("/api/refresh", methods=["POST"])
    def api_refresh():
        try:
            repo = current_repo()
            refreshed_repo = DatabaseRepository(db_path=repo.db_path)
            app.config["REPOSITORY"] = refreshed_repo
            app.config["ANALYZER"] = get_analyzer(refreshed_repo)
            return jsonify(
                {
                    "status": "success",
                    "message": "Data refreshed",
                    "database_path": str(refreshed_repo.db_path),
                    "total_papers": refreshed_repo.get_paper_count(),
                }
            )
        except Exception as exc:
            return jsonify({"status": "error", "message": str(exc)}), 500

    @app.route("/api/registry/venues")
    def api_registry_venues():
        from config import VENUES

        repo = current_repo()
        all_summaries = repo.analysis.get_all_venue_summaries()
        summary_map = {item["venue"]: item for item in all_summaries if item.get("year") is None}
        result = []

        for _, venue_config in VENUES.items():
            venue_name = venue_config.name
            summary = summary_map.get(venue_name)
            if summary:
                paper_count = summary.get("paper_count", 0)
                top_keywords = summary.get("top_keywords", [])[:10]
            else:
                paper_count = repo.get_paper_count(venue=venue_name)
                top_kw = repo.get_top_keywords(venue=venue_name, limit=10)
                top_keywords = [{"keyword": kw, "count": count} for kw, count in top_kw]

            result.append(
                {
                    "name": venue_name,
                    "full_name": venue_config.full_name,
                    "domain": getattr(venue_config, "domain", "ML"),
                    "years_supported": venue_config.years,
                    "icon_url": f"/static/assets/venues/{venue_name}.svg",
                    "paper_count": paper_count,
                    "latest_year": max(venue_config.years) if venue_config.years else None,
                    "top_keywords": top_keywords,
                }
            )

        return jsonify({"venues": result})

    @app.route("/api/arxiv/timeseries")
    def api_arxiv_timeseries():
        repo = current_repo()
        granularity = request.args.get("granularity", "year")
        category = request.args.get("category", "ALL")
        data = repo.analysis.get_arxiv_timeseries(category, granularity)
        return jsonify(
            {
                "granularity": granularity,
                "category": category,
                "data": data or [],
                "cached": bool(data),
            }
        )

    @app.route("/api/arxiv/keywords/trends")
    def api_arxiv_keyword_trends():
        repo = current_repo()
        granularity = request.args.get("granularity", "year")
        keyword = request.args.get("keyword")
        category = request.args.get("category", "ALL")
        if not keyword:
            return jsonify({"error": "keyword parameter is required"}), 400

        data = repo.analysis.get_keyword_trends_cached(
            scope="arxiv",
            keyword=keyword,
            granularity=granularity,
        )
        return jsonify(
            {
                "keyword": keyword,
                "granularity": granularity,
                "category": category,
                "data": data,
            }
        )

    @app.route("/api/arxiv/stats")
    def api_arxiv_stats():
        repo = current_repo()
        return jsonify(repo.get_arxiv_stats())

    @app.route("/api/arxiv/compare")
    def api_arxiv_compare():
        categories_str = request.args.get("categories", "cs.LG,cs.CV")
        categories = [category.strip() for category in categories_str.split(",")]
        granularity = request.args.get("granularity", "year")
        agent = ArxivAnalysisAgent()
        return jsonify(agent.compare_categories(categories, granularity))

    @app.route("/api/arxiv/emerging")
    def api_arxiv_emerging():
        repo = current_repo()
        category = request.args.get("category", "ALL")
        limit = request.args.get("limit", 20, type=int)
        min_growth_rate = request.args.get("min_growth_rate", 1.5, type=float)
        return jsonify(
            repo.analysis.get_emerging_topics(
                category=category,
                limit=limit,
                min_growth_rate=min_growth_rate,
            )
        )

    @app.route("/api/arxiv/papers")
    def api_arxiv_papers():
        import json

        repo = current_repo()
        category = request.args.get("category")
        limit = request.args.get("limit", 20, type=int)
        offset = request.args.get("offset", 0, type=int)

        with repo._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM raw_papers WHERE source = 'arxiv'"
            params = []

            if category and category != "ALL":
                query += " AND categories LIKE ?"
                params.append(f"%{category}%")

            count_query = query.replace("SELECT *", "SELECT COUNT(*) as total")
            cursor.execute(count_query, params)
            total = cursor.fetchone()["total"]

            query += " ORDER BY retrieved_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cursor.execute(query, params)

            papers = []
            for row in cursor.fetchall():
                papers.append(
                    {
                        "arxiv_id": row["source_paper_id"],
                        "title": row["title"],
                        "abstract": row["abstract"],
                        "authors": json.loads(row["authors"]) if row["authors"] else [],
                        "categories": row["categories"],
                        "year": row["year"],
                        "retrieved_at": row["retrieved_at"],
                        "doi": row["doi"],
                        "journal_ref": row["journal_ref"],
                        "comments": row["comments"],
                    }
                )

        return jsonify({"total": total, "limit": limit, "offset": offset, "papers": papers})

    @app.route("/api/arxiv/paper/<arxiv_id>")
    def api_arxiv_paper_detail(arxiv_id):
        repo = current_repo()
        paper = repo.raw.get_raw_paper_by_source("arxiv", arxiv_id)
        if not paper:
            return jsonify({"error": "Paper not found"}), 404

        result = {
            "arxiv_id": paper.source_paper_id,
            "title": paper.title,
            "abstract": paper.abstract,
            "authors": paper.authors,
            "categories": paper.categories,
            "year": paper.year,
            "doi": paper.doi,
            "journal_ref": paper.journal_ref,
            "comments": paper.comments,
            "retrieved_at": paper.retrieved_at.isoformat() if paper.retrieved_at else None,
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
            "abs_url": f"https://arxiv.org/abs/{arxiv_id}",
        }

        paper_id = repo.structured.find_paper_by_title(paper.title)
        if paper_id:
            keywords = repo.analysis.get_paper_keywords(paper_id)
            result["keywords"] = [keyword.keyword for keyword in keywords[:10]]
        else:
            result["keywords"] = []
        result["related_papers"] = []
        return jsonify(result)

    @app.route("/api/analysis/meta")
    def api_analysis_meta():
        repo = current_repo()
        return jsonify(repo.analysis.get_all_meta())

    @app.route("/api/venues/discover", methods=["POST"])
    def api_discover_venues():
        repo = current_repo()
        payload = request.json or {}
        discovery = VenueDiscovery()
        venues = discovery.discover_conferences(
            min_year=payload.get("min_year", 2022),
            include_workshops=payload.get("include_workshops", False),
        )

        grouped = {}
        for venue in venues:
            item = grouped.setdefault(
                venue.name,
                {
                    "full_name": venue.full_name,
                    "domain": venue.domain,
                    "tier": venue.tier,
                    "venue_type": "workshop" if venue.is_workshop else "conference",
                    "openreview_ids": [],
                    "years": [],
                },
            )
            item["openreview_ids"].append(venue.venue_id)
            item["years"].append(venue.year)

        saved_count = 0
        for name, data in grouped.items():
            repo.structured.save_discovered_venue(
                name=name,
                full_name=data["full_name"],
                domain=data["domain"],
                tier=data["tier"],
                venue_type=data["venue_type"],
                openreview_ids=sorted(set(data["openreview_ids"])),
                years=sorted(set(data["years"]), reverse=True),
            )
            saved_count += 1

        return jsonify(
            {
                "status": "success",
                "discovered": len(venues),
                "saved": saved_count,
                "summary": discovery.get_summary_by_domain(venues),
            }
        )

    @app.route("/api/venues/stats")
    def api_venue_stats():
        repo = current_repo()
        return jsonify(repo.structured.get_venue_stats())

    @app.route("/api/venues/by-domain")
    def api_venues_by_domain():
        repo = current_repo()
        domain = request.args.get("domain")
        if not domain:
            return jsonify({"error": "domain parameter required"}), 400

        venues = repo.structured.get_venues_by_domain(domain)
        return jsonify(
            {
                "domain": domain,
                "venues": [
                    {
                        "name": venue.canonical_name,
                        "full_name": venue.full_name,
                        "domain": venue.domain,
                        "tier": getattr(venue, "tier", "C"),
                        "years": getattr(venue, "years_available", []),
                        "openreview_ids": getattr(venue, "openreview_ids", []),
                    }
                    for venue in venues
                ],
            }
        )

    @app.route("/api/venues/by-tier")
    def api_venues_by_tier():
        repo = current_repo()
        tier = request.args.get("tier", "A")
        venues = repo.structured.get_venues_by_tier(tier)
        return jsonify(
            {
                "tier": tier,
                "venues": [
                    {
                        "name": venue.canonical_name,
                        "full_name": venue.full_name,
                        "domain": venue.domain,
                        "tier": getattr(venue, "tier", "C"),
                        "years": getattr(venue, "years_available", []),
                        "paper_count": repo.get_paper_count(venue=venue.canonical_name),
                    }
                    for venue in venues
                ],
            }
        )

    @app.route("/api/venues/explorer")
    def api_venue_explorer():
        repo = current_repo()
        venues = repo.structured.get_all_venues()
        result = {"total": len(venues), "venues": [], "by_domain": {}, "by_tier": {}}

        for venue in venues:
            venue_data = {
                "name": venue.canonical_name,
                "full_name": venue.full_name,
                "domain": venue.domain,
                "tier": getattr(venue, "tier", "C"),
                "type": venue.venue_type,
                "years": getattr(venue, "years_available", []),
                "paper_count": repo.get_paper_count(venue=venue.canonical_name),
                "openreview_ids": getattr(venue, "openreview_ids", [])[:3],
            }
            result["venues"].append(venue_data)

            domain = venue.domain or "General"
            result["by_domain"].setdefault(domain, []).append(venue_data)

            tier = getattr(venue, "tier", "C")
            result["by_tier"].setdefault(tier, []).append(venue_data)

        return jsonify(result)

    return app


def run_server(host: str = "0.0.0.0", port: int = 5000, debug: bool = True):
    app = create_app()
    print(f"\nDeepTrender Web server running at http://localhost:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_server()
