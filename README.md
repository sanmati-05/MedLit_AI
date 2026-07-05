# MedLit AI - Biomedical Literature Mining Pipeline

> Automated extraction of genes, drugs, and clinical insights from PubMed literature, with cross-paper synthesis.

---

## Overview

Biomedical researchers face an overwhelming volume of scientific literature. Manually reading dozens of PubMed papers to identify relevant genes, drug targets, and recurring findings takes hours and does not scale, especially early in a project when the goal is simply to map out what is already known.

MedLit AI takes a disease name as input, retrieves the most relevant PubMed papers, extracts genes and drugs mentioned in each one, and, beyond summarizing individual papers - aggregates these mentions across the full set to surface which genes and drugs appear most consistently in the literature. The output is a structured report a researcher can use as a starting point for a literature review, not just a set of individual summaries. It has been validated on three diseases - lung cancer, Alzheimer's disease, and COPD, with results below.

---

## Pipeline Architecture

```
User Input (Disease Name)
        │
        ▼
PubMed Fetch — NCBI Entrez API, top N papers by relevance
        │
        ▼
LLM Entity Extraction (per paper) genes, drugs, 1-line summary, PMID
        │
        ▼
Cross-Paper Synthesis - aggregate gene/drug frequency across all papers
        │
        ▼
Relevance Scoring - entity density + publication recency
        │
        ▼
Report Generation - structured CSV + text summary, top-ranked papers and entities
```

---

## How It Works

**1. Fetch** - PubMed is queried using the disease name combined with biomedical keywords (gene, protein, mutation, drug, therapy). Titles, abstracts, publication years, and PMIDs are parsed from the response.

**2. Extract** - Each paper's title and abstract are passed to an LLM (`qwen/qwen3-32b` via Groq) with a structured prompt that returns gene symbols, drug names, and a short summary as JSON.

**3. Synthesize** - Gene and drug mentions are aggregated across all retrieved papers, so a researcher can see which entities are most consistently discussed rather than reading each paper in isolation.

**4. Score** - Each paper receives a relevance score based on entity density and how recently it was published.

**5. Report** - Results are saved as both a structured CSV (for filtering and further analysis) and a readable text summary of the top-ranked papers and entities.

---

## Results

The pipeline was run on three diseases with well-characterized gene and drug landscapes, to check whether the extracted findings match established biology rather than surfacing noise.

### Lung Cancer

| Gene | Papers | | Drug | Papers |
|------|--------|---|------|--------|
| EGFR | 5/10 | | trastuzumab deruxtecan | 2/10 |
| MET | 4/10 | | lorlatinib | 1/10 |
| ROS1, BRAF, KRAS, ALK, RET, ERBB2/HER2 | 2/10 each | | crizotinib, entrectinib, afatinib, gefitinib, erlotinib | 1/10 each |

EGFR, ALK, ROS1, BRAF, KRAS, MET, and RET are the standard panel of oncogenic driver genes used in clinical lung cancer molecular testing today. The pipeline surfaced all of them from a 10-paper sample without being told what to look for.

*Data quality note: ERBB2 and HER2 are the same gene (HER2 is ERBB2's common name), but the extraction step counted them as two separate entities. Combined, ERBB2/HER2 would rank at 4/10, tied with MET. This is a direct, observed case for the gene-alias normalization step listed under Limitations below.*

### Alzheimer's Disease

| Gene | Papers | | Drug | Papers |
|------|--------|---|------|--------|
| APP | 5/10 | | Donepezil, Memantine, donanemab, lecanemab, aducanumab | 1/10 each |
| MAPT | 4/10 | | | |
| PSEN1, APOE | 2/10 each | | | |
| PSEN2, SNCA | 1/10 each | | | |

APP, PSEN1, PSEN2, and APOE are the core genes implicated in both familial and sporadic Alzheimer's disease, and MAPT (tau) reflects the field's continued focus on tau pathology alongside amyloid. The drug list also reflects the current treatment landscape accurately — lecanemab, donanemab, and aducanumab are the three recently approved or trial-stage anti-amyloid antibodies.

### COPD

| Gene | Papers | | Drug | Papers |
|------|--------|---|------|--------|
| A1AT | 1/10 | | Mepolizumab | 2/10 |
| | | | ensifentrine, dupilumab, Benralizumab | 1/10 each |

COPD returned a noticeably weaker gene signal than the other two diseases, but a stronger biologic/drug signal. A1AT (alpha-1 antitrypsin) is the best-established genetic risk factor for COPD, so its appearance is consistent with known biology — but the low gene count relative to lung cancer and Alzheimer's likely reflects that current COPD literature emphasizes biologic treatments (Mepolizumab, Dupilumab, Benralizumab) over novel genetic drivers, rather than a failure of extraction.

---
Full per-paper reports (including PMIDs, individual gene/drug lists, and paper summaries) are available as CSV files in [`/results`](./results).

---

## Tech Stack & Setup

| | |
|---|---|
| Language | Python 3.x |
| Literature Source | NCBI PubMed, Entrez API (BioPython) |
| LLM Provider | Groq API |
| LLM Model | `qwen/qwen3-32b` |
| LLM Framework | LangChain (`langchain-groq`) |

**Install dependencies**
```bash
pip install biopython langchain-groq python-dotenv
```

**Configure environment** — create a `.env` file:
```env
NCBI_EMAIL=your_email@example.com
GROQ_API_KEY=your_groq_api_key
```
Get a free Groq key at [console.groq.com](https://console.groq.com). NCBI requires a registered email for Entrez API use — see [ncbi.nlm.nih.gov](https://www.ncbi.nlm.nih.gov).

**Run**
```bash
python medlit_ai.py --disease "lung cancer,alzheimer,COPD" --top_n 10
```

---

## Limitations & Future Work

- Gene/drug extraction depends on LLM output quality; name variants are not yet normalized to standard gene symbols (see the ERBB2/HER2 case above)
- Currently limited to PubMed; does not yet cover preprint servers (bioRxiv, medRxiv)
- Planned: gene alias resolution, larger paper counts, and a simple web interface for non-technical users

---

## Author

**Sanmati Ganesh**
sanmati.bioinfo@gmail.com
[LinkedIn](https://www.linkedin.com/in/sanmati-ganesh-701008273)

---

## License

Released under the [MIT License](LICENSE) — free to use, modify, and distribute with attribution.
