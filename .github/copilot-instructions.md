# Copilot Instructions for AgenticAI

## Project Overview
This codebase is a collection of Python scripts and SQL files for data processing and reporting, primarily targeting Databricks and Azure environments. The main focus is on price area data extraction, audit, and loading workflows.

## Key Components
- **Python Scripts**: 
  - `nt_msp_priceArea_load.py`: Loads price area data, integrates with Databricks, and uses context from Databricks jobs. Calls `nt_msp_priceArea_query.py` for SQL logic.
  - `nt_msp_priceArea_query.py`: Contains parameterized SQL for extracting price area data from multiple joined tables. Uses string formatting for schema injection.
  - `nt_pchg_audit.py`: Handles price change audit logic, interacts with Azure File Share, and uses Databricks context for job/run IDs.
- **SQL Files**: 
  - `complex_promo.sql`, `impact_report.sql`: Contain complex SQL queries for reporting and analytics.

## Patterns & Conventions
- **Databricks Integration**: Scripts expect to run in Databricks notebooks, using `dbutils` and magic commands (e.g., `%run`).
- **Context Handling**: Job and run IDs are extracted from Databricks context JSON for traceability.
- **Azure Integration**: Uses `azure.storage.fileshare` for file operations; credentials and connection strings are expected as environment variables or notebook parameters.
- **DataFrame Operations**: Heavy use of PySpark DataFrames for data transformation and grouping.
- **Parameterization**: SQL queries are parameterized for schema flexibility (e.g., `{0}` for schema name).

## Developer Workflows
- **Running Scripts**: Execute scripts as Databricks notebooks. Use `%run` to import shared methods or dependencies.
- **Dependencies**: Ensure required Python packages (`pandas`, `azure-storage-file-share`, `pyspark`) are installed in the Databricks cluster.
- **Configuration**: Set environment variables (e.g., `conn_str`, `share_name`, `directory_path`, `mountPoint`) before running scripts.
- **Debugging**: Use Databricks notebook cells for stepwise execution and inspection. Handle exceptions with clear error propagation.

## Examples
- To extract price area data, update the schema in `nt_msp_priceArea_query.py` and call from `nt_msp_priceArea_load.py`.
- For audits, ensure Azure File Share credentials are set and run `nt_pchg_audit.py` in a Databricks environment.

## References
- See `nt_msp_priceArea_load.py` and `nt_msp_priceArea_query.py` for the main data flow pattern.
- Use `nt_pchg_audit.py` as a reference for Azure and Databricks context integration.

---
For questions or unclear patterns, review the referenced scripts or consult the data engineering team.
