import duckdb
import adbc_driver_postgresql.dbapi as pg

PG = "postgresql://postgres:bench@127.0.0.1:55433/bench"

NARROW = "SELECT g::BIGINT AS id, (g * 0.37)::DOUBLE PRECISION AS x FROM generate_series(1, {n}) g"
WIDE_PG = """
SELECT g::BIGINT AS id,
       (g % 1000)::INTEGER AS i,
       (g * 0.37)::DOUBLE PRECISION AS f,
       ((g % 100000) / 7.0)::NUMERIC(18, 4) AS dec,
       (TIMESTAMP '2020-01-01' + g * INTERVAL '1 second') AS ts,
       (TIMESTAMPTZ '2020-01-01 00:00:00+00' + g * INTERVAL '1 second') AS tstz,
       (DATE '2020-01-01' + (g % 3650)) AS d,
       (g % 2 = 0) AS b,
       ('name-' || g)::TEXT AS s,
       md5(g::TEXT) AS s2
FROM generate_series(1, 1000000) g
"""
WIDE_DUCK = WIDE_PG.replace("(DATE '2020-01-01' + (g % 3650))", "(DATE '2020-01-01' + (g % 3650)::INTEGER)").replace("DOUBLE PRECISION", "DOUBLE")

con = duckdb.connect("bench.duckdb")
for name, n in [("narrow_100k", 100_000), ("narrow_1m", 1_000_000)]:
    con.execute(f"CREATE OR REPLACE TABLE {name} AS {NARROW.format(n=n).replace('DOUBLE PRECISION', 'DOUBLE')}")
con.execute(f"CREATE OR REPLACE TABLE wide_1m AS {WIDE_DUCK}")
print(con.sql("DESCRIBE wide_1m").fetchall())
con.close()

with pg.connect(PG, autocommit=True) as c, c.cursor() as cur:
    for name, n in [("narrow_100k", 100_000), ("narrow_1m", 1_000_000)]:
        cur.execute(f"DROP TABLE IF EXISTS {name}")
        cur.execute(f"CREATE TABLE {name} AS {NARROW.format(n=n)}")
    cur.execute("DROP TABLE IF EXISTS wide_1m")
    cur.execute(f"CREATE TABLE wide_1m AS {WIDE_PG}")
    cur.execute("ANALYZE")
    cur.execute("SELECT count(*) FROM wide_1m")
    print(cur.fetchall())
