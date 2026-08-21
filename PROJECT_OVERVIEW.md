# Exoplanet Evidence Fusion Network (EEFN) - Overview

This document explains what this project does, why it matters, and how it helps astronomers.

---

## 1. What is the problem?
When scientists search for planets outside our solar system (exoplanets), they collect data from different telescopes, databases, and space missions (like NASA's TESS telescope and the European Space Agency's Gaia mission). 

Unfortunately, these databases don't always agree. For example:
* One database might say a star is a certain size, while another says it is twice as large.
* These discrepancies lead to incorrect calculations of a planet's actual size and temperature.
* Sometimes, what looks like a new planet is actually just a pair of stars orbiting each other (a binary star system).

Currently, matching and cleaning up this conflicting data is a manual, slow, and error-prone process.

## 2. Why should we solve it?
* **Time Wasted:** Astronomers spend weeks or months clean-cleaning databases and double-checking mismatched star properties instead of doing actual science.
* **Bad Targets:** Telescopes on Earth are in high demand. If astronomers book expensive telescope time to look closer at a candidate planet, but it turns out to be a data error (a false positive), valuable time and resources are wasted.
* **Accuracy:** We need reliable, clean datasets to build an accurate map of our galaxy and understand which planets might actually be habitable.

## 3. What are the benefits of solving this?
By automatically gathering, cross-referencing, and cleaning up these datasets in one place, this project provides:
* **Immediate Alerts:** It flags physically impossible planet sizes (e.g., a planet that looks larger than a star because of bad database numbers) and other clear conflicts.
* **Smart Filtering:** It uses a machine learning classifier to predict how likely a planet candidate is to be real, or if it is just a data error.
* **Better Decision Making:** Scientists can look at a single page to see all mismatched data points, cross-check their sources, and decide if a planet candidate is worth booking telescope time to follow up on.
* **Saves Time & Money:** It handles the boring data cleanup automatically so astronomers can focus on analyzing genuine exoplanet discoveries.
