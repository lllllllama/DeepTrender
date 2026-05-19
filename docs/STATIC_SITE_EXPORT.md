# Static Site Export Guide

This guide explains how to export DeepTrender data to a static GitHub Pages site.

## Overview

The static site export system allows you to deploy DeepTrender as a fully static website on GitHub Pages, without requiring a Flask backend. The frontend automatically detects whether it's running in static mode or API mode.

## Quick Start

### 1. Export Static Site

```bash
python src/tools/export_static_site.py --output-dir docs --top-keywords 300
```

### 2. Test Locally

```bash
python -m http.server -d docs 8000
```

Visit: http://localhost:8000

### 3. Deploy to GitHub Pages

1. Go to Settings → Pages
2. Source: GitHub Actions
3. Save
4. Run the `Update Keywords` workflow manually or wait for the scheduled run

## Command Line Options

```bash
python src/tools/export_static_site.py --help

Options:
  --output-dir TEXT       Output directory (default: docs)
  --top-keywords INTEGER  Max keywords per venue (default: 300)
```

## Features

- Venue data export (index, top keywords, trends)
- arXiv data export (timeseries, emerging keywords, stats)
- Rank calculation in all exports
- Static asset copying with path transformation
- Automatic mode detection in frontend
- Keyword search with autocomplete
- GitHub Actions integration

## GitHub Actions Integration

The workflow automatically exports the static site after data collection, uploads `docs/` as a Pages artifact, and deploys it with `actions/deploy-pages`.

Workflow inputs:
- `ccf_tier`: Filter by CCF tier (A/B/C/all)
- `export_only`: Skip data collection, only export static site

## Troubleshooting

### Issue: 404 errors when loading JSON files
**Solution**: Ensure paths are relative (`./data/...`) not absolute (`/data/...`)

### Issue: Charts not rendering
**Solution**: Check browser console for errors. Verify JSON files exist in `docs/data/`

## Performance

- Export time: ~10-30 seconds
- Total size: ~5-20 MB
- Load time: <2 seconds on GitHub Pages
