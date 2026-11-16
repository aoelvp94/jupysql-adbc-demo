# jupysql-adbc-demo

Prototype [ADBC](https://arrow.apache.org/adbc/) support for [jupysql](https://github.com/ploomber/jupysql): `%sql` results from an ADBC DBAPI connection are read as Arrow record batches, so `.PolarsDataFrame()` and `.ArrowTable()` do not go through Python rows. It is a personal demo, not an official jupysql change, and nothing here has been opened upstream.

Upstream base: [ploomber/jupysql](https://github.com/ploomber/jupysql) [`e4b695ac8cf40849bd4ce98388432a1875ad1828`](https://github.com/ploomber/jupysql/commit/e4b695ac8cf40849bd4ce98388432a1875ad1828). The two commits on branch `local/adbc-arrow` are exported under `patches/`:

1. `97956c0` — Read ADBC DBAPI results as Arrow record batches
2. `cf5b447` — Convert ADBC interval columns to durations for rows and polars

## Layout

- `patches/0001-*.patch`, `patches/0002-*.patch`: `git format-patch` of the two commits
- `patches/jupysql-adbc.patch`: combined diff (`e4b695a..cf5b447`)
- `bench.py`, `parity.py`, `setup_data.py`: benchmark, type-parity check, and data setup
- `BENCH.md`, `bench.json`, `parity.json`: results from the run below
- `demo.ipynb`: short notebook (DuckDB + Postgres over ADBC)
- `docker-compose.yml`: PostgreSQL 17 used by the Postgres bench (`localhost:55433`, user `postgres`, password `bench`, database `bench`)
- `pyproject.toml`, `uv.lock`: bench environment (`uv` / `uvx`)

The full jupysql tree is not included. Clone it next to these files as `./jupysql` (that directory is gitignored) and apply the patches as shown below. `pyproject.toml` depends on that local checkout.

## Apply the patches

```bash
git clone https://github.com/ploomber/jupysql.git
git -C jupysql checkout e4b695ac8cf40849bd4ce98388432a1875ad1828

# preferred: apply the two commits, preserving messages
git -C jupysql am ../patches/0001-*.patch ../patches/0002-*.patch

# alternative: one combined diff
# git -C jupysql apply --check ../patches/jupysql-adbc.patch
# git -C jupysql apply ../patches/jupysql-adbc.patch
```

## Run the benchmark with uv

```bash
docker compose up -d
uv sync
uv run python setup_data.py
uv run python bench.py duckdb postgres
uv run python parity.py
uv run pytest jupysql/src/tests/test_adbc.py
```

`setup_data.py` writes `bench.duckdb` (not committed; it is larger than 1 MB) and creates the Postgres tables. To re-run only one engine: `uv run python bench.py duckdb`.

## Benchmark results

Local box: 8 vCPU, 15 GB RAM, Linux. Python 3.12.15, adbc-driver-manager / postgresql / sqlite 1.13.0, duckdb 2.0.0, polars 2.1.0, pyarrow 26.0.1, SQLAlchemy 2.1.8, duckdb-engine 0.17.0, psycopg2-binary. PostgreSQL 17 in Docker; DuckDB file database. Each (engine, dataset, path) runs in a fresh subprocess: 1 cold run, then 5 warm rounds; the table is the warm median. Peak MB is the growth in process max RSS over the connected baseline during the cold run.

Full run on commit `97956c0`; three ADBC cases were re-run on `cf5b447` (interval fix) and matched within noise. Datasets: `narrow_100k` / `narrow_1m` = `(BIGINT, DOUBLE)`; `wide_1m` = BIGINT, INTEGER, DOUBLE, NUMERIC(18,4), TIMESTAMP, TIMESTAMPTZ, DATE, BOOLEAN, 2 × TEXT. Query: `SELECT * FROM <table>`.

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

`.PolarsDataFrame()` over ADBC is within a few milliseconds of bare `fetch_arrow_table()`: 29–78x faster than today's SQLAlchemy path on DuckDB and 5.5–6.4x on PostgreSQL, with 3–9x lower peak memory (Postgres wide: 1172 MB → 243 MB). Materializing every row as Python tuples remains slow (wide: 4.4 s DuckDB, 5.2 s Postgres). Full write-up: [`BENCH.md`](BENCH.md).

## Postgres COPY / `commit()` fix

The PostgreSQL ADBC driver streams query results with `COPY`. jupysql's DBAPI path would otherwise call `connection.commit()` after `execute`, which cancels that open Arrow stream. `ADBCConnection` sets driver-level autocommit (`connection.adbc_connection.set_autocommit(True)`) and clears `_requires_manual_commit` so the stream can be consumed.

## Related issues

- [ploomber/jupysql#765](https://github.com/ploomber/jupysql/issues/765) — drop SQLAlchemy as a hard dependency
- [ploomber/jupysql#536](https://github.com/ploomber/jupysql/issues/536)
- [ploomber/jupysql#725](https://github.com/ploomber/jupysql/issues/725)

## License

Apache License 2.0. The patches are meant to be applied to jupysql, which is also Apache 2.0. This repository is a personal prototype and is not affiliated with Ploomber.
