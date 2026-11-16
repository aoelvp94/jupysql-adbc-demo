
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
