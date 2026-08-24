#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
README Renderer - Generate a clean README.md from the CSV.
Includes full data display: statistics, charts, and interactive filters.
"""

import csv
import datetime
import sys
import os
import re
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple

# ============================================
# Configuration
# ============================================
CSV_PATH = os.getenv('CSV_PATH', 'food-original.csv')
OUT_PATH = os.getenv('README_PATH', 'README.md')
MAX_TOP_RATED = int(os.getenv('MAX_TOP_RATED', '5'))


# ============================================
# Utility Functions
# ============================================

def esc(s: Optional[str]) -> str:
    """Escape Markdown special characters."""
    if s is None:
        return ""
    s = str(s)
    s = s.replace("|", "\\|")
    s = s.replace("\n", " ").replace("\r", "")
    s = s.replace("<", "&lt;").replace(">", "&gt;")
    return s.strip()


def parse_rating(s: Optional[str]) -> float:
    """Parse the rating string to a float."""
    if s is None:
        return 0.0
    try:
        return float(str(s).strip())
    except (ValueError, TypeError):
        return 0.0


def rating_to_stars(rating: Optional[float]) -> str:
    """Render the rating as star icons."""
    if rating is None or rating <= 0:
        return "—"
    full = int(round(rating))
    full = max(0, min(5, full))
    return "★" * full + "☆" * (5 - full)


def get_price_range(price_str: Optional[str]) -> str:
    """Bucket the price into a range."""
    if not price_str:
        return "TBD"
    price_str = str(price_str).strip()
    numbers = re.findall(r'[\d.]+', price_str)
    if not numbers:
        return "TBD"
    nums = [float(n) for n in numbers]
    avg_price = sum(nums) / len(nums)

    if avg_price < 30:
        return "Under ¥30"
    elif avg_price < 60:
        return "¥30-60"
    elif avg_price < 100:
        return "¥60-100"
    else:
        return "Above ¥100"


def is_example_row(row: Dict[str, str]) -> bool:
    """Check if the row is the placeholder example."""
    name = (row.get("name") or "").strip()
    notes = (row.get("notes") or "").strip()
    return "example" in name.lower() or "example" in notes.lower()


def format_hours(hours: Optional[str]) -> str:
    """Format hours by replacing ';' with <br> for multi-line display."""
    if not hours or hours.strip().upper() == 'NULL':
        return ""
    return hours.strip().replace(";", "<br>")


def get_cuisine_stats(rows: List[Dict]) -> List[Tuple[str, int]]:
    """Count restaurants per cuisine."""
    stats = defaultdict(int)
    for r in rows:
        cuisine = (r.get("cuisine") or "").strip()
        if cuisine:
            stats[cuisine] += 1
    return sorted(stats.items(), key=lambda x: x[1], reverse=True)


def get_top_rated(rows: List[Dict], limit: int = 5) -> List[Dict]:
    """Return the highest-rated restaurants."""
    sorted_rows = sorted(
        rows,
        key=lambda r: parse_rating(r.get("rating", "")),
        reverse=True
    )
    return sorted_rows[:limit]


def get_current_beijing_time() -> datetime.datetime:
    """Get the current Beijing time (UTC+8)."""
    try:
        # Python 3.11+
        from datetime import UTC, timezone, timedelta
        return datetime.datetime.now(UTC).astimezone(timezone(timedelta(hours=8)))
    except ImportError:
        try:
            # Python 3.9-3.10
            from datetime import timezone, timedelta
            return datetime.datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
        except ImportError:
            # Fallback
            return datetime.datetime.utcnow() + datetime.timedelta(hours=8)


def generate_progress_bar(percentage: float, width: int = 20) -> str:
    """Generate a visual progress bar."""
    filled = int(percentage / 100 * width)
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def generate_statistics(rows: List[Dict]) -> Dict[str, Any]:
    """Compute summary statistics."""
    total = len(rows)
    ratings = [parse_rating(r.get("rating", "")) for r in rows]
    avg_rating = sum(ratings) / total if total > 0 else 0.0
    cuisine_stats = get_cuisine_stats(rows)

    price_dist = defaultdict(int)
    for r in rows:
        price_range = get_price_range(r.get("price", ""))
        price_dist[price_range] += 1

    top_rated = get_top_rated(rows, MAX_TOP_RATED)

    return {
        'total': total,
        'avg_rating': avg_rating,
        'cuisine_stats': cuisine_stats,
        'price_dist': price_dist,
        'top_rated': top_rated,
        'max_rating': max(ratings) if ratings else 0.0,
        'min_rating': min(ratings) if ratings else 0.0,
    }


# ============================================
# Markdown Generation Functions
# ============================================

def generate_stats_markdown(stats: Dict[str, Any], section_id: str = "data-statistics") -> List[str]:
    lines = []
    lines.append(f'<h2 id="{section_id}">📊 Guide Statistics</h2>\n\n')
    lines.append("| Metric | Value |\n| :--- | ---: |\n")
    lines.append(f"| 📝 Total restaurants | **{stats['total']}** |\n")
    lines.append(f"| ⭐ Average rating | **{stats['avg_rating']:.2f}** / 5.0 |\n")
    if stats['total'] > 0:
        lines.append(f"| 🔼 Highest rating | **{stats['max_rating']:.1f}** / 5.0 |\n")
        lines.append(f"| 🔽 Lowest rating | **{stats['min_rating']:.1f}** / 5.0 |\n")
    lines.append("\n")

    if stats['cuisine_stats']:
        lines.append("### 🍽️ Cuisine Breakdown\n\n| Cuisine | Count | Share |\n| :--- | ---: | ---: |\n")
        for cuisine, count in stats['cuisine_stats']:
            percentage = (count / stats['total'] * 100) if stats['total'] > 0 else 0
            bar = generate_progress_bar(percentage)
            lines.append(f"| {cuisine} | {count} | {percentage:.1f}% {bar} |\n")
        lines.append("\n")

    if any(stats['price_dist'].values()):
        lines.append("### 💰 Price Distribution\n\n| Price Range | Count | Share |\n| :--- | ---: | ---: |\n")
        price_order = ["Under ¥30", "¥30-60", "¥60-100", "Above ¥100", "TBD"]
        for price_range in price_order:
            count = stats['price_dist'].get(price_range, 0)
            if count > 0:
                percentage = (count / stats['total'] * 100) if stats['total'] > 0 else 0
                bar = generate_progress_bar(percentage)
                lines.append(f"| {price_range} | {count} | {percentage:.1f}% {bar} |\n")
        lines.append("\n")

    if stats['top_rated']:
        lines.append(f"### 🏆 Top Rated (Top {MAX_TOP_RATED})\n\n| Rank | Name | Cuisine | Rating | Price |\n| :---: | :--- | :--- | :---: | :--- |\n")
        for idx, r in enumerate(stats['top_rated'], 1):
            name = esc(r.get("name", ""))
            cuisine = esc(r.get("cuisine", ""))
            rating = parse_rating(r.get("rating", ""))
            price = esc(r.get("price", ""))
            stars = rating_to_stars(rating)
            lines.append(f"| {idx} | {name} | {cuisine} | {stars} {rating:.1f} | {price} |\n")
        lines.append("\n")
    return lines


def generate_main_table(rows: List[Dict], section_id: str = "restaurant-list") -> List[str]:
    lines = []
    lines.append(f'<h2 id="{section_id}">📋 Restaurant List</h2>\n\n')
    lines.append("| Name | Cuisine | Price | Rating | Hours |\n| :--- | :--- | :---: | :---: | :--- |\n")
    for r in rows:
        url = (r.get("url") or "").strip()
        name_raw = esc(r.get("name", ""))
        name = f"[{name_raw}]({url})" if url else name_raw
        rating_val = parse_rating(r.get("rating", ""))
        stars = rating_to_stars(rating_val)
        rating_display = f"{stars} {rating_val:.1f}" if rating_val > 0 else "—"
        hours = format_hours(esc(r.get("hours", "")))
        lines.append(f"| {name} | {esc(r.get('cuisine', ''))} | {esc(r.get('price', ''))} | {rating_display} | {hours} |\n")
    return lines


def generate_detail_table(rows: List[Dict], section_id: str = "detailed-info") -> List[str]:
    lines = []
    lines.append(f'<h2 id="{section_id}">📖 Detailed Information</h2>\n\n')
    lines.append("<details>\n<summary>📖 Click to expand details (notes / recommended dishes)</summary>\n\n")
    lines.append("| Name | Notes / Recommended Dishes |\n| :--- | :--- |\n")
    for r in rows:
        url = (r.get("url") or "").strip()
        name_raw = esc(r.get("name", ""))
        name = f"[{name_raw}]({url})" if url else name_raw
        notes = esc(r.get("notes", "")) or "—"
        lines.append(f"| {name} | {notes} |\n")
    lines.append("\n</details>\n\n")
    return lines


def generate_search_guide(section_id: str = "how-to-use") -> List[str]:
    lines = []
    lines.append(f'<h2 id="{section_id}">🔍 How to Use</h2>\n\n')
    lines.append("### Method 1: Browse Directly\n1. Browse the restaurant list below\n2. Click a restaurant name to open its Amap page\n3. Click 📖 to expand details\n\n")
    lines.append("### Method 2: Database Query\nFor complex queries, import the generated SQL file:\n\n```bash\nmysql -u root -p < food.sql\n```\n\n")
    lines.append("### Method 3: Keyword Search\nUse `Ctrl+F` (or `Cmd+F`) in your browser to search keywords (e.g., \"grilled\", \"hot pot\", \"Xiang cuisine\")\n\n")
    return lines


def generate_legend(section_id: str = "legend") -> List[str]:
    lines = []
    lines.append("\n---\n\n")
    lines.append(f'<h2 id="{section_id}">📌 Legend</h2>\n\n')
    lines.append("| Icon | Meaning |\n| :---: | --- |\n")
    lines.append("| ★★★★★ | Recommendation strength (more stars = stronger) |\n| 📖 | Expand details |\n| 📊 | Guide statistics |\n| 🏆 | Top rated |\n")
    return lines


def generate_footer(section_id: str = "contribution") -> List[str]:
    lines = []
    lines.append("\n---\n\n")
    lines.append(f'<h2 id="{section_id}">📝 Contribution Guide</h2>\n\n')
    lines.append("1. Fork this repository\n2. Edit `food-original.csv`\n3. Run `python readme_render.py` to update README\n4. Run `python export_to_sql.py` to update the SQL file\n5. Submit a Pull Request\n\n")
    lines.append("### CSV Format\n\n| Field | Meaning | Example |\n| :--- | :--- | :--- |\n")
    lines.append("| name | Restaurant name | Yaba Shengjian (Linton Road) |\n| cuisine | Cuisine type | Suzhou cuisine |\n| price | Average price | ¥28/person |\n| rating | Score (0-5) | 4.7 |\n| url | Amap link | https://surl.amap.com/xxx |\n| hours | Opening hours | 6:30-19:30 |\n| notes | Notes / recommended dishes | Fried buns, beef soup |\n")
    return lines


def read_csv_data(csv_path: str) -> List[Dict]:
    rows = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not is_example_row(row):
                    rows.append(row)
    except FileNotFoundError:
        print(f"❌ Error: {csv_path} not found", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error reading CSV: {e}", file=sys.stderr)
        sys.exit(1)
    return rows


# ============================================
# Main Entry Point
# ============================================

def main():
    print("=" * 60)
    print("📝 README Generator")
    print("=" * 60)
    print(f"📂 CSV file: {CSV_PATH}")
    print(f"📄 README output: {OUT_PATH}")
    print("=" * 60)

    rows = read_csv_data(CSV_PATH)
    if not rows:
        print("⚠️ Warning: No valid data (maybe only the example row)")

    # Sort by rating descending
    rows.sort(key=lambda r: parse_rating(r.get("rating", "")), reverse=True)
    print(f"✅ Successfully read: {len(rows)} valid records")

    stats = generate_statistics(rows)
    lines = []

    # 1. Title and header
    lines.append("# 🍜 Johor Food Guide\n\n")
    lines.append("> 📋 This file is auto-generated by `readme_render.py` from `food-original.csv`\n\n")
    lines.append("> ✏️ To add or edit a restaurant, update `food-original.csv` and submit a Pull Request\n\n")

    beijing_time = get_current_beijing_time()
    lines.append(f"📊 **{len(rows)}** restaurants in the guide ｜ 🕒 Updated at Beijing time: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')} CST\n\n")

    # 2. Table of contents
    lines.append("## 📑 Table of Contents\n\n")
    lines.append("- [📊 Guide Statistics](#data-statistics)\n")
    lines.append("- [📋 Restaurant List](#restaurant-list)\n")
    lines.append("- [📖 Detailed Information](#detailed-info)\n")
    lines.append("- [🔍 How to Use](#how-to-use)\n")
    lines.append("- [📌 Legend](#legend)\n")
    lines.append("- [📝 Contribution Guide](#contribution)\n\n")

    # 3. Assemble sections
    lines.extend(generate_stats_markdown(stats))
    lines.extend(generate_main_table(rows))
    lines.extend(generate_detail_table(rows))
    lines.extend(generate_search_guide())
    lines.extend(generate_legend())
    lines.extend(generate_footer())

    # 4. Write the file
    try:
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"✅ README generated successfully: {OUT_PATH} ({len(rows)} records)")
    except Exception as e:
        print(f"❌ Error writing README: {e}", file=sys.stderr)
        sys.exit(1)

    # 5. Console summary
    print("=" * 60)
    print("\n📊 Summary:")
    print(f"  - Total restaurants: {stats['total']}")
    print(f"  - Average rating: {stats['avg_rating']:.2f}")
    print(f"  - Highest rating: {stats['max_rating']:.1f}")
    print(f"  - Lowest rating: {stats['min_rating']:.1f}")
    print(f"  - Cuisine types: {len(stats['cuisine_stats'])}")

    if stats['cuisine_stats']:
        print("\n  🍽️ Cuisine breakdown (Top 5):")
        for cuisine, count in stats['cuisine_stats'][:5]:
            print(f"    - {cuisine}: {count}")
        if len(stats['cuisine_stats']) > 5:
            print(f"    ... and {len(stats['cuisine_stats']) - 5} more")

    print("\n💡 Tip: Run `python export_to_sql.py` to generate the database install script")


if __name__ == "__main__":
    main()