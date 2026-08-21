"""
Catalog abstraction layer (UPGRADE_PLAN.md D.2): the per-catalog identifiers
(VizieR table IDs, display names, versions) that ingest.py needs were previously
inlined as string literals scattered through the cross-match calls. Collecting them
here means a future catalog migration -- the plan's stated example is Gaia DR4
replacing DR3 -- is a one-line edit to a registry entry, not a hunt through
ingest.py's HTTP-call bodies for every place the old identifier was typed.

This does not change any behavior by itself; ingest.py's Gaia Source/AstroParams
calls should read `GAIA_SOURCE`/`GAIA_ASTROPARAMS` from here instead of inlining
'vizier:I/355/gaiadr3' etc.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CatalogSpec:
    name: str               # matches CatalogSource.name in the DB
    version: str            # stored on CatalogSource.version and PipelineRun.catalog_versions
    vizier_table: Optional[str] = None  # CDS X-Match `cat2` identifier, e.g. "vizier:I/355/gaiadr3"
    distance_arcsec: float = 5.0


NASA_TOI = CatalogSpec(name="NASA Exoplanet Archive", version="TAP-toi-1.0")

GAIA_SOURCE = CatalogSpec(
    name="Gaia DR3",
    version="I/355/gaiadr3",
    vizier_table="vizier:I/355/gaiadr3",
)

GAIA_ASTROPARAMS = CatalogSpec(
    name="Gaia DR3 AstroParams",
    version="I/355/paramp",
    vizier_table="vizier:I/355/paramp",
)

# Recoverable per UPGRADE_PLAN.md F.5 but not yet wired into ingest.py's cross-match
# loop -- registered now so F.5 is a matter of adding the fetch call and consuming
# these entries, not inventing new identifiers at that point.
TWO_MASS = CatalogSpec(
    name="2MASS Photometry",
    version="II/246/out",
    vizier_table="vizier:II/246/out",
)

PAN_STARRS = CatalogSpec(
    name="Pan-STARRS",
    version="II/349/ps1",
    vizier_table="vizier:II/349/ps1",
)

# The 3 catalogs actually live in ingest.py today (UPGRADE_PLAN.md A.13).
LIVE_CATALOGS = [NASA_TOI, GAIA_SOURCE, GAIA_ASTROPARAMS]

ALL_CATALOGS = {c.name: c for c in [NASA_TOI, GAIA_SOURCE, GAIA_ASTROPARAMS, TWO_MASS, PAN_STARRS]}
