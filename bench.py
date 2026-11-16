import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import time

ROUNDS = int(os.environ.get("ROUNDS", "5"))
PG_URL = "postgresql://postgres:bench@127.0.0.1:55433/bench"
DUCK_PATH = os.path.abspath("bench.duckdb")
DATASETS = ["narrow_100k", "narrow_1m", "wide_1m"]
PATHS = {
    "a_sqlalchemy_rows": "current: SQLAlchemy ResultSet, fetch all rows",
    "a_sqlalchemy_polars": "current: SQLAlchemy ResultSet -> .PolarsDataFrame()",
    "a_sqlalchemy_render": "current: SQLAlchemy ResultSet -> _repr_html_ (displaylimit 10)",
    "b_adbc_arrow": "ADBC cursor.fetch_arrow_table() (no jupysql)",
    "c_adbc_polars": "ADBC %sql ResultSet -> .PolarsDataFrame()",
    "c_adbc_arrow": "ADBC %sql ResultSet -> .ArrowTable()",
    "d_adbc_render": "ADBC %sql ResultSet -> _repr_html_ (displaylimit 10)",
    "d_adbc_rows": "ADBC %sql ResultSet, fetch all rows",
    "ref_duckdb_native_polars": "reference: native duckdb DBAPI -> .PolarsDataFrame() (.pl())",
}


def maxrss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def run_case(engine, dataset, path):
    from IPython.testing.globalipapp import start_ipython

    ip = start_ipython()
    ip.run_line_magic("load_ext", "sql")
    ip.run_line_magic("config", "SqlMagic.feedback = 0")
    ip.run_line_magic("config", "SqlMagic.displaycon = False")
    from sql.connection import ConnectionManager

    query = f"SELECT * FROM {dataset}"
    raw = None

    if path.startswith("a_"):
        url = PG_URL.replace("postgresql://", "postgresql+psycopg2://") if engine == "postgres" else f"duckdb:///{DUCK_PATH}"
        ip.run_line_magic("sql", url)
    elif path == "ref_duckdb_native_polars":
        import duckdb

        ip.user_ns["nativeconn"] = duckdb.connect(DUCK_PATH)
        ip.run_line_magic("sql", "nativeconn")
    else:
        if engine == "postgres":
            import adbc_driver_postgresql.dbapi as drv

            raw = drv.connect(PG_URL)
        else:
            import adbc_driver_duckdb.dbapi as drv

            raw = drv.connect(path=DUCK_PATH)
        if not path.startswith("b_"):
            ip.user_ns["adbcconn"] = raw
            ip.run_line_magic("sql", "adbcconn")

    def once():
        if path == "b_adbc_arrow":
            with raw.cursor() as cur:
                cur.execute(query)
                out = cur.fetch_arrow_table()
            return out.num_rows
        rs = ip.run_line_magic("sql", query)
        if path.endswith("_rows"):
            n = len(rs)
        elif path.endswith("_polars"):
            n = rs.PolarsDataFrame().height
        elif path == "c_adbc_arrow":
            n = rs.ArrowTable().num_rows
        else:
            html = rs._repr_html_()
            n = html.count("<tr>") - 1
        ConnectionManager.current._result_sets.close_all()
        return n

    base = maxrss_mb()
    t0 = time.perf_counter()
    rows = once()
    cold = time.perf_counter() - t0
    peak = maxrss_mb() - base
    times = []
    for _ in range(ROUNDS):
        t0 = time.perf_counter()
        once()
        times.append(time.perf_counter() - t0)
    return {
        "engine": engine,
        "dataset": dataset,
        "path": path,
        "rows": rows,
        "cold_s": cold,
        "median_s": statistics.median(times),
        "min_s": min(times),
        "rounds": ROUNDS,
        "peak_rss_delta_mb": peak,
    }


def main():
    if len(sys.argv) == 4:
        print(json.dumps(run_case(*sys.argv[1:])))
        return
    engines = sys.argv[1:] or ["duckdb", "postgres"]
    results = []
    for engine in engines:
        for dataset in DATASETS:
            for path in PATHS:
                if path.startswith("ref_") and engine != "duckdb":
                    continue
                out = subprocess.run([sys.executable, __file__, engine, dataset, path], capture_output=True, text=True)
                if out.returncode:
                    print(engine, dataset, path, "FAILED", out.stderr[-2000:], file=sys.stderr)
                    results.append({"engine": engine, "dataset": dataset, "path": path, "error": out.stderr.strip().splitlines()[-1]})
                    continue
                r = json.loads([l for l in out.stdout.splitlines() if l.startswith("{")][-1])
                results.append(r)
                print(f"{engine:8} {dataset:12} {path:26} rows={r['rows']:>8} median={r['median_s']:.3f}s peak+={r['peak_rss_delta_mb']:.0f}MB", flush=True)
    import adbc_driver_manager, duckdb, polars, pyarrow, sqlalchemy

    meta = {
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "versions": {
            "adbc_driver_manager": adbc_driver_manager.__version__,
            "duckdb": duckdb.__version__,
            "polars": polars.__version__,
            "pyarrow": pyarrow.__version__,
            "sqlalchemy": sqlalchemy.__version__,
        },
        "postgres": "17 (docker postgres:17, localhost)",
        "rounds": ROUNDS,
        "paths": PATHS,
    }
    with open("bench.json", "w") as f:
        json.dump({"meta": meta, "results": results}, f, indent=2)


if __name__ == "__main__":
    main()
