# Analytics Tools Quick Reference

## Overview

The ds-mcp framework provides 4 core tools for exploring Redshift analytics databases through the AnalyticsReader class.

## Prerequisites

1. **AWS Credentials**: Run `assume 3VDEV` (or appropriate environment)
2. **Python Dependencies**: `threevictors`, `pandas`, `redshift-connector`
3. **Database Access**: Redshift analytics database permissions

## Available Tools

### 1. describe_table(table_name)

Get metadata about a table (schema, name, type).

**Limitations**: Works only for tables in the current database. For cross-database tables, use `read_table_head()`.

**Example**:
```python
# Current database table
reader.describe_table('price_anomalies.anomaly_table')

# Cross-database (won't work with describe_table)
# Use read_table_head() instead
```

### 2. get_table_schema(table_name)

Get detailed column information (names, data types, nullable, defaults).

**Limitations**: Works only for tables in the current database. For cross-database tables, use `read_table_head()`.

**Example**:
```python
# Current database table
schema = reader.get_table_schema('price_anomalies.anomaly_table')
print(schema)
```

### 3. read_table_head(table_name, limit=50)

Preview the first N rows from any table. **Supports cross-database queries**.

**Example**:
```python
# Cross-database query - WORKS!
df = reader.read_table_head('prod.monitoring.provider_combined_audit', limit=10)
print(df)

# Current database
df = reader.read_table_head('price_anomalies.anomaly_table', limit=20)
```

### 4. query_table(query, limit=1000)

Execute custom SELECT queries with safety limits. **Supports cross-database queries**.

**Example**:
```python
# Cross-database query - WORKS!
df = reader.query_table('''
    SELECT * FROM prod.monitoring.provider_combined_audit
    WHERE sales_date = 20251109
    LIMIT 100
''')

# Complex query with joins
df = reader.query_table('''
    SELECT customer, COUNT(*) as cnt
    FROM prod.monitoring.provider_combined_audit
    WHERE sales_date >= 20251101
    GROUP BY customer
    ORDER BY cnt DESC
''', limit=500)
```

## Usage in Interactive Chat

Run the interactive chat client:

```bash
cd ds-agentic-workflows
python chat.py
```

When prompted, enter table identifiers:
- For current DB: `price_anomalies.anomaly_table`
- For cross-DB: `prod.monitoring.provider_combined_audit`

Example chat queries:
- "Show me the first 10 rows from prod.monitoring.provider_combined_audit"
- "What columns are in the provider_combined_audit table?"
- "Get all records where sales_date = 20251109"

## Usage in ds-chat Web Interface

The ds-chat backend automatically exposes these tools through the FastAPI server.

1. Start the backend:
```bash
cd ds-chat/backend
python main.py
```

2. Open the frontend at `http://localhost:5173`

3. Tools are automatically available for the AI agent to use

## Direct Python Usage

```python
from ds_mcp.core.connectors import AnalyticsReader

# Initialize (requires AWS credentials)
reader = AnalyticsReader()

# Example 1: Quick preview
df = reader.read_table_head('prod.monitoring.provider_combined_audit', limit=5)
print(f"Preview: {len(df)} rows, {len(df.columns)} columns")

# Example 2: Filtered query
df = reader.query_table('''
    SELECT customers, sales_date, COUNT(*) as cnt
    FROM prod.monitoring.provider_combined_audit
    WHERE sales_date BETWEEN 20251101 AND 20251110
    GROUP BY customers, sales_date
    ORDER BY sales_date DESC, cnt DESC
''', limit=1000)

print(df.head(20))
```

## Important Notes

1. **Cross-database limitations**: `describe_table()` and `get_table_schema()` only work within the current database due to Redshift `information_schema` design
2. **Safety limits**: `query_table()` automatically adds LIMIT clauses if not present
3. **AWS credentials**: Must be valid and have Redshift access
4. **Query syntax**: Only SELECT and WITH queries are allowed (no INSERT/UPDATE/DELETE)

## Troubleshooting

**Problem**: "InvalidAccessKeyId" error
- **Solution**: Run `assume 3VDEV` to refresh AWS credentials

**Problem**: "Schema does not exist" error
- **Solution**: Verify the table name format (database.schema.table or schema.table)

**Problem**: `describe_table()` returns "not found" for cross-database table
- **Solution**: Use `read_table_head()` or `query_table()` instead

## Tool Comparison

| Tool | Cross-DB Support | Use Case |
|------|-----------------|----------|
| `describe_table()` | ❌ No | Quick metadata for current DB tables |
| `get_table_schema()` | ❌ No | Column details for current DB tables |
| `read_table_head()` | ✅ Yes | Preview any table (recommended for cross-DB) |
| `query_table()` | ✅ Yes | Custom SQL queries (recommended for cross-DB) |

## Best Practices

1. **For exploration**: Start with `read_table_head()` to understand table structure
2. **For analysis**: Use `query_table()` with specific WHERE clauses
3. **For schema details**: Use `get_table_schema()` for current DB tables, or inspect `read_table_head()` results for cross-DB
4. **Always filter**: Add WHERE clauses to limit data volume and improve performance
