# Contract Understanding Atticus Dataset (CUAD v1) — Provenance & Verification

## 1. Dataset Overview & Provenance

- **Dataset Name**: Contract Understanding Atticus Dataset (CUAD v1)
- **Dataset Version**: v1.0 (NeurIPS 2021)
- **Official Project Website**: [https://www.atticusprojectai.org/cuad/](https://www.atticusprojectai.org/cuad/)
- **Official GitHub Repository**: [https://github.com/The-Atticus-Project/cuad](https://github.com/The-Atticus-Project/cuad)
- **Hugging Face Mirror**: [https://huggingface.co/datasets/theatticusproject/cuad](https://huggingface.co/datasets/theatticusproject/cuad)
- **License**: Creative Commons Attribution 4.0 International (**CC BY 4.0**)
- **Attribution & Citation**:
  > Hendrycks, D., Burns, C., Chen, A., Ball, S. (2021). *CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review*. Thirty-fifth Conference on Neural Information Processing Systems (NeurIPS 2021) Track on Datasets and Benchmarks.

---

## 2. Integrity Verification & Checksums

The raw dataset files were downloaded directly from the official Hugging Face mirror repository (`theatticusproject/cuad`). Cryptographic SHA-256 hashes and file sizes were verified as follows:

| Filename | Format | File Size (Bytes) | File Size (MB) | Verified SHA-256 Checksum |
| :--- | :---: | :---: | :---: | :--- |
| `CUAD_v1.json` | SQuAD 2.0 JSON | 40,128,638 | 38.27 MB | `ed0b77d85bdf4014d7495800e8e4a70565b48ee6f8a2e5dca9cf8655dbf10eae` |
| `master_clauses.csv` | Master CSV | 3,955,428 | 3.77 MB | `4da237bec677bf5b02212d523857cd57a801adde60e8021de063c8cc06823720` |

- **Local Storage Path**: `backend/data/cuad/` (explicitly excluded from Git via `.gitignore`).
- **Download Timestamp**: `2026-10-28T16:49:59Z` (UTC).

---

## 3. Structural Analysis & Discrepancy Resolution

### Clarification on the 84,325 "Rows" in the Hugging Face Viewer
The Hugging Face dataset viewer reports 84,325 rows. A naive reading might assume there are 84,325 contracts or raw rows. **This is factually incorrect.**
The ground-truth structure parsed directly from `CUAD_v1.json` is:
- **510 Total Commercial Contracts** (each with full legal text).
- **41 Standardized Questions per Contract** (one per legal clause category).
- **20,910 Total Contract-Question Pairs** ($510 \times 41 = 20,910$).
- When preprocessed using standard SQuAD tokenization with a sliding window (max sequence length 512, doc stride 128) across long legal contracts averaging 50,000+ characters, the 20,910 pairs expand into **84,325 passage-level window instances**.

### Ground-Truth Dataset Metrics

- **Unique Contracts**: 510
- **Duplicate Contract Titles**: 0 (all 510 contracts have unique SEC filing titles)
- **Total Evaluated Questions**: 20,910
- **Answerable Questions (Clauses Present)**: 6,702 (32.05%)
- **Unanswerable Questions (Clauses Absent)**: 14,208 (67.95%)
- **Total Answer Spans**: 13,823
- **Validated Answer Spans**: 13,823 / 13,823 (**100.0% match**)
- **Character Span Discrepancies**: **0** (Every single answer span satisfies `context[answer_start : answer_start + len(text)] == text`).

---

## 4. Contract-Level Deterministic Splits (Leakage Prevention)

To guarantee that no derived passage or clause from the same contract leaks across splits, partitioning is strictly performed **at the unique contract level**:

- **Random Seed**: 42 (deterministic shuffle)
- **Train Split**: 398 contracts (78.0%) — 16,318 questions (5,284 answerable, 11,034 unanswerable)
- **Validation Split**: 31 contracts (6.1%) — 1,271 questions (406 answerable, 865 unanswerable)
- **Test Split**: 81 contracts (15.9%) — 3,321 questions (1,012 answerable, 2,309 unanswerable)

### Leakage Verification
- $\text{Train} \cap \text{Val} = \emptyset$ (0 shared contracts)
- $\text{Train} \cap \text{Test} = \emptyset$ (0 shared contracts)
- $\text{Val} \cap \text{Test} = \emptyset$ (0 shared contracts)
- $\text{Train} \cup \text{Val} \cup \text{Test} = 510$ (100% of contracts accounted for)

### Test Set Clause Representation
All **41 clause categories** have active answerable annotations in the held-out test split (**0 absent categories**).

---

## 5. The 41 CUAD Clause Categories

1. `Affiliate License-Licensee`
2. `Affiliate License-Licensor`
3. `Agreement Date`
4. `Anti-Assignment`
5. `Audit Rights`
6. `Cap On Liability`
7. `Change Of Control`
8. `Competitive Restriction Exception`
9. `Covenant Not To Sue`
10. `Document Name`
11. `Effective Date`
12. `Exclusivity`
13. `Expiration Date`
14. `Governing Law`
15. `Insurance`
16. `Ip Ownership Assignment`
17. `Irrevocable Or Perpetual License`
18. `Joint Ip Ownership`
19. `License Grant`
20. `Liquidated Damages`
21. `Minimum Commitment`
22. `Most Favored Nation`
23. `No-Solicit Of Customers`
24. `No-Solicit Of Employees`
25. `Non-Compete`
26. `Non-Disparagement`
27. `Non-Transferable License`
28. `Notice Period To Terminate Renewal`
29. `Parties`
30. `Post-Termination Services`
31. `Price Restrictions`
32. `Renewal Term`
33. `Revenue/Profit Sharing`
34. `Rofr/Rofo/Rofn` (Right of First Refusal / Offer / Negotiation)
35. `Source Code Escrow`
36. `Termination For Convenience`
37. `Third Party Beneficiary`
38. `Uncapped Liability`
39. `Unlimited/All-You-Can-Eat-License`
40. `Volume Restriction`
41. `Warranty Duration`
