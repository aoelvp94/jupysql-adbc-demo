import nbformat as nbf

cells = [
    nbf.v4.new_markdown_cell("# `%sql` over ADBC\n\nLocal prototype: jupysql branch `local/adbc-arrow`. ADBC DBAPI connections are detected automatically; results are read as Arrow record batches."),
    nbf.v4.new_code_cell("%load_ext sql\n%config SqlMagic.displaylimit = 5"),
    nbf.v4.new_markdown_cell("## DuckDB via ADBC"),
    nbf.v4.new_code_cell("import adbc_driver_duckdb.dbapi\n\nduck = adbc_driver_duckdb.dbapi.connect()\n%sql duck"),
    nbf.v4.new_code_cell("%%sql\nCREATE TABLE trips AS\nSELECT g AS id, TIMESTAMP '2026-01-01' + g * INTERVAL '1 minute' AS started_at,\n       (g % 97)::DECIMAL(10, 2) AS fare, 'zone-' || (g % 10) AS zone\nFROM range(1000000) t(g)"),
    nbf.v4.new_code_cell("%sql SELECT * FROM trips ORDER BY id"),
    nbf.v4.new_code_cell("%sql conn_info << SELECT 1\nfrom sql.connection import ConnectionManager\nConnectionManager.current.alias, ConnectionManager.current.dialect, type(conn_info.sqlaproxy).__name__"),
    nbf.v4.new_code_cell("import time\n\nrs = %sql SELECT * FROM trips\nt0 = time.perf_counter()\ndf = rs.PolarsDataFrame()\nprint(f\"{df.height:,} rows to polars in {time.perf_counter() - t0:.3f}s\")\ndf.schema"),
    nbf.v4.new_code_cell("rs = %sql SELECT zone, count(*) AS n, sum(fare) AS revenue FROM trips GROUP BY zone ORDER BY zone\nrs.ArrowTable().schema"),
    nbf.v4.new_markdown_cell("## PostgreSQL via ADBC"),
    nbf.v4.new_code_cell("import adbc_driver_postgresql.dbapi\n\npg = adbc_driver_postgresql.dbapi.connect(\"postgresql://postgres:bench@127.0.0.1:55433/bench\")\n%sql pg"),
    nbf.v4.new_code_cell("%sql SELECT * FROM wide_1m ORDER BY id"),
    nbf.v4.new_code_cell("rs = %sql SELECT * FROM wide_1m\nt0 = time.perf_counter()\ndf = rs.PolarsDataFrame()\nprint(f\"{df.height:,} rows to polars in {time.perf_counter() - t0:.3f}s\")\ndf.schema"),
    nbf.v4.new_code_cell("%config SqlMagic.autopolars = True\n%sql SELECT d, count(*) AS n FROM wide_1m GROUP BY d ORDER BY d LIMIT 3"),
]
nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}})
nbf.write(nb, "demo.ipynb")
