# Competitor Research Agent

**_Autonomous multi-agent system for scraping, analyzing sentiment, and generating AI-powered pricing recommendations._**

---

## 📌 Overview

This project is an **autonomous multi-agent system** designed to:
- Scrape competitor product pages  
- Collect and analyze customer reviews  
- Extract sentiment insights  
- Compare market prices  
- Generate **AI-driven pricing recommendations**  
- Store all results into FAISS-powered memory for contextual reasoning

It uses:
- **Multiple Agents** (Scraper, Sentiment, Pricing, Coordinator)  
- **A2A (Agent-to-Agent) Protocol**  
- **Retrieval-augmented FAISS Memory**  
- **LLM-based analysis**  
- **Dark-Tech HTML business reports**  

This project is my submission for the **Kaggle Agents Intensive — Capstone Project**.

---

## 🧠 Agent Architecture

<p align="center">
  <img src="agent architecture.png" width="85%" />
</p>


---

## 🏗 Tech Stack

| Component | Technology |
|-----------|-------------|
| Multi-Agent System | Python + Requests |
| A2A Protocol | JSON-RPC-style over HTTP |
| Embeddings | Sentence Transformers (via API or local) |
| Memory | FAISS vector search + JSONL metadata |
| Web Scraping | `requests`, `beautifulsoup4` |
| Sentiment | LLM-powered |
| Pricing | Hybrid statistical + sentiment model |
| Logging | RotatingFileHandler + custom formatter |
| Report | HTML (Dark tech theme) |

---

## 📂 Project Structure

competitor research agent/  
├── agents/  
│   ├── coordinator_agent.py  
│   ├── scraper_agent.py  
│   ├── sentiment_agent.py  
│   ├── pricing_agent.py  
│   └── stub_registry.py  
│  
├── scrapers/  
│   ├── product_page.py  
│   ├── review_page.py  
│   ├── search_page.py  
│   └── logger.py  
│  
├── memory_bank/  
│   ├── base_memory.py  
│   ├── faiss_memory.py  
│   ├── product_memory.py  
│   ├── sentiment_memory.py  
│   ├── pricing_memory.py  
│   └── metadata/*.jsonl + *.faiss  
│  
├── infra/  
│   ├── embedding.py  
│   ├── util.py  
│  
├── report.html                     # Business report (Dark Theme)  
├── merged.jsonl                    # Merged memory used for report  
├── merge_jsonl.py                  # Script to merge 3 memories  
├── generate_report_html.py         # Generate HTML business report  
├── requirements.txt  
└── README.md

---

## 🛠 Installation

1. Clone the repo
```bash
git clone https://github.com/ch1ns0n/competitor_research_agent.git
cd competitor_research_agent
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Download FAISS runtime (if needed)
```bash
pip install faiss-cpu
```

---

## ▶ How to Run

1. Start Stub Agent Registry
```bash
python agents/stub_registry.py
```

2. Run individual agents

**Scraper Agent**
```bash
python agents/scraper_agent.py
```

**Sentiment Agent**
```bash
python agents/sentiment_agent.py
```

**Pricing Agent**
```bash
python agents/pricing_agent.py
```

3. Run Coordinator

The Coordinator will:  
scrape → analyze → price → embed → store → generate business summary
```bash
python agents/coordinator_agent.py
```

---

## 💡 Highlights

- Autonomous multi-agent system  
- End-to-end scraping + analysis + pricing pipeline
- FAISS memory improves recommendations over time  
- Dark-tech business report for presentation  
- Full logging + traceability  
- Modular and extendable

---

## 🧭 Future Improvements

- Add dashboards (Streamlit)  
- Add product clustering for category insights  
- Async scraping for speed  
- Real browser scraping with Playwright  
- Plug-and-play agent marketplace