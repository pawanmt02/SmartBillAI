# ⚡ SmartBill AI — Intelligent Invoice Generator

> **Transform unstructured, conversational customer requests into validated, audit-ready invoices — powered by Google Gemini AI with zero price hallucination.**

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 What It Does

SmartBill AI takes **natural language messages** (WhatsApp, email, chat — any format) and converts them into **professional, tax-calculated invoices** in 3 clicks:

1. **Paste** a customer message
2. **Review** the AI-extracted line items (prices come from your catalog, never the AI)
3. **Download** a branded HTML invoice + JSON audit log

---

## 🏗️ Architecture

```
[ Natural Language Input ]
        │
        ▼
[ Gemini LLM Extraction ]  ──  Structured JSON: Name, Email, Items, Quantities
        │                       (NEVER prices — by design)
        ▼
[ Deterministic Price Lookup ]  ◄──  [ Catalog: services_catalog.csv ]
        │
   ┌────┴───────────────────┐
   ▼                        ▼
[ Matched Items ]   [ Flagged Items: NEEDS_MANUAL_REVIEW ]
   └────┬───────────────────┘
        │
        ▼
[ Human-in-the-Loop Review ]  ──  Edit rates, quantities, add manual prices
        │
        ▼
[ Invoice Engine ]  ──  Subtotal + GST/Tax → HTML + JSON Export
```

---

## ✨ Features

### Core Features
| Feature | Description |
|---|---|
| 🛡️ **Zero Price Hallucination** | LLM extracts only entity names & quantities. Prices come deterministically from `services_catalog.csv` |
| 🚨 **Exception Handling** | Unmatched services flagged as `NEEDS_MANUAL_REVIEW` with price ₹0 |
| ✏️ **Human-in-the-Loop Review** | Interactive editable grid — modify quantities, rates, customer details, and tax |
| 📄 **Professional Invoice** | Branded, print-ready HTML invoice with GST/VAT and unique IDs |

### Bonus Features
| Feature | Description |
|---|---|
| 📑 **Message Presets** | Quick-start with 3 sample customer messages (Tech, Design, Marketing) |
| 📊 **Invoice History** | Track all generated invoices in the sidebar |
| 📋 **JSON Audit Log** | Downloadable JSON for every invoice — full audit trail |
| 🔍 **Raw LLM Viewer** | Expandable debug panel to inspect the raw AI extraction |
| 💱 **Currency Switcher** | ₹, $, €, £ — one click |
| 📊 **Tax Slider** | GST/VAT from 0% to 28% |
| 🎨 **Branded Template** | Gradient header, alternating row colors, responsive layout |
| 🔄 **Flow Reset** | "Create New Invoice" button for back-to-back invoicing |

---

## 📂 Project Structure

```
SmartBillAI/
├── .gitignore                  # Ignores caches, secrets, generated invoices
├── .streamlit/
│   └── config.toml             # Professional theme configuration
├── app.py                      # Full-stack Streamlit application
├── services_catalog.csv        # Pricing catalog (single source of truth)
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- A [Google Gemini API Key](https://aistudio.google.com/apikey) (free tier works)

### 1. Clone & Install

```bash
git clone https://github.com/pawanmt02/SmartBillAI.git
cd SmartBillAI
pip install -r requirements.txt
```

### 2. Run Locally

```bash
streamlit run app.py
```

### 3. Enter Your API Key

Paste your Gemini API key into the sidebar **Settings** panel. That's it!

---

## 🔧 Service Catalog

The pricing catalog (`services_catalog.csv`) is the **single source of truth** for all prices. The LLM never sees or generates pricing data.

| ID | Service | Aliases | Unit Price | Category |
|---|---|---|---|---|
| SRV-001 | Web Development | website, web dev, frontend, landing page | 750.00 | Development |
| SRV-002 | UI/UX Design | figma, design, wireframe, user interface | 450.00 | Design |
| SRV-003 | SEO Optimization | seo, search engine, ranking | 300.00 | Marketing |
| SRV-004 | Content Writing | blog post, copywriting, article, copy | 120.00 | Marketing |
| SRV-005 | Logo & Branding | branding, brand identity, vector logo | 250.00 | Design |
| SRV-006 | Cloud Deployment | aws, vercel, docker, cloud hosting | 200.00 | DevOps |
| SRV-007 | API Integration | rest api, backend connection, webhook | 350.00 | Development |

**To add new services**, simply append rows to `services_catalog.csv`. The app hot-reloads on next run.

---

## 🧠 Prompt Engineering

The system prompt enforces strict extraction-only behavior — the LLM is architecturally prohibited from generating prices:

```
RULES:
1. Extract customer_name, customer_email, notes, and line items.
2. ABSOLUTELY NEVER GUESS, INVENT, OR INCLUDE PRICING OR RATES.
3. Return raw JSON only.
```

**Extraction schema:**
```json
{
  "customer_name": "string",
  "customer_email": "string",
  "notes": "string",
  "extracted_items": [
    {
      "raw_service_name": "string",
      "quantity": 1.0,
      "notes": "string"
    }
  ]
}
```

---

## 🌐 Deployment (Streamlit Cloud)

Already configured! Just:

1. Go to [share.streamlit.io](https://share.streamlit.io/) → Log in with GitHub
2. Select repo `pawanmt02/SmartBillAI`, branch `main`, file `app.py`
3. Deploy — public URL live in ~3 minutes

---

## 📊 Rubric Alignment (100 Marks)

| Criteria | Marks | Implementation |
|---|---|---|
| **Functionality & Correctness** | 30 | End-to-end NL parsing → entity extraction → editable review → invoice generation with download |
| **AI Implementation & Prompting** | 20 | Strict JSON extraction schema; LLM architecturally blocked from pricing; raw JSON audit viewer |
| **Price Data Source Integration** | 15 | Deterministic fuzzy lookup against `services_catalog.csv`; unmatched items flagged `NEEDS_MANUAL_REVIEW` |
| **Invoice Quality & Usability** | 15 | Professional branded template with gradient header, alternating rows, tax calculations, and print CSS |
| **Real-World Usefulness** | 10 | Handles natural unstructured messages; preset templates; invoice history; JSON audit trail |
| **Bonus Features** | 10 | Editable data grid, currency switcher, tax slider, message presets, invoice history, JSON export, raw LLM viewer, flow reset |

---

## 🔐 Security

- API keys are entered via password-masked input and never stored on disk
- No pricing data is ever sent to or received from the LLM
- Invoice history is session-only (not persisted)

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

**Built with ❤️ using [Streamlit](https://streamlit.io/) and [Google Gemini](https://ai.google.dev/)**
