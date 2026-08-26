#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV to SQL Converter - Generates full MySQL database installation scripts
Reads CSV files and generates complete SQL scripts including database creation, table structure, and data import.
"""

import csv
import os
import sys
from datetime import datetime

# ============================================
# Configuration Parameters
# ============================================
CSV_PATH = os.getenv('CSV_PATH', 'food-original.csv')
SQL_PATH = os.getenv('SQL_PATH', 'data/food.sql')
DATABASE_NAME = os.getenv('DATABASE_NAME', 'johor_food_db')
TABLE_NAME = os.getenv('TABLE_NAME', 'johor_food')


# ============================================
# Core Functions
# ============================================

def escape_sql_value(val):
    """Escape SQL string values"""
    if val is None or str(val).strip() == '' or str(val).strip().upper() == 'NULL':
        return 'NULL'
    val = str(val)
    # Handle special characters
    escaped = val.replace('\\', '\\\\').replace("'", "''")
    return f"'{escaped}'"


def detect_column_type(column_name, sample_values):
    """
    Infer appropriate MySQL data type based on column name and sample data
    """
    # Infer by column name
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
    else:
        # Infer by sample data
        max_len = 0
        has_null = False
        for val in sample_values:
            if val is None or str(val).strip() == '':
                has_null = True
                continue
            max_len = max(max_len, len(str(val)))

        if max_len > 500:
            return 'TEXT DEFAULT NULL'
        elif max_len > 200:
            return f'VARCHAR({min(max_len + 50, 1000)}) DEFAULT NULL'
        else:
            return f'VARCHAR({max(50, min(max_len + 20, 255))}) DEFAULT NULL'


def generate_create_table_sql(fields, rows):
    """Generate CREATE TABLE statement"""
    lines = []
    lines.append(f"CREATE TABLE `{TABLE_NAME}` (")

    # Add field definitions
    field_defs = []

    # Primary key field
    field_defs.append("    -- Primary Key")
    field_defs.append("    `id` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'Primary Key ID'")
    field_defs.append("")
    field_defs.append("    -- Basic Information")

    # Data fields
    for field in fields:
        sample_values = [row.get(field, '') for row in rows[:100]]  # Use first 100 rows as sample
        col_type = detect_column_type(field, sample_values)
        comment = field.replace('_', ' ').title()

        # Add comments for special fields
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

        field_defs.append(f"    `{field}` {col_type} COMMENT '{comment}'")

    # System fields
    field_defs.append("")
    field_defs.append("    -- System Fields")
    field_defs.append("    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Created At'")
    field_defs.append(
        "    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated At'")

    # Primary key and indexes
    field_defs.append("")
    field_defs.append("    -- Indexes")
    field_defs.append("    PRIMARY KEY (`id`)")
    field_defs.append("    INDEX `idx_name` (`name`)")
    field_defs.append("    INDEX `idx_cuisine` (`cuisine`)")
    field_defs.append("    INDEX `idx_rating` (`rating`)")

    lines.append(",\n".join(field_defs))
    lines.append(f") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Johor Food Recommendations Table'")

    return "\n".join(lines)


def generate_insert_sql(rows, fields):
    """Generate INSERT statements (batch insert)"""
    if not rows:
        return "-- No data to insert"

    lines = []
    lines.append("BEGIN;")
    lines.append("")

    # Batch insert to improve efficiency (50 records per batch)
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

        # ✅ 修复：将包含 \n 的 join 操作提取到 f-string 外部作为变量
        fields_joined = ', '.join(fields_quoted)
        values_joined = ',\n    '.join(values_list)
        sql = f"INSERT INTO `{TABLE_NAME}` ({fields_joined}) VALUES\n    {values_joined};"
        lines.append(sql)
        lines.append("")

    lines.append("COMMIT;")
    return "\n".join(lines)


def generate_validation_queries():
    """Generate data validation queries"""
    return """
-- ============================================
-- 5. Data Validation Queries (Optional)
-- ============================================

-- Check total imported records
SELECT COUNT(*) AS total_records FROM `{TABLE_NAME}`;

-- Statistics by cuisine
SELECT 
    `cuisine`,
    COUNT(*) AS count,
    ROUND(AVG(`rating`), 2) AS avg_rating
FROM `{TABLE_NAME}`
WHERE `cuisine` IS NOT NULL
GROUP BY `cuisine`
ORDER BY count DESC;

-- High-rated recommendations (4.8+)
SELECT `name`, `cuisine`, `rating`, `price`, `notes`
FROM `{TABLE_NAME}`
WHERE `rating` >= 4.8
ORDER BY `rating` DESC;

-- Group by price range
SELECT 
    CASE 
        WHEN `price` REGEXP '^¥[0-9]+$' AND CAST(REPLACE(`price`, '¥', '') AS UNSIGNED) < 30 THEN 'Under ¥30'
        WHEN `price` REGEXP '^¥[0-9]+$' AND CAST(REPLACE(`price`, '¥', '') AS UNSIGNED) BETWEEN 30 AND 60 THEN '¥30-60'
        WHEN `price` REGEXP '^¥[0-9]+$' AND CAST(REPLACE(`price`, '¥', '') AS UNSIGNED) BETWEEN 60 AND 100 THEN '¥60-100'
        WHEN `price` REGEXP '^¥[0-9]+$' AND CAST(REPLACE(`price`, '¥', '') AS UNSIGNED) > 100 THEN 'Above ¥100'
        ELSE 'TBD'
    END AS price_range,
    COUNT(*) AS count
FROM `{TABLE_NAME}`
GROUP BY price_range
ORDER BY price_range;
""".format(TABLE_NAME=TABLE_NAME)


def generate_views():
    """Generate common views"""
    return """
-- ============================================
-- 6. Create Views (For frequent queries)
-- ============================================

-- Create high-rated food view
CREATE OR REPLACE VIEW `v_high_rating_food` AS
SELECT 
    `id`, `name`, `cuisine`, `price`, `rating`, `notes`
FROM `{TABLE_NAME}`
WHERE `rating` >= 4.5
ORDER BY `rating` DESC;

-- Create cuisine stats view
CREATE OR REPLACE VIEW `v_cuisine_stats` AS
SELECT 
    `cuisine`,
    COUNT(*) AS total_count,
    ROUND(AVG(`rating`), 2) AS avg_rating,
    MAX(`rating`) AS max_rating,
    MIN(`rating`) AS min_rating
FROM `{TABLE_NAME}`
WHERE `cuisine` IS NOT NULL
GROUP BY `cuisine`
ORDER BY total_count DESC;
""".format(TABLE_NAME=TABLE_NAME)


def generate_stored_procedures():
    """Generate stored procedures"""
    return """
-- ============================================
-- 7. Create Stored Procedures (For easy data management)
-- ============================================

DELIMITER //

-- Query food by rating range
CREATE PROCEDURE `sp_get_food_by_rating`(
    IN min_rating DECIMAL(3,2),
    IN max_rating DECIMAL(3,2)
)
BEGIN
    SELECT `name`, `cuisine`, `price`, `rating`, `notes`
    FROM `{TABLE_NAME}`
    WHERE `rating` BETWEEN min_rating AND max_rating
    ORDER BY `rating` DESC;
END //

-- Query food by cuisine
CREATE PROCEDURE `sp_get_food_by_cuisine`(
    IN cuisine_name VARCHAR(50)
)
BEGIN
    SELECT `name`, `price`, `rating`, `notes`
    FROM `{TABLE_NAME}`
    WHERE `cuisine` = cuisine_name
    ORDER BY `rating` DESC;
END //

-- Search food (fuzzy search on name and notes)
CREATE PROCEDURE `sp_search_food`(
    IN keyword VARCHAR(100)
)
BEGIN
    SELECT `name`, `cuisine`, `price`, `rating`, `notes`
    FROM `{TABLE_NAME}`
    WHERE `name` LIKE CONCAT('%', keyword, '%')
       OR `notes` LIKE CONCAT('%', keyword, '%')
    ORDER BY `rating` DESC;
END //

DELIMITER ;
""".format(TABLE_NAME=TABLE_NAME)


def generate_completion_message():
    """Generate installation completion message"""
    return """
-- ============================================
-- Installation Complete
-- ============================================
SELECT '✅ Johor Food Database Installation Completed!' AS status;
SELECT '📊 Instructions:' AS info;
SELECT '  - View all data: SELECT * FROM {TABLE_NAME};' AS tips;
SELECT '  - View top-rated food: SELECT * FROM v_high_rating_food;' AS tips;
SELECT '  - View stats by cuisine: SELECT * FROM v_cuisine_stats;' AS tips;
SELECT '  - Query by rating range: CALL sp_get_food_by_rating(4.5, 5.0);' AS tips;
SELECT '  - Query by cuisine: CALL sp_get_food_by_cuisine(''Hunan'');' AS tips;
SELECT '  - Search food: CALL sp_search_food(''Beef'');' AS tips;
""".format(TABLE_NAME=TABLE_NAME)


def read_csv(csv_path):
    """Read CSV file"""
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


def write_sql(sql_path, fields, rows, total_count):
    """Generate complete SQL script"""
    # Ensure output directory exists
    os.makedirs(os.path.dirname(sql_path) or '.', exist_ok=True)

    with open(sql_path, 'w', encoding='utf-8') as sqlfile:
        # Header
        sqlfile.write("-- ============================================\n")
        sqlfile.write("-- Johor Food Database - Complete Installation Script\n")
        sqlfile.write(f"-- Generated by: {os.path.basename(__file__)}\n")
        sqlfile.write(f"-- Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        sqlfile.write(f"-- Total records: {total_count}\n")
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

        # 2. Drop Existing Table
        sqlfile.write("-- ============================================\n")
        sqlfile.write("-- 2. Drop Existing Table (Proceed with caution; comment out to keep existing data)\n")
        sqlfile.write("-- ============================================\n")
        sqlfile.write(f"DROP TABLE IF EXISTS `{TABLE_NAME}`;\n\n")

        # 3. Create Table
        sqlfile.write("-- ============================================\n")
        sqlfile.write("-- 3. Create Table Structure\n")
        sqlfile.write("-- ============================================\n")
        sqlfile.write(generate_create_table_sql(fields, rows))
        sqlfile.write("\n\n")

        # 4. Import Data
        sqlfile.write("-- ============================================\n")
        sqlfile.write("-- 4. Import Data\n")
        sqlfile.write("-- ============================================\n")
        sqlfile.write(generate_insert_sql(rows, fields))
        sqlfile.write("\n\n")

        # 5. Validation Queries
        sqlfile.write(generate_validation_queries())
        sqlfile.write("\n\n")

        # 6. Views
        sqlfile.write(generate_views())
        sqlfile.write("\n\n")

        # 7. Stored Procedures
        sqlfile.write(generate_stored_procedures())
        sqlfile.write("\n\n")

        # 8. Completion Message
        sqlfile.write(generate_completion_message())


def main():
    """Main Function"""
    print("=" * 60)
    print("🚀 Johor Food Database - SQL Generator Tool")
    print("=" * 60)
    print(f"📂 CSV File: {CSV_PATH}")
    print(f"📄 SQL File: {SQL_PATH}")
    print(f"🗄️  Database Name: {DATABASE_NAME}")
    print(f"📋 Table Name: {TABLE_NAME}")
    print("=" * 60)

    # Read CSV
    fields, rows = read_csv(CSV_PATH)

    # Filter out sample rows
    rows = [r for r in rows if not ("Sample" in (r.get('name') or '') or "Sample" in (r.get('notes') or ''))]

    if not rows:
        print("⚠️ Warning: CSV file is empty or contains only sample rows")

    total_count = len(rows)
    print(f"✅ Successfully read: {total_count} records, {len(fields)} fields")
    print(f"📋 Fields: {', '.join(fields)}")

    # Generate SQL
    write_sql(SQL_PATH, fields, rows, total_count)

    print(f"✅ SQL generated successfully: {SQL_PATH}")
    print(f"📊 Total records: {total_count}")
    print("=" * 60)
    print("💡 How to use:")
    print(f"   mysql -u root -p < {SQL_PATH}")
    print("   Or run inside MySQL client: source " + SQL_PATH)
    print("=" * 60)


if __name__ == "__main__":
    main()
