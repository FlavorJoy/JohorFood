# Contribution Guide - Add/Update Food Entries

Welcome to contribute to the Johor food recommendations! Follow these steps to submit restaurant info:

1. Open `food-original.csv` in the repo root.
2. Add a row at the end, fields in order:
   name,cuisine,price,rating,url,hours,contact,reservation_needed,queue_time,tags,notes
3. Fill in an example:
   Example Restaurant,Local Johor Cuisine,¥50-100,4.5,https://example.com,Mon-Sun 11:00-21:00,0512-12345678,No,10-20 min,Budget eats,Example note
4. Open a new branch and create a PR.
5. After the PR is merged into the default branch (main/master), GitHub Actions will automatically run `readme_render.py` and commit the generated `README.md`.

> **Additional Note**: After the PR is merged, the automation script `export_to_sql.py` will also run, converting `food-original.csv` into `data/food.sql`. This SQL file contains INSERT statements for the `johor_food` table, which can be used directly to create a database or for backup.

This repo uses CSV as the single source of truth; README and SQL are auto-generated artifacts. Please ensure that the CSV field order and column names are not changed.