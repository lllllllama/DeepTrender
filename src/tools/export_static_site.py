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
from datetime import datetime
from typing import Any, Dict, List, Optional
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseRepository, get_repository
from config import VENUES, ROOT_DIR


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
        self.stats = {
            "venues_exported": 0,
            "venues_with_data": 0,
            "arxiv_exported": 0,
            "files_copied": 0,
            "total_size_bytes": 0,
        }

    def _clear_generated_venue_data(self) -> None:
        for path in self.venues_data_dir.glob("venue_*_*.json"):
            path.unlink()
        for filename in ("global_keyword_trends.json", "global_emerging_keywords.json"):
            path = self.venues_data_dir / filename
            if path.exists():
                path.unlink()

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
        top_kw = self.repo.get_top_keywords(venue=venue_name, limit=10)
        top_keywords = [{"keyword": kw, "count": c} for kw, c in top_kw]

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
            "has_data": paper_count > 0,
        }

    def collect_venue_index_data(self) -> List[Dict[str, Any]]:
        venues_data = []
        for venue_name in self.collect_venue_names():
            venues_data.append(self.build_venue_index_entry(venue_name))
        return venues_data

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
            top_keywords = self.repo.get_top_keywords(venue=venue_name, year=year, limit=top_n)
            yearly_data[str(year)] = [
                {"keyword": kw, "count": count, "rank": rank + 1}
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
            top_keywords = self.repo.get_top_keywords(venue=venue_name, year=year, limit=100)
            for rank, (kw, count) in enumerate(top_keywords, start=1):
                keyword_yearly_counts[kw][year] = count
                keyword_yearly_ranks[kw][year] = rank

        keyword_totals = {kw: sum(counts.values()) for kw, counts in keyword_yearly_counts.items()}
        top_keywords = sorted(keyword_totals.keys(), key=lambda k: keyword_totals[k], reverse=True)[:max_keywords]

        trends_data = {}
        for kw in top_keywords:
            yearly_points = []
            for year in sorted(years):
                yearly_points.append(
                    {
                        "year": year,
                        "count": keyword_yearly_counts[kw].get(year, 0),
                        "rank": keyword_yearly_ranks[kw].get(year, 0),
                    }
                )
            trends_data[kw] = yearly_points

        output_file = self.venues_data_dir / f"venue_{venue_name}_keyword_trends.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(trends_data, f, indent=2, ensure_ascii=False)

        self.stats["total_size_bytes"] += output_file.stat().st_size
        return True

    def export_venue_keywords_index(self, venue_name: str) -> bool:
        if not self.is_known_venue_name(venue_name):
            return False

        top_keywords = self.repo.get_top_keywords(venue=venue_name, limit=self.top_keywords)

        output_file = self.venues_data_dir / f"venue_{venue_name}_keywords_index.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump([kw for kw, _ in top_keywords], f, indent=2, ensure_ascii=False)

        self.stats["total_size_bytes"] += output_file.stat().st_size
        return True

    def export_global_keyword_trends(self, venue_names: List[str], max_keywords: int = 50) -> bool:
        keyword_yearly_counts = defaultdict(lambda: defaultdict(int))

        for venue_name in venue_names:
            input_file = self.venues_data_dir / f"venue_{venue_name}_keyword_trends.json"
            if not input_file.exists():
                continue
            with open(input_file, "r", encoding="utf-8") as f:
                trends = json.load(f)

            for keyword, points in trends.items():
                for point in points:
                    year = int(point["year"])
                    keyword_yearly_counts[keyword][year] += int(point.get("count", 0) or 0)

        if not keyword_yearly_counts:
            return False

        all_years = sorted({
            year
            for yearly_counts in keyword_yearly_counts.values()
            for year in yearly_counts
        })
        totals = {
            keyword: sum(yearly_counts.values())
            for keyword, yearly_counts in keyword_yearly_counts.items()
        }
        top_keywords = sorted(totals, key=totals.get, reverse=True)[:max_keywords]

        rows = []
        for keyword in top_keywords:
            counts = [keyword_yearly_counts[keyword].get(year, 0) for year in all_years]
            rows.append({
                "keyword": keyword,
                "years": all_years,
                "counts": counts,
                "total": sum(counts),
                "points": [
                    {"year": year, "count": count, "rank": 0}
                    for year, count in zip(all_years, counts)
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
        granularities = ["day", "week", "month", "year"]
        categories = ["ALL", "cs.LG", "cs.CV", "cs.CL", "cs.AI", "cs.RO"]
        exported_count = 0

        for granularity in granularities:
            for category in categories:
                data = self.repo.analysis.get_arxiv_timeseries(category, granularity)
                if not data:
                    continue

                output_data = {
                    "granularity": granularity,
                    "category": category,
                    "data": data,
                    "cached": True,
                    "exported_at": datetime.now().isoformat(),
                }
                output_file = self.arxiv_data_dir / f"arxiv_timeseries_{granularity}_{category}.json"
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

    def export_manifest(self):
        self.stats["total_papers"] = self.repo.get_paper_count()
        self.stats["total_keywords"] = self.repo.get_total_keyword_count()
        manifest = {
            "generated_at": datetime.now().isoformat(),
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
