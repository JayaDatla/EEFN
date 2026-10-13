"""Small helpers shared by the prospective-evaluation scripts."""
import requests

NASA_TAP_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"


def current_dispositions() -> dict:
    """Current TFOP disposition for every TOI, keyed by 'NNNN.NN'. Lower-case and without
    IS NOT NULL: the archive's firewall has answered 403 to the upper-case forms of such queries."""
    last = None
    for _ in range(4):
        try:
            r = requests.get(NASA_TAP_URL, params={"query": "select toi, tfopwg_disp from toi", "format": "json"}, timeout=120)
            r.raise_for_status()
            return {f"{float(row['toi']):.2f}": row["tfopwg_disp"] for row in r.json()}
        except Exception as e:
            last = e
    raise SystemExit(f"NASA TAP unreachable: {last}")
