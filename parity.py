import json

from IPython.testing.globalipapp import start_ipython

PG_URL = "postgresql://postgres:bench@127.0.0.1:55433/bench"

PG_QUERY = """
SELECT 42::SMALLINT AS i2, 42::INTEGER AS i4, 9007199254740993::BIGINT AS i8,
       1.5::REAL AS f4, 0.1::DOUBLE PRECISION AS f8,
       12345678901234.5678::NUMERIC(18, 4) AS dec, 1.23456789012345678901234567890::NUMERIC AS dec_unbounded,
       TIMESTAMP '2024-02-29 12:34:56.123456' AS ts, TIMESTAMPTZ '2024-02-29 12:34:56.123456+03' AS tstz,
       DATE '2024-02-29' AS d, TIME '12:34:56.5' AS t, INTERVAL '1 day 2 hours 3 seconds' AS iv,
       TRUE AS b, 'héllo'::TEXT AS s, 'ab'::CHAR(4) AS ch, '\\xdeadbeef'::BYTEA AS blob,
       '{"a": 1}'::JSONB AS jsonb, 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::UUID AS uuid,
       ARRAY[1, 2, 3] AS arr, NULL::INTEGER AS null_int, NULL::TEXT AS null_text
"""

DUCK_QUERY = """
SELECT 42::SMALLINT AS i2, 42::INTEGER AS i4, 9007199254740993::BIGINT AS i8, 340282366920938463463374607431768211455::UHUGEINT AS u128,
       1.5::REAL AS f4, 0.1::DOUBLE AS f8,
       12345678901234.5678::DECIMAL(18, 4) AS dec, 1.2345678901234567890123456789::DECIMAL(38, 28) AS dec38,
       TIMESTAMP '2024-02-29 12:34:56.123456' AS ts, TIMESTAMPTZ '2024-02-29 12:34:56.123456+03' AS tstz,
       DATE '2024-02-29' AS d, TIME '12:34:56.5' AS t, INTERVAL '1 day 2 hours 3 seconds' AS iv,
       TRUE AS b, 'héllo' AS s, '\\xDE\\xAD'::BLOB AS blob,
       'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::UUID AS uuid,
       [1, 2, 3] AS arr, {'k': 1, 'v': 'x'} AS st, MAP {'a': 1} AS m, NULL::INTEGER AS null_int
"""


def collect(ip, setup, query):
    from sql.connection import ConnectionManager

    setup(ip)
    rs = ip.run_line_magic("sql", query)
    row = list(rs)[0]
    keys = rs.keys
    ConnectionManager.current._result_sets.close_all()
    rs = ip.run_line_magic("sql", query)
    try:
        pl_schema = {k: str(v) for k, v in rs.PolarsDataFrame().schema.items()}
    except Exception as e:
        pl_schema = {"error": f"{type(e).__name__}: {e}"[:200]}
    ConnectionManager.current._result_sets.close_all()
    return {k: (type(v).__name__, repr(v)) for k, v in zip(keys, row)}, pl_schema


def main():
    ip = start_ipython()
    ip.run_line_magic("load_ext", "sql")
    ip.run_line_magic("config", "SqlMagic.feedback = 0")

    def pg_sa(ip):
        ip.run_line_magic("sql", PG_URL.replace("postgresql://", "postgresql+psycopg2://") + " --alias pg_sa")

    def pg_adbc(ip):
        import adbc_driver_postgresql.dbapi as drv

        ip.user_ns["pgadbc"] = drv.connect(PG_URL)
        ip.run_line_magic("sql", "pgadbc --alias pg_adbc")

    def duck_sa(ip):
        ip.run_line_magic("sql", "duckdb:// --alias duck_sa")

    def duck_adbc(ip):
        import adbc_driver_duckdb.dbapi as drv

        ip.user_ns["duckadbc"] = drv.connect()
        ip.run_line_magic("sql", "duckadbc --alias duck_adbc")

    out = {}
    for engine, query, current, adbc in [
        ("postgres", PG_QUERY, pg_sa, pg_adbc),
        ("duckdb", DUCK_QUERY, duck_sa, duck_adbc),
    ]:
        cur_rows, cur_pl = collect(ip, current, query)
        adbc_rows, adbc_pl = collect(ip, adbc, query)
        cols = {}
        for k in cur_rows:
            cols[k] = {
                "current_py": cur_rows[k],
                "adbc_py": adbc_rows.get(k),
                "current_polars": cur_pl.get(k, cur_pl.get("error")),
                "adbc_polars": adbc_pl.get(k, adbc_pl.get("error")),
            }
            cols[k]["py_match"] = cur_rows[k] == adbc_rows.get(k)
            cols[k]["polars_match"] = cols[k]["current_polars"] == cols[k]["adbc_polars"]
        out[engine] = cols
    with open("parity.json", "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    for engine, cols in out.items():
        print(f"## {engine}")
        for k, v in cols.items():
            flag = "OK " if v["py_match"] and v["polars_match"] else "DIFF"
            print(f"{flag} {k:14} cur={v['current_py']} adbc={v['adbc_py']} | pl cur={v['current_polars']} adbc={v['adbc_polars']}")


if __name__ == "__main__":
    main()
