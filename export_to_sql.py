#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV to SQL Converter - Generates full MySQL database installation scripts
Reads CSV files and generates:
  - One master table with all data
  - Separate tables per distinct area (based on 'area' column)
"""

import csv
import os
import sys
import re
from datetime import datetime
from collections import defaultdict

# ============================================
# Configuration Parameters
# ============================================
CSV_PATH = os.getenv('CSV_PATH', 'food-original.csv')
SQL_PATH = os.getenv('SQL_PATH', 'data/food.sql')
DATABASE_NAME = os.getenv('DATABASE_NAME', 'malaysia_food_db')
BASE_TABLE_NAME = os.getenv('BASE_TABLE_NAME', 'malaysia_food')  # Master table name
AREA_SEPARATOR = '_'  # Separator between base name and area suffix

# Keywords to ignore during generation (case-insensitive)
IGNORE_KEYWORDS = ['example', 'eaxample', 'sample', '示例', 'Example', 'Example Restaurant']

# ============================================
# Helper Functions
# ============================================

def escape_sql_value(val):
    """Escape SQL string values"""
    if val is None or str(val).strip() == '' or str(val).strip().upper() == 'NULL':
        return 'NULL'
    val = str(val)
    escaped = val.replace('\\', '\\\\').replace("'", "''")
    return f"'{escaped}'"

def sanitize_table_name(name):
    """Convert area name to a valid MySQL table name suffix"""
    # Lowercase, replace spaces and special chars with underscore, remove invalid chars
    name = str(name).strip().lower()
    name = re.sub(r'[^a-z0-9_]+', '_', name)
    name = re.sub(r'_+', '_', name)  # collapse multiple underscores
    name = name.strip('_')
    if not name:
        name = 'unknown'
    return name

def detect_column_type(column_name, sample_values):
    """Infer MySQL data type based on column name and sample data"""
    if column_name == 'id':
        return 'INT UNSIGNED NOT NULL AUTO_INCREMENT'
    elif column_name in ['rating']:
        return 'DECIMAL(3,2) DEFAULT NULL'
    elif column_name in ['name']:
        return 'VARCHAR(100) NOT NULL'
    elif column_name in ['cuisine']:
        return 'VARCHAR(50) DEFAULT NULL'
    elif column_name in ['price']:
        return 'VARCHAR(50) DEFAULT NULL'
    elif column_name in ['url']:
        return 'VARCHAR(500) DEFAULT NULL'
    elif column_name in ['hours']:
        return 'VARCHAR(200) DEFAULT NULL'
    elif column_name in ['notes']:
        return 'TEXT DEFAULT NULL'
    elif column_name in ['created_at', 'updated_at']:
        return 'TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP'
    elif column_name in ['area']:
        return 'VARCHAR(50) DEFAULT NULL'
    else:
        max_len = 0
        for val in sample_values:
            if val is None or str(val).strip() == '':
                continue
            max_len = max(max_len, len(str(val)))
        if max_len > 500:
            return 'TEXT DEFAULT NULL'
        elif max_len > 200:
            return f'VARCHAR({min(max_len + 50, 1000)}) DEFAULT NULL'
        else:
            return f'VARCHAR({max(50, min(max_len + 20, 255))}) DEFAULT NULL'

def generate_create_table_sql(table_name, fields, rows):
    """Generate CREATE TABLE statement for a specific table"""
    lines = []
    lines.append(f"CREATE TABLE `{table_name}` (")

    field_defs = []
    field_defs.append("    -- Primary Key")
    field_defs.append("    `id` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'Primary Key ID'")
    field_defs.append("")
    field_defs.append("    -- Basic Information")

    for field in fields:
        sample_values = [row.get(field, '') for row in rows[:100]]
        col_type = detect_column_type(field, sample_values)
        comment = field.replace('_', ' ').title()
        if field == 'name':
            comment = 'Restaurant/Food Name'
        elif field == 'cuisine':
            comment = 'Cuisine/Flavor Category'
        elif field == 'price':
            comment = 'Price Range or Avg Spending'
        elif field == 'rating':
            comment = 'Rating (Out of 5.0)'
        elif field == 'url':
            comment = 'Amap / Map Link'
        elif field == 'hours':
            comment = 'Business Hours'
        elif field == 'notes':
            comment = 'Recommended Dishes / Notes'
        elif field == 'area':
            comment = 'Geographic Area'

        field_defs.append(f"    `{field}` {col_type} COMMENT '{comment}'")

    field_defs.append("")
    field_defs.append("    -- System Fields")
    field_defs.append("    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Created At'")
    field_defs.append(
        "    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated At'")

    field_defs.append("")
    field_defs.append("    -- Indexes")
    field_defs.append("    PRIMARY KEY (`id`)")
    field_defs.append("    INDEX `idx_name` (`name`)")
    field_defs.append("    INDEX `idx_cuisine` (`cuisine`)")
    field_defs.append("    INDEX `idx_rating` (`rating`)")
    if 'area' in fields:
        field_defs.append("    INDEX `idx_area` (`area`)")

    lines.append(",\n".join(field_defs))
    lines.append(f") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='{table_name} Table'")

    return "\n".join(lines)

def generate_insert_sql(table_name, rows, fields):
    """Generate INSERT statements for a specific table"""
    if not rows:
        return "-- No data to insert"

    lines = []
    lines.append("BEGIN;")
    lines.append("")

    batch_size = 50
    fields_quoted = [f'`{f}`' for f in fields]

    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        values_list = []
        for row in batch:
            values = []
            for f in fields:
                val = row.get(f, '')
                values.append(escape_sql_value(val))
            values_list.append(f"({', '.join(values)})")

        fields_joined = ', '.join(fields_quoted)
        values_joined = ',\n    '.join(values_list)
        sql = f"INSERT INTO `{table_name}` ({fields_joined}) VALUES\n    {values_joined};"
        lines.append(sql)
        lines.append("")

    lines.append("COMMIT;")
    return "\n".join(lines)

def generate_validation_queries(table_name):
    """Generate validation queries (only for master table)"""
    return f"""
-- ============================================
-- 5. Data Validation Queries (Master Table)
-- ============================================

-- Check total imported records
SELECT COUNT(*) AS total_records FROM `{table_name}`;

-- Statistics by cuisine
SELECT 
    `cuisine`,
    COUNT(*) AS count,
    ROUND(AVG(`rating`), 2) AS avg_rating
FROM `{table_name}`
WHERE `cuisine` IS NOT NULL
GROUP BY `cuisine`
ORDER BY count DESC;

-- High-rated recommendations (4.8+)
SELECT `name`, `cuisine`, `rating`, `price`, `notes`
FROM `{table_name}`
WHERE `rating` >= 4.8
ORDER BY `rating` DESC;

-- Group by price range
SELECT 
    CASE 
        WHEN `price` REGEXP '^[¥RM]+[0-9]+$' THEN 'Budget'
        WHEN `price` REGEXP '^[¥RM]+[0-9]-[0-9]+$' THEN 'Mid-range'
        ELSE 'TBD'
    END AS price_range,
    COUNT(*) AS count
FROM `{table_name}`
GROUP BY price_range
ORDER BY price_range;

-- Statistics by area
SELECT `area`, COUNT(*) AS count
FROM `{table_name}`
WHERE `area` IS NOT NULL
GROUP BY `area`
ORDER BY count DESC;
"""

def generate_views(table_name):
    """Generate views (only for master table)"""
    return f"""
-- ============================================
-- 6. Create Views (Master Table)
-- ============================================

-- High-rated food view
CREATE OR REPLACE VIEW `v_high_rating_food` AS
SELECT 
    `id`, `name`, `cuisine`, `price`, `rating`, `notes`, `area`
FROM `{table_name}`
WHERE `rating` >= 4.5
ORDER BY `rating` DESC;

-- Cuisine stats view
CREATE OR REPLACE VIEW `v_cuisine_stats` AS
SELECT 
    `cuisine`,
    COUNT(*) AS total_count,
    ROUND(AVG(`rating`), 2) AS avg_rating,
    MAX(`rating`) AS max_rating,
    MIN(`rating`) AS min_rating
FROM `{table_name}`
WHERE `cuisine` IS NOT NULL
GROUP BY `cuisine`
ORDER BY total_count DESC;
"""

def generate_stored_procedures(table_name):
    """Generate stored procedures (only for master table)"""
    return f"""
-- ============================================
-- 7. Create Stored Procedures (Master Table)
-- ============================================

DELIMITER //

-- Query by rating range
CREATE PROCEDURE `sp_get_food_by_rating`(
    IN min_rating DECIMAL(3,2),
    IN max_rating DECIMAL(3,2)
)
BEGIN
    SELECT `name`, `cuisine`, `price`, `rating`, `notes`, `area`
    FROM `{table_name}`
    WHERE `rating` BETWEEN min_rating AND max_rating
    ORDER BY `rating` DESC;
END //

-- Query by cuisine
CREATE PROCEDURE `sp_get_food_by_cuisine`(
    IN cuisine_name VARCHAR(50)
)
BEGIN
    SELECT `name`, `price`, `rating`, `notes`, `area`
    FROM `{table_name}`
    WHERE `cuisine` = cuisine_name
    ORDER BY `rating` DESC;
END //

-- Search food (fuzzy)
CREATE PROCEDURE `sp_search_food`(
    IN keyword VARCHAR(100)
)
BEGIN
    SELECT `name`, `cuisine`, `price`, `rating`, `notes`, `area`
    FROM `{table_name}`
    WHERE `name` LIKE CONCAT('%', keyword, '%')
       OR `notes` LIKE CONCAT('%', keyword, '%')
    ORDER BY `rating` DESC;
END //

DELIMITER ;
"""

def generate_completion_message(master_table, area_tables):
    """Generate installation completion message"""
    area_list = ', '.join([f'`{t}`' for t in area_tables]) if area_tables else 'none'
    return f"""
-- ============================================
-- Installation Complete
-- ============================================
SELECT '✅ Malaysia Food Database Installation Completed!' AS status;
SELECT '📊 Instructions:' AS info;
SELECT '  - Master table: {master_table} (all data)' AS tips;
SELECT '  - Area tables: {area_list}' AS tips;
SELECT '  - View all data: SELECT * FROM {master_table};' AS tips;
SELECT '  - View top-rated: SELECT * FROM v_high_rating_food;' AS tips;
SELECT '  - Stats by cuisine: SELECT * FROM v_cuisine_stats;' AS tips;
SELECT '  - Query by rating: CALL sp_get_food_by_rating(4.5, 5.0);' AS tips;
SELECT '  - Query by cuisine: CALL sp_get_food_by_cuisine(''BBQ'');' AS tips;
SELECT '  - Search food: CALL sp_search_food(''Kimchi'');' AS tips;
"""

def read_csv(csv_path):
    """Read CSV file and return fields and rows"""
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            fields = reader.fieldnames
            if not fields:
                print("❌ CSV file has no headers", file=sys.stderr)
                sys.exit(1)
            rows = list(reader)
            return fields, rows
    except FileNotFoundError:
        print(f"❌ CSV file does not exist: {csv_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error reading CSV file: {e}", file=sys.stderr)
        sys.exit(1)

def write_sql(sql_path, fields, all_rows, master_table):
    """Generate complete SQL script with master and area tables"""
    os.makedirs(os.path.dirname(sql_path) or '.', exist_ok=True)

    # Check if 'area' column exists
    has_area = 'area' in fields
    if not has_area:
        print("⚠️ Warning: No 'area' column found. Only master table will be generated.")

    # Group rows by area (if area exists and not empty)
    area_groups = defaultdict(list)
    if has_area:
        for row in all_rows:
            area_val = row.get('area', '').strip()
            if area_val:
                area_groups[area_val].append(row)
            else:
                area_groups['unknown'].append(row)  # group empty as 'unknown'
    else:
        area_groups['all'] = all_rows  # dummy

    # Prepare table names
    # Master table uses BASE_TABLE_NAME
    master_table_name = master_table
    # Area tables: base + separator + sanitized area
    area_table_names = {}
    for area_name in area_groups.keys():
        if area_name == 'all':
            continue  # skip if no area
        safe_suffix = sanitize_table_name(area_name)
        table_name = f"{master_table_name}{AREA_SEPARATOR}{safe_suffix}"
        area_table_names[area_name] = table_name

    # Start writing SQL
    with open(sql_path, 'w', encoding='utf-8') as sqlfile:
        # Header
        sqlfile.write("-- ============================================\n")
        sqlfile.write("-- Malaysia Food Database - Complete Installation Script\n")
        sqlfile.write(f"-- Generated by: {os.path.basename(__file__)}\n")
        sqlfile.write(f"-- Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        sqlfile.write(f"-- Total valid records: {len(all_rows)}\n")
        sqlfile.write(f"-- Database: {DATABASE_NAME}\n")
        sqlfile.write("-- ============================================\n\n")

        # 1. Create Database
        sqlfile.write("-- ============================================\n")
        sqlfile.write("-- 1. Create Database (If Not Exists)\n")
        sqlfile.write("-- ============================================\n")
        sqlfile.write(f"CREATE DATABASE IF NOT EXISTS `{DATABASE_NAME}` \n")
        sqlfile.write("    CHARACTER SET utf8mb4 \n")
        sqlfile.write("    COLLATE utf8mb4_unicode_ci;\n\n")
        sqlfile.write(f"USE `{DATABASE_NAME}`;\n\n")

        # 2. Drop existing tables (master + area)
        sqlfile.write("-- ============================================\n")
        sqlfile.write("-- 2. Drop Existing Tables (if any)\n")
        sqlfile.write("-- ============================================\n")
        sqlfile.write(f"DROP TABLE IF EXISTS `{master_table_name}`;\n")
        for tbl in area_table_names.values():
            sqlfile.write(f"DROP TABLE IF EXISTS `{tbl}`;\n")
        sqlfile.write("\n")

        # 3. Create and populate master table
        sqlfile.write("-- ============================================\n")
        sqlfile.write("-- 3. Master Table (All Data)\n")
        sqlfile.write("-- ============================================\n")
        sqlfile.write(generate_create_table_sql(master_table_name, fields, all_rows))
        sqlfile.write("\n\n")
        sqlfile.write(generate_insert_sql(master_table_name, all_rows, fields))
        sqlfile.write("\n\n")

        # 4. Create and populate area tables
        if has_area and len(area_groups) > 1:  # at least one area group besides maybe 'unknown'
            sqlfile.write("-- ============================================\n")
            sqlfile.write("-- 4. Area-Specific Tables\n")
            sqlfile.write("-- ============================================\n")
            for area_name, rows in area_groups.items():
                if not rows:
                    continue
                tbl = area_table_names.get(area_name)
                if not tbl:
                    continue
                sqlfile.write(f"-- Table for area: {area_name}\n")
                sqlfile.write(generate_create_table_sql(tbl, fields, rows))
                sqlfile.write("\n\n")
                sqlfile.write(generate_insert_sql(tbl, rows, fields))
                sqlfile.write("\n\n")

        # 5. Validation Queries (for master only)
        sqlfile.write(generate_validation_queries(master_table_name))
        sqlfile.write("\n\n")

        # 6. Views (for master only)
        sqlfile.write(generate_views(master_table_name))
        sqlfile.write("\n\n")

        # 7. Stored Procedures (for master only)
        sqlfile.write(generate_stored_procedures(master_table_name))
        sqlfile.write("\n\n")

        # 8. Completion Message
        sqlfile.write(generate_completion_message(master_table_name, list(area_table_names.values())))

def main():
    print("=" * 60)
    print("🚀 Malaysia Food Database - SQL Generator (with Area Partitioning)")
    print("=" * 60)
    print(f"📂 CSV File: {CSV_PATH}")
    print(f"📄 SQL File: {SQL_PATH}")
    print(f"🗄️  Database Name: {DATABASE_NAME}")
    print(f"📋 Master Table: {BASE_TABLE_NAME}")
    print("=" * 60)

    # Read CSV
    fields, rows = read_csv(CSV_PATH)

    # Filter out example/sample rows
    filtered_rows = []
    for r in rows:
        name = str(r.get('name') or '').lower()
        notes = str(r.get('notes') or '').lower()
        is_example = any(kw.lower() in name or kw.lower() in notes for kw in IGNORE_KEYWORDS)
        if not is_example:
            filtered_rows.append(r)
    rows = filtered_rows

    if not rows:
        print("⚠️ Warning: CSV file is empty or contains only example/sample rows")

    total_count = len(rows)
    print(f"✅ Successfully read: {total_count} valid records, {len(fields)} fields")
    print(f"📋 Fields: {', '.join(fields)}")

    # Generate SQL
    write_sql(SQL_PATH, fields, rows, BASE_TABLE_NAME)

    print(f"✅ SQL generated successfully: {SQL_PATH}")
    print(f"📊 Total valid records: {total_count}")

    # Count areas
    if 'area' in fields:
        areas = set()
        for r in rows:
            a = r.get('area', '').strip()
            if a:
                areas.add(a)
        print(f"📌 Distinct areas found: {len(areas)} - {', '.join(sorted(areas))}")
    else:
        print("📌 No 'area' column; only master table generated.")

    print("=" * 60)
    print("💡 How to use:")
    print(f"   mysql -u root -p < {SQL_PATH}")
    print("   Or run inside MySQL client: source " + SQL_PATH)
    print("=" * 60)

if __name__ == "__main__":
    main()