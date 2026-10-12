"""Errors shared by the real-data enrichment code."""


class TransientCatalogError(Exception):
    """A catalog/MAST call failed for a reason that says nothing about the target (network
    error, 5xx, timeout). Distinct from "queried fine, nothing found": the nightly syncs record
    the former as status "error" and retry within a day instead of banning the target for 90 days.
    """
