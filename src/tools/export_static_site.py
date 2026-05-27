#!/usr/bin/env python3
"""Static site export tool.

Exports data and static assets into a docs-friendly folder layout.
"""

import sys
import json
import shutil
import argparse
import csv
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseRepository, get_repository
from config import VENUES, ROOT_DIR
from taxonomy.keyword_normalizer import get_keyword_canonicalizer


ARXIV_EXPORT_CATEGORIES = ["ALL", "cs.LG", "cs.CV", "cs.CL", "cs.AI", "cs.RO"]
ARXIV_EXPORT_GRANULARITIES = ["year", "month", "week", "day"]


class StaticSiteExporter:
    """Exporter for static website data and assets."""

    def __init__(
        self,
        output_dir: str = "docs",
        top_keywords: int = 300,
        repository: Optional[DatabaseRepository] = None,
    ):
        self.output_dir = Path(output_dir)
        self.data_dir = self.output_dir / "data"
        self.venues_data_dir = self.data_dir / "venues"
        self.arxiv_data_dir = self.data_dir / "arxiv"
        self.quality_data_dir = self.data_dir / "quality"
        self.top_keywords = top_keywords

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.venues_data_dir.mkdir(parents=True, exist_ok=True)
        self.arxiv_data_dir.mkdir(parents=True, exist_ok=True)
        self.quality_data_dir.mkdir(parents=True, exist_ok=True)

        self.repo = repository or get_repository()
        self.registry_metadata = self._load_venue_registry_metadata()
        self._keyword_cache = None
        self.stats = {
            "venues_exported": 0,
            "venues_with_data": 0,
            "arxiv_exported": 0,
            "files_copied": 0,
            "total_size_bytes": 0,
        }

    def _clear_generated_venue_data(self) -> None:
        # Active export files are overwritten below. Avoid unlinking existing
        # artifacts so restricted Windows environments can regenerate docs.
        return

    def _load_venue_registry_metadata(self) -> Dict[str, Dict[str, Any]]:
        metadata = {
            name: {
                "name": config.name,
                "full_name": config.full_name,
                "domain": "ML",
                "tier": "A",
                "source": "config",
            }
            for name, config in VENUES.items()
        }

        registry_path = ROOT_DIR / "data" / "registry" / "ccf_venues.csv"
        if not registry_path.exists():
            return metadata

        with registry_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                name = (row.get("canonical_name") or "").strip()
                if not name:
                    continue
                metadata[name] = {
                    "name": name,
                    "full_name": row.get("full_name") or name,
                    "domain": row.get("domain") or "General",
                    "tier": row.get("tier") or "C",
                    "source": row.get("source_preference") or "registry",
                }
        return metadata

    def collect_venue_names(self) -> List[str]:
        names = set(self.registry_metadata)
        names.update(venue.canonical_name for venue in self.repo.structured.get_all_venues())
        names.update(VENUES)

        def sort_key(name: str):
            return (
                -self.repo.get_paper_count(venue=name),
                self.registry_metadata.get(name, {}).get("tier", "Z"),
                name,
            )

        return sorted(names, key=sort_key)

    def is_known_venue_name(self, venue_name: str) -> bool:
        return (
            venue_name in self.registry_metadata
            or venue_name in VENUES
            or self.repo.structured.get_venue_by_name(venue_name) is not None
        )

    def build_venue_index_entry(self, venue_name: str) -> Dict[str, Any]:
        metadata = self.registry_metadata.get(venue_name, {"name": venue_name})
        venue_obj = self.repo.structured.get_venue_by_name(venue_name)
        years = self.repo.get_all_years(venue=venue_name)
        paper_count = self.repo.get_paper_count(venue=venue_name)
        top_kw = self._top_cached_keywords(venue=venue_name, limit=10)
        top_keywords = [{"keyword": kw, "count": c} for kw, c in top_kw]
        has_data = paper_count > 0
        data_warnings = []
        if not has_data:
            data_warnings.append(
                {
                    "code": "registered_no_papers",
                    "message": "Venue is registered but no structured papers were exported for it.",
                }
            )
        elif not top_keywords:
            data_warnings.append(
                {
                    "code": "low_sample_size",
                    "message": "Venue has papers but no exported keyword facts.",
                }
            )

        return {
            "name": venue_name,
            "full_name": metadata.get("full_name")
            or getattr(venue_obj, "full_name", None)
            or venue_name,
            "domain": metadata.get("domain")
            or getattr(venue_obj, "domain", None)
            or "General",
            "tier": metadata.get("tier")
            or getattr(venue_obj, "tier", None)
            or "C",
            "source": metadata.get("source", "database"),
            "years_available": sorted(years, reverse=True),
            "paper_count": paper_count,
            "top_keywords": top_keywords,
            "has_data": has_data,
            "data_status": "ok" if has_data else "registered_no_papers",
            "warnings": data_warnings,
        }

    def collect_venue_index_data(self) -> List[Dict[str, Any]]:
        venues_data = []
        for venue_name in self.collect_venue_names():
            venues_data.append(self.build_venue_index_entry(venue_name))
        return venues_data

    def _get_keyword_cache(self) -> Dict[str, Any]:
        if self._keyword_cache is not None:
            return self._keyword_cache

        cache = {
            "labels": {},
            "topics": {},
            "global": defaultdict(set),
            "global_year": defaultdict(lambda: defaultdict(set)),
            "venue": defaultdict(lambda: defaultdict(set)),
            "venue_year": defaultdict(lambda: defaultdict(set)),
        }
        canonicalizer = get_keyword_canonicalizer()

        with self.repo._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT v.canonical_name AS venue, p.year, pk.keyword, pk.paper_id
                FROM paper_keywords pk
                JOIN papers p ON pk.paper_id = p.paper_id
                LEFT JOIN venues v ON p.venue_id = v.venue_id
                """
            )

            for row in cursor.fetchall():
                venue = row["venue"]
                year = row["year"]
                paper_id = row["paper_id"]
                normalized = canonicalizer.normalize(row["keyword"])
                if not normalized or paper_id is None:
                    continue

                key = normalized.canonical_key
                cache["labels"][key] = normalized.canonical_keyword
                cache["topics"][key] = normalized.topic_id
                cache["global"][key].add(paper_id)
                if year is not None:
                    cache["global_year"][int(year)][key].add(paper_id)
                if venue:
                    cache["venue"][venue][key].add(paper_id)
                    if year is not None:
                        cache["venue_year"][(venue, int(year))][key].add(paper_id)

        self._keyword_cache = cache
        return cache

    def _top_cached_keyword_keys(
        self,
        venue: Optional[str] = None,
        year: Optional[int] = None,
        limit: int = 50,
    ) -> List[tuple[str, str, int]]:
        cache = self._get_keyword_cache()
        if venue and year:
            group = cache["venue_year"].get((venue, int(year)), {})
        elif venue:
            group = cache["venue"].get(venue, {})
        elif year:
            group = cache["global_year"].get(int(year), {})
        else:
            group = cache["global"]

        rows = [
            (key, cache["labels"].get(key, key.replace("_", " ")), len(paper_ids))
            for key, paper_ids in group.items()
        ]
        return sorted(rows, key=lambda item: (-item[2], item[1]))[:limit]

    def _top_cached_keywords(
        self,
        venue: Optional[str] = None,
        year: Optional[int] = None,
        limit: int = 50,
    ) -> List[Tuple[str, int]]:
        return [
            (label, count)
            for _, label, count in self._top_cached_keyword_keys(
                venue=venue,
                year=year,
                limit=limit,
            )
        ]

    def export_venues_index(self, venues_data: Optional[List[Dict[str, Any]]] = None) -> int:
        venues_data = venues_data if venues_data is not None else self.collect_venue_index_data()

        output_file = self.venues_data_dir / "venues_index.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(venues_data, f, indent=2, ensure_ascii=False)

        self.stats["total_size_bytes"] += output_file.stat().st_size
        return len(venues_data)

    def export_venue_top_keywords(self, venue_name: str, top_n: int = 50) -> bool:
        if not self.is_known_venue_name(venue_name):
            return False

        years = self.repo.get_all_years(venue=venue_name)
        yearly_data = {}
        for year in sorted(years):
            top_keywords = self._top_cached_keywords(venue=venue_name, year=year, limit=top_n)
            denominator = self.repo.get_paper_count(venue=venue_name, year=year)
            yearly_data[str(year)] = [
                {
                    "keyword": kw,
                    "count": count,
                    "relative_frequency": round(count / denominator, 6) if denominator else 0,
                    "rank": rank + 1,
                }
                for rank, (kw, count) in enumerate(top_keywords)
            ]

        output_file = self.venues_data_dir / f"venue_{venue_name}_top_keywords.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(yearly_data, f, indent=2, ensure_ascii=False)

        self.stats["total_size_bytes"] += output_file.stat().st_size
        return True

    def export_venue_keyword_trends(self, venue_name: str, max_keywords: int = 300) -> bool:
        if not self.is_known_venue_name(venue_name):
            return False

        years = self.repo.get_all_years(venue=venue_name)
        keyword_yearly_counts = defaultdict(dict)
        keyword_yearly_ranks = defaultdict(dict)

        for year in sorted(years):
            top_keywords = self._top_cached_keyword_keys(venue=venue_name, year=year, limit=100)
            denominator = self.repo.get_paper_count(venue=venue_name, year=year)
            for rank, (key, _label, count) in enumerate(top_keywords, start=1):
                keyword_yearly_counts[key][year] = {
                    "count": count,
                    "relative_frequency": round(count / denominator, 6) if denominator else 0,
                }
                keyword_yearly_ranks[key][year] = rank

        keyword_totals = {
            kw: sum(point["count"] for point in counts.values())
            for kw, counts in keyword_yearly_counts.items()
        }
        top_keywords = sorted(keyword_totals.keys(), key=lambda k: keyword_totals[k], reverse=True)[:max_keywords]

        trends_data = {}
        labels = self._get_keyword_cache()["labels"]
        for kw in top_keywords:
            yearly_points = []
            for year in sorted(years):
                yearly_points.append(
                    {
                        "year": year,
                        "count": keyword_yearly_counts[kw].get(year, {}).get("count", 0),
                        "relative_frequency": keyword_yearly_counts[kw].get(year, {}).get("relative_frequency", 0),
                        "rank": keyword_yearly_ranks[kw].get(year, 0),
                    }
                )
            trends_data[labels.get(kw, kw.replace("_", " "))] = yearly_points

        output_file = self.venues_data_dir / f"venue_{venue_name}_keyword_trends.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(trends_data, f, indent=2, ensure_ascii=False)

        self.stats["total_size_bytes"] += output_file.stat().st_size
        return True

    def export_venue_keywords_index(self, venue_name: str) -> bool:
        if not self.is_known_venue_name(venue_name):
            return False

        top_keywords = self._top_cached_keywords(venue=venue_name, limit=self.top_keywords)

        output_file = self.venues_data_dir / f"venue_{venue_name}_keywords_index.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump([kw for kw, _ in top_keywords], f, indent=2, ensure_ascii=False)

        self.stats["total_size_bytes"] += output_file.stat().st_size
        return True

    def export_global_keyword_trends(self, venue_names: List[str], max_keywords: int = 50) -> bool:
        cache = self._get_keyword_cache()
        if not cache["global"]:
            return False

        all_years = sorted(cache["global_year"])
        top_keywords = self._top_cached_keyword_keys(limit=max_keywords)

        rows = []
        for key, label, _total in top_keywords:
            counts = [
                len(cache["global_year"].get(year, {}).get(key, set()))
                for year in all_years
            ]
            denominators = [self.repo.get_paper_count(year=year) for year in all_years]
            rows.append({
                "keyword": label,
                "years": all_years,
                "counts": counts,
                "total": sum(counts),
                "points": [
                    {
                        "year": year,
                        "count": count,
                        "relative_frequency": round(count / denominator, 6) if denominator else 0,
                        "rank": 0,
                    }
                    for year, count, denominator in zip(all_years, counts, denominators)
                ],
            })

        output_file = self.venues_data_dir / "global_keyword_trends.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)

        self.stats["total_size_bytes"] += output_file.stat().st_size
        return True

    def export_global_emerging_keywords(self, limit: int = 50) -> bool:
        trends_file = self.venues_data_dir / "global_keyword_trends.json"
        if not trends_file.exists():
            return False

        with open(trends_file, "r", encoding="utf-8") as f:
            trends = json.load(f)

        candidates = []
        for row in trends:
            years = row.get("years", [])
            counts = row.get("counts", [])
            if not years or not counts:
                continue

            latest_count = int(counts[-1] or 0)
            previous_count = int(counts[-2] or 0) if len(counts) > 1 else 0
            if latest_count <= 0:
                continue

            growth_rate = ((latest_count + 1) / (previous_count + 1) - 1) * 100
            first_seen = next(
                (year for year, count in zip(years, counts) if int(count or 0) > 0),
                years[-1],
            )
            candidates.append({
                "keyword": row["keyword"],
                "growth_rate": growth_rate,
                "first_seen": first_seen,
                "recent_count": latest_count,
                "previous_count": previous_count,
                "trend": "up" if latest_count >= previous_count else "down",
            })

        if not candidates:
            candidates = [
                {
                    "keyword": row["keyword"],
                    "growth_rate": 0,
                    "first_seen": row.get("years", [None])[0],
                    "recent_count": int((row.get("counts") or [0])[-1] or 0),
                    "previous_count": 0,
                    "trend": "flat",
                }
                for row in trends[:limit]
            ]

        candidates.sort(key=lambda item: (item["growth_rate"], item["recent_count"]), reverse=True)

        output_file = self.venues_data_dir / "global_emerging_keywords.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(candidates[:limit], f, indent=2, ensure_ascii=False)

        self.stats["total_size_bytes"] += output_file.stat().st_size
        return True

    def export_keyword_normalization_audit(self) -> bool:
        audit = self.repo.get_keyword_normalization_audit(limit=25)
        audit["generated_at"] = datetime.now().isoformat()
        audit["policy"] = {
            "taxonomy_policy": "DeepTrender canonical topics backed by arXiv, ACM CCS, and Papers with Code mappings where configured.",
            "alias_policy": "strict taxonomy aliases plus export-only keyword_stat_aliases for extractor fragments.",
        }

        output_file = self.quality_data_dir / "keyword_normalization_audit.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(audit, f, indent=2, ensure_ascii=False)

        self.stats["total_size_bytes"] += output_file.stat().st_size
        return True

    def export_all_venues(self) -> Dict:
        self._clear_generated_venue_data()
        exported_venues = []
        venues_with_data = []
        venues_data = []

        for venue_name in self.collect_venue_names():
            self.export_venue_top_keywords(venue_name, top_n=50)
            self.export_venue_keyword_trends(venue_name, max_keywords=self.top_keywords)
            self.export_venue_keywords_index(venue_name)
            exported_venues.append(venue_name)
            venue_data = self.build_venue_index_entry(venue_name)
            venues_data.append(venue_data)
            if venue_data["has_data"]:
                venues_with_data.append(venue_name)

        venues_count = self.export_venues_index(venues_data)
        self.export_global_keyword_trends(exported_venues)
        self.export_global_emerging_keywords()
        self.stats["venues_exported"] = len(exported_venues)
        self.stats["venues_with_data"] = len(venues_with_data)
        return {
            "venues_count": venues_count,
            "venues_exported": exported_venues,
            "venues_with_data": venues_with_data,
        }

    def export_arxiv_timeseries(self) -> int:
        exported_count = 0

        for granularity in ARXIV_EXPORT_GRANULARITIES:
            for category in ARXIV_EXPORT_CATEGORIES:
                data = self.repo.analysis.get_arxiv_timeseries(category, granularity)
                warnings = self._arxiv_warnings(category=category, data=data)

                output_data = {
                    "granularity": granularity,
                    "category": category,
                    "data": data,
                    "cached": True,
                    "exported_at": datetime.now().isoformat(),
                    "warnings": warnings,
                }
                output_file = self.arxiv_data_dir / f"arxiv_timeseries_{granularity}_{category}.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(output_data, f, indent=2, ensure_ascii=False)

                self.stats["total_size_bytes"] += output_file.stat().st_size
                exported_count += 1

        return exported_count

    def _arxiv_keyword_trend_rows(self, category: str, granularity: str) -> Dict[str, List[Dict[str, Any]]]:
        rows = self.repo.analysis.get_keyword_trends_for_scope(
            scope="arxiv",
            granularity=granularity,
            venue=category,
        )
        trends = defaultdict(list)
        for row in rows:
            trends[row["keyword"]].append(
                {
                    "bucket": row["bucket"],
                    "count": row["count"],
                    "relative_frequency": row.get("relative_frequency", 0),
                    "rank": row.get("rank", 0),
                }
            )
        return dict(trends)

    def export_arxiv_keyword_trends(self) -> int:
        exported_count = 0
        for category in ARXIV_EXPORT_CATEGORIES:
            keyword_totals = defaultdict(int)
            for granularity in ARXIV_EXPORT_GRANULARITIES:
                trends = self._arxiv_keyword_trend_rows(category, granularity)
                warnings = []
                if not trends:
                    warnings.append(
                        {
                            "code": "registered_no_papers",
                            "message": "No arXiv keyword trend cache was exported for this category/granularity.",
                        }
                    )
                for keyword, points in trends.items():
                    keyword_totals[keyword] += sum(int(point.get("count") or 0) for point in points)
                output_data = {
                    "category": category,
                    "granularity": granularity,
                    "trends": trends,
                    "exported_at": datetime.now().isoformat(),
                    "warnings": warnings,
                }
                output_file = self.arxiv_data_dir / f"arxiv_keyword_trends_{granularity}_{category}.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(output_data, f, indent=2, ensure_ascii=False)
                self.stats["total_size_bytes"] += output_file.stat().st_size
                exported_count += 1

            keywords = [
                keyword
                for keyword, _total in sorted(
                    keyword_totals.items(),
                    key=lambda item: (-item[1], item[0]),
                )[: self.top_keywords]
            ]
            index_output = {
                "category": category,
                "keywords": keywords,
                "exported_at": datetime.now().isoformat(),
                "warnings": []
                if keywords
                else [
                    {
                        "code": "registered_no_papers",
                        "message": "No cached arXiv keywords were exported for this category.",
                    }
                ],
            }
            output_file = self.arxiv_data_dir / f"arxiv_keywords_index_{category}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(index_output, f, indent=2, ensure_ascii=False)
            self.stats["total_size_bytes"] += output_file.stat().st_size
            exported_count += 1
        return exported_count

    def _arxiv_raw_and_linked_counts(self, category: str) -> Tuple[int, int]:
        with self.repo._get_connection() as conn:
            cursor = conn.cursor()
            params = []
            where = "WHERE r.source = 'arxiv'"
            if category != "ALL":
                where += " AND r.categories LIKE ?"
                params.append(f"%{category}%")
            cursor.execute(f"SELECT COUNT(*) AS count FROM raw_papers r {where}", params)
            raw_count = cursor.fetchone()["count"]
            cursor.execute(
                f"""
                SELECT COUNT(DISTINCT ps.paper_id) AS count
                FROM raw_papers r
                JOIN paper_sources ps ON ps.raw_id = r.raw_id AND ps.source = 'arxiv'
                {where}
                """,
                params,
            )
            linked_count = cursor.fetchone()["count"]
        return raw_count, linked_count

    def _arxiv_warnings(self, category: str, data: Optional[List[Dict]] = None) -> List[Dict[str, str]]:
        warnings = []
        raw_count, linked_count = self._arxiv_raw_and_linked_counts(category)
        if raw_count == 0:
            warnings.append({"code": "registered_no_papers", "message": "No raw arXiv papers are registered for this category."})
        if raw_count > linked_count:
            warnings.append(
                {
                    "code": "missing_source_mapping",
                    "message": f"{raw_count - linked_count} raw arXiv papers are not linked to structured paper_id records.",
                }
            )
        if linked_count and linked_count < 5:
            warnings.append({"code": "low_sample_size", "message": "Fewer than 5 linked arXiv papers are available."})
        if not data:
            warnings.append({"code": "registered_no_papers", "message": "No analysis cache was exported for this arXiv scope."})
        for row in data or []:
            warnings.extend(row.get("warnings") or [])
        if self._stale_status() == "stale":
            warnings.append({"code": "stale_data", "message": "Latest source data is older than the freshness threshold."})
        return self._dedupe_warnings(warnings)

    def export_arxiv_quality(self) -> int:
        exported_count = 0
        for category in ARXIV_EXPORT_CATEGORIES:
            raw_count, linked_count = self._arxiv_raw_and_linked_counts(category)
            timeseries = []
            for granularity in ARXIV_EXPORT_GRANULARITIES:
                timeseries.extend(self.repo.analysis.get_arxiv_timeseries(category, granularity))
            output_data = {
                "category": category,
                "generated_at": datetime.now().isoformat(),
                "raw_paper_count": raw_count,
                "linked_paper_count": linked_count,
                "source_mapping_coverage_ratio": round(linked_count / raw_count, 6) if raw_count else 0,
                "stale_status": self._stale_status(),
                "warnings": self._arxiv_warnings(category=category, data=timeseries),
            }
            output_file = self.arxiv_data_dir / f"arxiv_quality_{category}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            self.stats["total_size_bytes"] += output_file.stat().st_size
            exported_count += 1
        return exported_count

    def export_arxiv_emerging(self) -> int:
        categories = ["ALL", "cs.LG", "cs.CV", "cs.CL", "cs.AI", "cs.RO"]
        exported_count = 0

        for category in categories:
            topics = self.repo.analysis.get_emerging_topics(category=category, limit=50, min_growth_rate=1.5)
            if not topics:
                continue

            output_file = self.arxiv_data_dir / f"arxiv_emerging_{category}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(topics, f, indent=2, ensure_ascii=False)

            self.stats["total_size_bytes"] += output_file.stat().st_size
            exported_count += 1

        return exported_count

    def export_arxiv_stats(self) -> bool:
        stats_data = self.repo.get_arxiv_stats()
        stats_data["exported_at"] = datetime.now().isoformat()

        output_file = self.arxiv_data_dir / "arxiv_stats.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(stats_data, f, indent=2, ensure_ascii=False)

        self.stats["total_size_bytes"] += output_file.stat().st_size
        return True

    def export_all_arxiv(self) -> Dict:
        results = {
            "timeseries": self.export_arxiv_timeseries(),
            "keyword_trends": self.export_arxiv_keyword_trends(),
            "quality": self.export_arxiv_quality(),
            "emerging": self.export_arxiv_emerging(),
            "stats": self.export_arxiv_stats(),
        }
        self.stats["arxiv_exported"] = sum(1 for v in results.values() if v)
        return results

    def copy_static_assets(self) -> int:
        src_static = ROOT_DIR / "src" / "web" / "static"
        if not src_static.exists():
            return 0

        copied_count = 0
        for item in src_static.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(src_static)
                dest_path = self.output_dir / rel_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest_path)
                copied_count += 1
                self.stats["total_size_bytes"] += dest_path.stat().st_size

        self.stats["files_copied"] = copied_count
        return copied_count

    def _dedupe_warnings(self, warnings: List[Dict[str, str]]) -> List[Dict[str, str]]:
        seen = set()
        deduped = []
        for warning in warnings:
            key = (warning.get("code"), warning.get("message"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(warning)
        return deduped

    def _stale_status(self) -> str:
        latest = self.repo.analysis.get_max_retrieved_at()
        if not latest:
            return "no_data"
        try:
            latest_dt = datetime.fromisoformat(str(latest))
        except ValueError:
            return "unknown"
        return "stale" if datetime.now() - latest_dt > timedelta(days=30) else "fresh"

    def _coverage_ratios(self) -> Dict[str, float]:
        total_papers = self.repo.get_paper_count()
        if total_papers <= 0:
            return {"keyword_coverage_ratio": 0, "topic_fact_coverage_ratio": 0}
        with self.repo._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(DISTINCT paper_id) AS count FROM paper_keywords")
            keyword_papers = cursor.fetchone()["count"]
            cursor.execute("SELECT COUNT(DISTINCT paper_id) AS count FROM paper_topics")
            topic_papers = cursor.fetchone()["count"]
        return {
            "keyword_coverage_ratio": round(keyword_papers / total_papers, 6),
            "topic_fact_coverage_ratio": round(topic_papers / total_papers, 6),
        }

    def export_manifest(self):
        self.stats["total_papers"] = self.repo.get_paper_count()
        self.stats["total_keywords"] = self.repo.get_total_keyword_count()
        coverage = self._coverage_ratios()
        venues_with_data = self.stats.get("venues_with_data", [])
        if isinstance(venues_with_data, int):
            venues_with_data = [
                item["name"]
                for item in self.collect_venue_index_data()
                if item.get("has_data")
            ]
        venues_exported = self.stats.get("venues_exported", [])
        if isinstance(venues_exported, int):
            venues_exported = [item["name"] for item in self.collect_venue_index_data()]
        venues_without_data = sorted(set(venues_exported) - set(venues_with_data))
        manifest = {
            "generated_at": datetime.now().isoformat(),
            "stale_status": self._stale_status(),
            "arxiv_categories_exported": ARXIV_EXPORT_CATEGORIES,
            "venues_exported": venues_exported,
            "venues_with_data": venues_with_data,
            "venues_without_data": venues_without_data,
            "keyword_coverage_ratio": coverage["keyword_coverage_ratio"],
            "topic_fact_coverage_ratio": coverage["topic_fact_coverage_ratio"],
            "warnings": self._dedupe_warnings(
                [
                    {
                        "code": "stale_data",
                        "message": "Latest source data is older than the freshness threshold.",
                    }
                ]
                if self._stale_status() == "stale"
                else []
            ),
            "stats": self.stats,
        }
        manifest_file = self.output_dir / "data" / "manifest.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

    def export_all(self):
        self.export_all_venues()
        self.export_all_arxiv()
        self.export_keyword_normalization_audit()
        self.copy_static_assets()
        self.export_manifest()
        return self.stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Export DeepTrender static site")
    parser.add_argument("--output-dir", type=str, default="docs", help="Output directory")
    parser.add_argument("--top-keywords", type=int, default=300, help="Max keywords per venue")
    args = parser.parse_args()

    exporter = StaticSiteExporter(output_dir=args.output_dir, top_keywords=args.top_keywords)
    try:
        exporter.export_all()
        print(f"Static export complete: {args.output_dir}")
        return 0
    except Exception as e:
        print(f"Export failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
