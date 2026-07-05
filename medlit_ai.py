# -*- coding: utf-8 -*-
"""MedLit_AI.py

Biomedical literature mining pipeline — fetches PubMed papers for a disease,
extracts genes/drugs using an LLM, and synthesizes findings across all papers
instead of just reporting on them one at a time.
"""

import os
import csv
import json
import time
import re
import argparse
from datetime import datetime
from collections import Counter
from dotenv import load_dotenv
from Bio import Entrez
from langchain_groq import ChatGroq

load_dotenv()  # was missing before, so .env values weren't actually being read

Entrez.email = os.getenv("NCBI_EMAIL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

CURRENT_YEAR = datetime.now().year

# scoring weights, kept as constants so they're easy to tweak without digging into functions
GENE_WEIGHT = 2
DRUG_WEIGHT = 2
RECENCY_HIGH = 3   # published within 2 years
RECENCY_MID = 1    # published within 5 years

llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model_name="qwen/qwen3-32b",
    temperature=0,
)


# 1. FETCH PAPERS
def fetch_pubmed_papers(disease, max_papers=10):
    print(f"\nSearching PubMed for: {disease}")
    handle = Entrez.esearch(
        db="pubmed",
        term=f'''
        ({disease}) AND
        (gene OR protein OR biomarker OR mutation OR pathway OR amyloid OR tau OR drug OR treatment OR therapy OR inhibitor OR agonist)
        [Title/Abstract]
        ''',
        retmax=max_papers,
        sort="relevance"
    )
    record = Entrez.read(handle)
    ids = record["IdList"]

    if not ids:
        return []

    handle = Entrez.efetch(db="pubmed", id=ids, rettype="xml")
    records = Entrez.read(handle)
    papers = []

    for article in records["PubmedArticle"]:
        try:
            art = article["MedlineCitation"]["Article"]
            pmid = str(article["MedlineCitation"]["PMID"])
            title = str(art.get("ArticleTitle", ""))

            abstract = ""
            if "Abstract" in art:
                abstract = " ".join(map(str, art["Abstract"]["AbstractText"]))

            year = art.get("Journal", {}).get("JournalIssue", {}).get("PubDate", {}).get("Year", "2022")

            papers.append({
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "year": int(year),
                "genes": [],
                "drugs": [],
                "summary": ""
            })

        except Exception:
            continue

    print(f"Fetched {len(papers)} papers")
    return papers


# 2. EXTRACT (with a retry, since the LLM occasionally returns broken JSON)
def extract_info(paper, retries=1):
    prompt = f"""
You are a biomedical information extraction system.

TASK:
Extract the following from the paper:

1. Genes:
- Extract gene symbols (e.g., APP, PSEN1, MAPT)
- Only include real biological genes
- Return as a list of uppercase strings

2. Drugs:
- Extract drug/compound names (e.g., Donepezil, Memantine)

3. Summary:
- 1-2 line concise summary

IMPORTANT RULES:
- Do NOT hallucinate
- If none found, return empty list []
- Output STRICTLY valid JSON
- Use double quotes ONLY

FORMAT:
{{
"genes": ["APP", "PSEN1"],
"drugs": ["Donepezil"],
"summary": "..."
}}

Title: {paper['title']}
Abstract: {paper['abstract'][:1000]}
"""
    attempt = 0
    while attempt <= retries:
        try:
            res = llm.invoke(prompt).content
            match = re.search(r"\{.*\}", res, re.DOTALL)
            if match:
                data = json.loads(match.group())
                paper["genes"] = [g.upper() for g in data.get("genes", [])]
                paper["drugs"] = data.get("drugs", [])
                paper["summary"] = data.get("summary", "")
                return paper
            else:
                raise ValueError("no JSON block found in LLM response")
        except Exception as e:
            attempt += 1
            if attempt > retries:
                print(f"extraction failed for '{paper['title'][:50]}...': {e}")
            else:
                time.sleep(1)  # brief pause before retrying
    return paper


def extract_all(papers):
    print("\nExtracting entities...")
    for i in range(len(papers)):
        papers[i] = extract_info(papers[i])
        time.sleep(0.5)
    return papers


# 3. RANK
def rank_papers(papers):
    for p in papers:
        score = 0
        score += len(p["genes"]) * GENE_WEIGHT
        score += len(p["drugs"]) * DRUG_WEIGHT

        age = CURRENT_YEAR - p["year"]
        if age < 2:
            score += RECENCY_HIGH
        elif age < 5:
            score += RECENCY_MID

        p["score"] = score
    return papers


# 4. SYNTHESIZE — this is the part that actually saves someone a literature review,
# not just reporting each paper on its own
def synthesize_findings(papers):
    gene_counter = Counter()
    drug_counter = Counter()

    for p in papers:
        gene_counter.update(set(p["genes"]))  # set() so a gene mentioned twice in one paper isn't double counted
        drug_counter.update(set(p["drugs"]))

    return {
        "genes": gene_counter.most_common(),
        "drugs": drug_counter.most_common()
    }


# 5. REPORT
def generate_report(disease, papers, synthesis, top_n=5):
    report = []
    report.append(f"\n--- REPORT: {disease.upper()} ---\n")

    total = len(papers)

    if synthesis["genes"]:
        report.append("Most frequently mentioned genes across all papers:")
        for gene, count in synthesis["genes"][:10]:
            report.append(f"  {gene} — {count}/{total} papers")
        report.append("")

    if synthesis["drugs"]:
        report.append("Most frequently mentioned drugs across all papers:")
        for drug, count in synthesis["drugs"][:10]:
            report.append(f"  {drug} — {count}/{total} papers")
        report.append("")

    report.append(f"Top {top_n} papers by relevance score:\n")
    top_papers = sorted(papers, key=lambda x: x['score'], reverse=True)[:top_n]

    for i, p in enumerate(top_papers, 1):
        report.append(f"{i}. {p['title']}")
        report.append(f"   PMID: {p['pmid']}  |  Year: {p['year']}  |  Score: {p['score']}")
        report.append(f"   Genes: {p['genes']}")
        report.append(f"   Drugs: {p['drugs']}")
        report.append(f"   Summary: {p['summary']}\n")

    return "\n".join(report)


def save_csv(disease, papers, filename):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["rank", "pmid", "title", "year", "score", "genes", "drugs", "summary"])

        ranked = sorted(papers, key=lambda x: x["score"], reverse=True)
        for i, p in enumerate(ranked, 1):
            writer.writerow([
                i, p["pmid"], p["title"], p["year"], p["score"],
                "; ".join(p["genes"]), "; ".join(p["drugs"]), p["summary"]
            ])


# MAIN PIPELINE
def run_pipeline(disease, max_papers=10, top_n=5):
    papers = fetch_pubmed_papers(disease, max_papers=max_papers)

    if not papers:
        return "No papers found."

    papers = extract_all(papers)
    papers = rank_papers(papers)
    synthesis = synthesize_findings(papers)

    report = generate_report(disease, papers, synthesis, top_n=top_n)

    os.makedirs("results", exist_ok=True)
    base_name = disease.replace(' ', '_')

    txt_path = f"results/{base_name}.txt"
    csv_path = f"results/{base_name}.csv"

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(report)
    save_csv(disease, papers, csv_path)

    print(f"\nSaved report: {txt_path}")
    print(f"Saved data: {csv_path}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MedLit AI — biomedical literature mining pipeline")
    parser.add_argument("--disease", type=str, help="Disease name, or multiple names separated by commas")
    parser.add_argument("--top_n", type=int, default=10, help="Number of papers to fetch (default: 10)")
    args = parser.parse_args()

    disease_input = args.disease or input("Enter disease (comma-separate for multiple): ") or "Alzheimer disease"
    diseases = [d.strip() for d in disease_input.split(",") if d.strip()]

    for disease in diseases:
        print(f"\n{'='*50}")
        result = run_pipeline(disease, max_papers=args.top_n)
        print(result)
