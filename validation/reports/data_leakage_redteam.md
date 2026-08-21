# Data Leakage Red Team Report

Scanning for target variables, hidden tags, and surrogate features leaking into ML classifiers.

## 1. Database Schema Target Classification

| Column Name | Category | Risk Classification | Rationale |
| :--- | :--- | :---: | :--- |
| `disposition` | TARGET | **SAFE** | Strict separation during model training. |
| `rade` | FEATURE | **SAFE** | Physical parameter. |
| `trandep` | FEATURE | **SAFE** | Raw photometry measurement. |
| `teff_disagreement` | FEATURE | **SAFE** | Engineered cross-catalog metric. |
| `ruwe` | FEATURE | **SAFE** | Astrometric measurement. |
| `followup_priority_score` | METRIC | **SAFE** | Post-inference score. |

---
*Verdict: SAFE (No data leakage detected)*
