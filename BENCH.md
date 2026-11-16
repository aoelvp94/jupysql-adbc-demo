# jupysql + ADBC benchmark

Local prototype only (branch `local/adbc-arrow` of ploomber/jupysql, nothing pushed).

- Box: 8 vCPU, 15 GB RAM, Linux. Python 3.12.15, adbc-driver-manager/postgresql/sqlite 1.13.0, duckdb 2.0.0, polars 2.1.0, pyarrow 26.0.1, SQLAlchemy 2.1.8, duckdb-engine 0.17.0, psycopg2-binary.
- PostgreSQL 17 in Docker on localhost; DuckDB file database `bench.duckdb`.
- Each (engine, dataset, path) runs in a fresh subprocess: 1 cold run, then 5 warm rounds; the table shows the warm median. Peak MB = growth in process max RSS over the connected baseline during the cold run.
- Full run on commit `97956c0`; re-ran 3 ADBC cases on `cf5b447` (interval fix) and got the same numbers within noise (pg wide polars 0.738 s, pg wide rows 5.31 s, duckdb wide polars 0.102 s).
- Datasets: `narrow_100k` / `narrow_1m` = (BIGINT, DOUBLE). `wide_1m` = BIGINT, INTEGER, DOUBLE, NUMERIC(18,4), TIMESTAMP, TIMESTAMPTZ, DATE, BOOLEAN, 2 x TEXT. Query: `SELECT * FROM <table>`.

Paths:

- `a_sqlalchemy_*`: today's jupysql path (`%sql duckdb:///...` via duckdb-engine, `%sql postgresql+psycopg2://...`). `rows` = fetch every row into the ResultSet, `polars` = `.PolarsDataFrame()` (built from Python rows), `render` = `_repr_html_()` at displaylimit 10.
- `b_adbc_arrow`: bare ADBC `cursor.fetch_arrow_table()`, no jupysql (floor).
- `c_adbc_*`: `%sql <adbc connection>` then `.PolarsDataFrame()` or `.ArrowTable()`.
- `d_adbc_render` / `d_adbc_rows`: `%sql <adbc connection>` then `_repr_html_()` / fetch every row as tuples.
- `ref_duckdb_native_polars`: existing jupysql native DuckDB DBAPI path (`.pl()` after re-executing the query).

### duckdb

| path | narrow_100k median s (peak MB) | narrow_1m median s (peak MB) | wide_1m median s (peak MB) |
|---|---|---|---|
| `a_sqlalchemy_rows` | 0.026 (23) | 0.298 (222) | 4.153 (707) |
| `a_sqlalchemy_polars` | 0.101 (55) | 0.680 (313) | 6.592 (944) |
| `a_sqlalchemy_render` | 0.002 (3) | 0.003 (16) | 0.004 (27) |
| `b_adbc_arrow` | 0.001 (5) | 0.004 (22) | 0.067 (148) |
| `c_adbc_polars` | 0.003 (13) | 0.009 (45) | 0.094 (282) |
| `c_adbc_arrow` | 0.002 (5) | 0.005 (22) | 0.071 (148) |
| `d_adbc_render` | 0.002 (5) | 0.008 (16) | 0.011 (20) |
| `d_adbc_rows` | 0.012 (20) | 0.135 (169) | 4.417 (811) |
| `ref_duckdb_native_polars` | 0.032 (47) | 0.372 (222) | 6.273 (878) |

### postgres

| path | narrow_100k median s (peak MB) | narrow_1m median s (peak MB) | wide_1m median s (peak MB) |
|---|---|---|---|
| `a_sqlalchemy_rows` | 0.039 (24) | 0.509 (243) | 2.200 (936) |
| `a_sqlalchemy_polars` | 0.111 (56) | 0.881 (329) | 4.667 (1172) |
| `a_sqlalchemy_render` | 0.015 (6) | 0.141 (59) | 0.577 (299) |
| `b_adbc_arrow` | 0.015 (2) | 0.144 (17) | 0.725 (105) |
| `c_adbc_polars` | 0.020 (4) | 0.147 (36) | 0.728 (243) |
| `c_adbc_arrow` | 0.016 (2) | 0.143 (17) | 0.738 (105) |
| `d_adbc_render` | 0.017 (2) | 0.118 (11) | 0.495 (15) |
| `d_adbc_rows` | 0.028 (17) | 0.284 (167) | 5.226 (719) |

### Speedup, current SQLAlchemy `.PolarsDataFrame()` vs ADBC `.PolarsDataFrame()`

| engine | dataset | current s | ADBC s | speedup | current peak MB | ADBC peak MB |
|---|---|---|---|---|---|---|
| duckdb | narrow_100k | 0.101 | 0.003 | 29.4x | 55 | 13 |
| duckdb | narrow_1m | 0.680 | 0.009 | 78.4x | 313 | 45 |
| duckdb | wide_1m | 6.592 | 0.094 | 70.4x | 944 | 282 |
| postgres | narrow_100k | 0.111 | 0.020 | 5.5x | 56 | 4 |
| postgres | narrow_1m | 0.881 | 0.147 | 6.0x | 329 | 36 |
| postgres | wide_1m | 4.667 | 0.728 | 6.4x | 1172 | 243 |

## Takeaways

- `.PolarsDataFrame()` over ADBC is within a few ms of bare `fetch_arrow_table()`: 29-78x faster than today's SQLAlchemy path on DuckDB and 5.5-6.4x on PostgreSQL, with 3-9x lower peak memory (PG wide: 1172 MB -> 243 MB).
- Rendering (displaylimit 10) is on par or faster; on PG wide the current path peaks at 299 MB because psycopg2 buffers the whole result client-side, ADBC peaks at 15 MB.
- Materializing every row as Python tuples is still the slow part: on the wide table ADBC rows (4.4 s DuckDB, 5.2 s PG) are about as slow as DuckDB/SQLAlchemy rows and 2.4x slower than psycopg2 rows. `pyarrow` `to_pylist` on DECIMAL and TIMESTAMPTZ dominates. Anything that iterates rows (`len(rs)`, `list(rs)`, `.csv()`, `.DataFrame()`) keeps that cost, so those should move to Arrow too.
- The existing native DuckDB fast path (`ref_duckdb_native_polars`) is slow here (6.3 s on wide_1m) because it re-executes the query after the preview fetch; ADBC keeps the batches it already read and never re-runs the query.
