# DataPulse Data Processing

## Supported File Formats

| Format | Extension | Notes |
|---|---|---|
| CSV | `.csv` | Primary format; most thoroughly tested |
| JSON | `.json` | Records array only: `[{...}, {...}]` |

Only the file extension is used for format dispatch — MIME types supplied by the client are not trusted.

---

## File Handling

### Upload flow

1. Client sends multipart/form-data with `file`, `name`, and optional `description`
2. FastAPI reads the entire file into memory (bounded by `MAX_UPLOAD_SIZE_BYTES`)
3. Extension is validated (`.csv` or `.json` only)
4. Raw bytes are saved to `UPLOAD_DIR/{user_id}/{dataset_id}/{safe_filename}`
5. File is parsed and column metadata is written to the database
6. Dataset status is updated to `ready` or `failed`

### Filename sanitization

`_safe_filename()` takes only the basename of the provided filename, strips leading dots, and replaces non-alphanumeric characters (except `-`, `.`, and space) with `_`. The result is truncated to 200 characters. This prevents path traversal and filesystem injection.

### Storage paths

Storage paths are stored as relative paths within `UPLOAD_DIR`. On every read or delete, the path is resolved and verified to remain inside `UPLOAD_DIR`. Any path that resolves outside is rejected.

---

## Encoding Detection

CSV files are decoded in the following order:
1. `utf-8-sig` (UTF-8 with BOM — common from Excel)
2. `utf-8`
3. `latin-1`

If all three fail, the file is decoded with `utf-8` using `errors="replace"` (replacement character `U+FFFD`). A warning is added to `ParseResult.warnings`.

---

## Column Type Inference

Types are inferred per column after initial string read:

| Type | Condition |
|---|---|
| `boolean` | pandas `bool` dtype |
| `integer` | pandas integer dtype, or ≥90% numeric-coercible and all values are integer-shaped |
| `float` | pandas float dtype, or ≥90% numeric-coercible |
| `datetime` | pandas datetime64 dtype, or ≥80% parseable as datetime |
| `string` | all other cases |
| `empty` | all values are null |

**Important caveats:**
- Type inference is heuristic. A column like `["01", "02", "03"]` may be inferred as `integer` or `string` depending on coercion thresholds.
- Ambiguous columns default to `string`.
- Inferred types are stored in `dataset_columns.inferred_type` and used to route statistics.
- Type coercions are applied to the in-memory DataFrame only; the stored file is never modified.

---

## NA / Missing Values

The following values are treated as missing (NA) when parsing CSV:

`""`, `"NA"`, `"N/A"`, `"null"`, `"NULL"`, `"None"`, `"NaN"`, `"nan"`, `"#N/A"`

Missing values in numeric columns become `NaN` (pandas). Missing values in non-numeric columns become `None` / `pd.NA`. Division by zero is avoided in all percentage calculations by checking `total_count > 0` first.

---

## Duplicate Row Detection

Duplicate rows are identified using `DataFrame.duplicated(keep=False)`, which marks all copies of duplicated rows (not just the second occurrence). The reported count is `duplicates_found // 2` to avoid double-counting.

Missing values participate in duplicate comparisons: two rows are considered duplicates only if every column value matches, including both being null.

---

## Processing Limits

| Limit | Default | Behavior when exceeded |
|---|---|---|
| File size | 50 MB | Upload rejected with 400 |
| Row count | 1,000,000 | DataFrame truncated; warning added to response |
| Column count | 500 | Upload rejected with 400 |
| Top categorical values | 20 | Only the 20 most frequent values are returned |
| Unique count checked | 50,000 rows | Skipped for larger columns to avoid memory pressure |

---

## Known Edge Cases

- **Very long field values:** no per-field truncation is implemented; extremely long strings contribute to memory usage
- **Mixed-type columns:** a column like `["1", "abc", "3"]` will be typed as `string` with numeric coercion skipped
- **Timezone-aware datetime:** aware datetimes are supported; naive datetimes are treated as-is without timezone coercion
- **Non-finite floats:** `NaN` and `±Inf` are serialized as `null` in API responses; they are excluded from numeric statistics
- **Duplicate column names:** detected and reported as a warning before normalization; pandas may append suffixes automatically

---

## Statistics Definitions

### Numeric statistics

| Statistic | Definition |
|---|---|
| `count` | Number of non-null, finite values |
| `missing` | Number of null values (`NaN`, `None`) |
| `min` / `max` | Minimum / maximum of non-null values |
| `mean` | Arithmetic mean of non-null values |
| `median` | 50th percentile |
| `std` | Sample standard deviation (ddof=1) |
| `p25` / `p75` | 25th and 75th percentiles |

Non-finite values (`±Inf`, `NaN`) are excluded from all numeric aggregations. A result that would be non-finite (e.g., `std` of a single value) is returned as `null`.

### Categorical statistics

Top values are sorted by frequency, descending. Up to 20 values are returned. The `count` excludes missing values; `missing` is the count of null values.

### Datetime statistics

`earliest` and `latest` are ISO 8601 strings (from `.isoformat()`). Timezone information is preserved if present. Unparseable values become null after coercion and are counted in `missing`.
