# AI Agent Instructions for MEBP Pricing Data Pipeline

## Architecture Overview

This is a **Databricks-based data pipeline** for Safeway's pricing system that extracts retail store and pricing data from Google BigQuery, processes it through PySpark, and loads it into MongoDB collections. The pipeline consists of ETL jobs that handle price area data and price change audit events.

### Core Data Flow
1. **Extract**: SQL queries pull data from GCP BigQuery (`udco_ds_locn` schema)
2. **Transform**: PySpark processes data into MongoDB-ready JSON structures with nested fields
3. **Load**: Custom functions write to MongoDB collections (`priceArea`, `priceChangeAudit`)

## Key Components

### Data Sources & Targets
- **Source**: GCP BigQuery tables in `udco_ds_locn` schema (retail stores, facilities, pricing data)
- **Processing**: Databricks notebooks with PySpark DataFrames
- **Target**: MongoDB collections with structured JSON documents
- **File Processing**: Azure File Share for gzipped CSV audit files

### Critical Patterns

#### Databricks Notebook Structure
All notebooks follow this pattern:
```python
# MAGIC %run "../General/nt_user_defined_methods"  # Shared utilities
# MAGIC %run "./[query_file]"                      # SQL queries

# Context extraction for job tracking
jsonContext = dbutils.notebook.entry_point.getDbutils().notebook().getContext().toJson()
context = json.loads(jsonContext)
varRunId = context.get("currentRunId", {}).get("id", -1)
varJobId = context.get("tags", {}).get("jobId", -1)
```

#### MongoDB Document Pattern
Transform DataFrames into nested JSON with `_id` composite keys:
```python
# Always create structured _id fields
df_with_id = df.withColumn('_id', F.struct(
    F.col('ROG_ID').alias('rog'),
    F.col('aciFacilityId'),
    F.col('priceAreaId')
))

# Group and aggregate nested arrays
df_result = df.groupBy('_id', other_fields)
    .agg(F.collect_list('nested_field').alias('nested_array'))
```

#### File Processing Workflow
For audit files (`nt_pchg_audit.py`):
1. Check last processed timestamp from `stg_file_check` table
2. List Azure File Share files, compare timestamps embedded in filenames (positions 14:28)
3. Download, decompress gzip files, process as pipe-delimited CSV
4. Archive processed files, maintain rolling 30-file limit

## Essential Functions (from `nt_user_defined_methods`)

- `getBqTable(sql)` - Execute BigQuery SQL with project ID formatting
- `mongodb_Write_with_df(collection, df)` - Write DataFrame to MongoDB collection
- `mongodb_Write_with_df_append(collection, df)` - Append to existing MongoDB collection
- `getDeltaTable(None, sql)` - Execute Delta table operations
- `addDeltaTable(table_name, df, mode)` - Write to Delta tables
- `udfInsertLogDetails(level, message)` - Logging function

## Configuration Variables

Key variables expected from shared methods:
- `bq_project_id` - GCP project ID for BigQuery
- `delta_schema` - Delta Lake schema name
- `conn_str`, `share_name`, `directory_path` - Azure File Share connection details
- `mountPoint` - Databricks mount point for file operations

## Data Transformation Conventions

### Column Naming
- **Source**: UPPER_CASE with underscores (BigQuery convention)
- **Target**: camelCase for MongoDB fields
- **Composite Keys**: Use `concat_ws("-", col1, col2)` for IDs like `"ROG-PRICE_AREA"`

### Type Casting Pattern
Always explicitly cast DataFrame columns for consistency:
```python
df = df.withColumn("PRICE_AREA", df["PRICE_AREA"].cast(IntegerType())) \
    .withColumn("NEW_PRICE", df["NEW_PRICE"].cast(DoubleType())) \
    .withColumn("EFFECTIVE_DATE", df["EFFECTIVE_DATE"].cast(StringType()))
```

### Error Handling
- Wrap main processing in try/except blocks
- Use `udfInsertLogDetails("E", str(e))` for error logging
- Always re-raise exceptions after logging
- Use `dbutils.notebook.exit("success")` for early exits when no data

## File Organization

- `nt_msp_priceArea_query.py` - Contains SQL query definitions only
- `nt_msp_priceArea_load.py` - Main ETL logic with JSON transformation functions
- `nt_pchg_audit.py` - File-based processing with Azure File Share integration
- Encrypted files (`complex_promo.sql`, `price_load.py`) require decryption before editing

## Development Guidelines

1. **Always import from shared methods first** - Most database/MongoDB functions are centralized
2. **Test with small datasets** - Use `.limit(100)` during development
3. **Monitor file timestamps** - Audit processing relies on embedded timestamps in filenames
4. **Validate MongoDB structure** - Ensure `_id` fields are properly structured before writing
5. **Handle empty DataFrames** - Check `.count() == 0` before processing to avoid errors