# Scientific Terminology Review Report

**Reviewer**: Senior Astronomy & Computing Reviewer  
**Status**: COMPLETED & ALIGNED  

---

## 1. Wording Issue
The initial development phase used the term **"Confirmation Probability"** to display the Random Forest model's output probability. 

## 2. Reviewer Criticism
Nature Astronomy peer reviewers feedback pointed out that the label "Confirmation Probability" is scientifically indefensible. It implies a physical, direct probability that an exoplanet actually exists. In reality, the Random Forest model is trained on catalog mismatches, human follow-up decisions, and transit parameter features. It does not calculate physical existence probability; it computes a statistical likelihood that the target matches historical validation profiles (vetoing binary false positives).

---

## 3. Alternative Evaluation

| Proposed Label | Pros | Cons |
| :--- | :--- | :--- |
| **Follow-Up Success Likelihood** | Clear operational value. | Implies a future physical observing outcome. |
| **Evidence Confidence Score** | Mathematically accurate. | Too abstract for telescope schedulers. |
| **Candidate Reliability Index** | Scientifically defensible; describes the quality of the catalog matches. | Does not indicate probability explicitly. |
| **Historical Validation Likelihood**| Accurately reflects training data correlation. | Verbose for UI panels. |

---

## 4. Selected Label & Rationale
We chose **Candidate Reliability Index**.
*   **Wording**: `Candidate Reliability Index` (rendered in the candidate file detail card).
*   **Rationale**: It represents a composite evaluation index showing whether the cross-catalog measurements are aligned and reliable, without implying physical discovery or confirmation. 

---
*Verdict: PASS*
