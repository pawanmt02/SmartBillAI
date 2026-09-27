import streamlit as st
import pandas as pd
import json
import re
from datetime import datetime
import google.generativeai as genai


# ──────────────────────────────────────────────
# Configuration & Page Setup
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="SmartBill AI - Invoice Generator",
    page_icon="⚡",
    layout="wide",
)


# ──────────────────────────────────────────────
# Load / Bootstrap the Service Catalog
# ──────────────────────────────────────────────
@st.cache_data
def load_catalog() -> pd.DataFrame:
    """Load the pricing catalog from CSV.
    Falls back to a built-in default so the app always starts."""
    try:
        return pd.read_csv("services_catalog.csv")
    except Exception:
        data = {
            "service_id": [
                "SRV-001", "SRV-002", "SRV-003",
                "SRV-004", "SRV-005", "SRV-006", "SRV-007",
            ],
            "service_name": [
                "Web Development", "UI/UX Design", "SEO Optimization",
                "Content Writing", "Logo & Branding", "Cloud Deployment",
                "API Integration",
            ],
            "aliases": [
                "website, web dev, frontend, landing page",
                "figma, design, wireframe, user interface",
                "seo, search engine, ranking",
                "blog post, copywriting, article, copy",
                "branding, brand identity, vector logo",
                "aws, vercel, docker, cloud hosting",
                "rest api, backend connection, webhook",
            ],
            "unit_price": [750.0, 450.0, 300.0, 120.0, 250.0, 200.0, 350.0],
            "category": [
                "Development", "Design", "Marketing",
                "Marketing", "Design", "DevOps", "Development",
            ],
        }
        df = pd.DataFrame(data)
        df.to_csv("services_catalog.csv", index=False)
        return df


catalog_df = load_catalog()


# ──────────────────────────────────────────────
# Deterministic Price Lookup (Zero Hallucination)
# ──────────────────────────────────────────────
def match_service_price(raw_name: str, catalog: pd.DataFrame) -> dict:
    """Match a raw service name against the catalog using fuzzy alias matching.

    Returns a dict with matched_name, unit_price, service_id, and status.
    Unmatched items are flagged as NEEDS_MANUAL_REVIEW with price 0.
    """
    raw_name_clean = raw_name.lower().strip()

    for _, row in catalog.iterrows():
        service_name_lower = row["service_name"].lower()
        aliases = [
            a.strip().lower()
            for a in str(row.get("aliases", "")).split(",")
        ]

        # Check exact / substring match on name or any alias
        if (
            service_name_lower in raw_name_clean
            or raw_name_clean in service_name_lower
            or any(alias in raw_name_clean for alias in aliases if alias)
        ):
            return {
                "matched_name": row["service_name"],
                "unit_price": float(row["unit_price"]),
                "service_id": row["service_id"],
                "status": "MATCHED",
            }

    return {
        "matched_name": raw_name,
        "unit_price": 0.0,
        "service_id": "N/A",
        "status": "NEEDS_MANUAL_REVIEW",
    }


# ──────────────────────────────────────────────
# LLM Extraction Engine (Gemini)
# ──────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are an expert procurement and billing data extraction engine.
Your sole task is to convert raw customer requirements into structured JSON.

RULES:
1. Extract:
   - customer_name  : Full name if present, else "Valued Client".
   - customer_email  : Valid email address if mentioned, else "".
   - notes           : Any explicit project deadlines, deliverables, or special instructions.
   - extracted_items : Array of objects with:
       • "raw_service_name" – the service the customer asked for
       • "quantity"         – float, default 1.0 if not specified
       • "notes"            – item-specific notes (empty string if none)

2. ABSOLUTELY NEVER GUESS, INVENT, OR INCLUDE PRICING OR RATES.
3. Return raw JSON only. Do not wrap in markdown quotes or preamble.
"""


def extract_invoice_details(api_key: str, text: str) -> dict:
    """Call Gemini to extract structured invoice data from free-form text."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""{SYSTEM_PROMPT}

Extract data from the following customer message and return JSON matching this schema:
{{
  "customer_name": "string",
  "customer_email": "string",
  "notes": "string",
  "extracted_items": [
    {{"raw_service_name": "string", "quantity": 1.0, "notes": "string"}}
  ]
}}

Customer Message:
\"\"\"{text}\"\"\"
"""
    response = model.generate_content(prompt)
    # Strip markdown fences that models sometimes add
    clean_json = re.sub(r"```json|```", "", response.text).strip()
    return json.loads(clean_json)


# ──────────────────────────────────────────────
# Invoice HTML Generator
# ──────────────────────────────────────────────
def build_invoice_html(
    invoice_number: str,
    date_str: str,
    customer_name: str,
    customer_email: str,
    items_df: pd.DataFrame,
    subtotal: float,
    tax_rate: int,
    tax_amount: float,
    grand_total: float,
    currency_symbol: str,
) -> str:
    """Build a clean, printable HTML invoice."""
    table_rows = ""
    for _, row in items_df.iterrows():
        table_rows += f"""
        <tr>
          <td style="padding:10px; border-bottom:1px solid #ddd;">{row['Service']}</td>
          <td style="padding:10px; border-bottom:1px solid #ddd; text-align:center;">{row['Quantity']}</td>
          <td style="padding:10px; border-bottom:1px solid #ddd; text-align:right;">{currency_symbol} {row['Unit Price']:,.2f}</td>
          <td style="padding:10px; border-bottom:1px solid #ddd; text-align:right;">{currency_symbol} {row['Line Total']:,.2f}</td>
        </tr>"""

    return f"""
    <div style="font-family:Arial, sans-serif; max-width:750px; margin:auto;
                padding:30px; border:1px solid #eee; border-radius:8px;">
      <table style="width:100%; border-collapse:collapse;">
        <tr>
          <td>
            <h2 style="margin:0;">KODNEXUS SERVICES</h2>
            <p style="color:#666; font-size:13px;">Bengaluru, Karnataka, India</p>
          </td>
          <td style="text-align:right;">
            <h3 style="margin:0;">INVOICE</h3>
            <p><b>No:</b> {invoice_number}<br><b>Date:</b> {date_str}</p>
          </td>
        </tr>
      </table>
      <hr style="margin:20px 0; border:none; border-top:1px solid #eee;">
      <p><b>Billed To:</b><br>{customer_name}<br>{customer_email}</p>
      <table style="width:100%; border-collapse:collapse; margin-top:20px;">
        <thead>
          <tr style="background-color:#f8f9fa;">
            <th style="padding:10px; text-align:left;">Service Description</th>
            <th style="padding:10px; text-align:center;">Qty</th>
            <th style="padding:10px; text-align:right;">Unit Price</th>
            <th style="padding:10px; text-align:right;">Total</th>
          </tr>
        </thead>
        <tbody>{table_rows}</tbody>
      </table>
      <div style="text-align:right; margin-top:25px;">
        <p>Subtotal: <b>{currency_symbol} {subtotal:,.2f}</b></p>
        <p>Tax ({tax_rate}%): <b>{currency_symbol} {tax_amount:,.2f}</b></p>
        <h3 style="color:#2e7d32;">Total Amount Due: {currency_symbol} {grand_total:,.2f}</h3>
      </div>
      <hr style="margin:20px 0; border:none; border-top:1px solid #eee;">
      <p style="font-size:12px; color:#999; text-align:center;">
        Generated by SmartBill AI &bull; Zero-hallucination invoice engine
      </p>
    </div>
    """


# ══════════════════════════════════════════════
# STREAMLIT  UI
# ══════════════════════════════════════════════

st.title("⚡ SmartBill AI")
st.caption(
    "Transform natural language requirements into validated, audit-ready invoices."
)

# ── Sidebar settings ──
with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input(
        "Gemini API Key",
        type="password",
        help="Enter your Google Gemini API key",
    )
    tax_rate = st.slider(
        "Tax Rate (GST / VAT %)", min_value=0, max_value=28, value=18
    )
    currency_symbol = st.selectbox("Currency", ["₹", "$", "€", "£"])

    st.divider()
    st.subheader("📖 Service Catalog")
    st.dataframe(
        catalog_df[["service_name", "unit_price", "category"]],
        use_container_width=True,
        hide_index=True,
    )

# ── Session state initialisation ──
if "extracted_data" not in st.session_state:
    st.session_state.extracted_data = None
if "invoice_approved" not in st.session_state:
    st.session_state.invoice_approved = False


# ────────────────────────────────
# Step 1 – Natural-Language Input
# ────────────────────────────────
st.subheader("1️⃣  Customer Requirement Input")

sample_prompt = (
    "Hi, this is Rajesh Sharma from Bangalore (rajesh@techcorp.in). "
    "We need 2 responsive landing pages built, 1 Figma UI/UX redesign, "
    "and 3 blog articles on Cloud AI. "
    "Please also include a mobile app penetration test. "
    "We need this delivered within 10 days."
)
user_input = st.text_area(
    "Customer Message / Project Scope:",
    value=sample_prompt,
    height=120,
)

if st.button("🚀 Process & Extract Entities", type="primary"):
    if not api_key:
        st.error("Please enter a valid Gemini API Key in the sidebar.")
    else:
        with st.spinner("Analysing message and looking up catalog prices…"):
            try:
                parsed = extract_invoice_details(api_key, user_input)

                processed_items = []
                for item in parsed.get("extracted_items", []):
                    lookup = match_service_price(
                        item["raw_service_name"], catalog_df
                    )
                    processed_items.append(
                        {
                            "Service": lookup["matched_name"],
                            "Quantity": float(item.get("quantity", 1.0)),
                            "Unit Price": lookup["unit_price"],
                            "Status": lookup["status"],
                        }
                    )

                st.session_state.customer_name = parsed.get(
                    "customer_name", "Valued Client"
                )
                st.session_state.customer_email = parsed.get(
                    "customer_email", ""
                )
                st.session_state.notes = parsed.get("notes", "")
                st.session_state.items_df = pd.DataFrame(processed_items)
                st.session_state.extracted_data = True
                st.session_state.invoice_approved = False

            except Exception as e:
                st.error(f"Extraction failed: {e}")


# ────────────────────────────────
# Step 2 – Review & Approval
# ────────────────────────────────
if st.session_state.extracted_data:
    st.divider()
    st.subheader("2️⃣  Review & Approval Dashboard")
    st.info(
        "🛡️ The AI did **not** invent prices. All prices come from the catalog. "
        "Items marked **NEEDS_MANUAL_REVIEW** must have a unit price assigned before approval."
    )

    col1, col2 = st.columns(2)
    with col1:
        st.session_state.customer_name = st.text_input(
            "Customer Name", value=st.session_state.customer_name
        )
    with col2:
        st.session_state.customer_email = st.text_input(
            "Customer Email", value=st.session_state.customer_email
        )

    if st.session_state.notes:
        st.text_area(
            "Project Notes (extracted)", value=st.session_state.notes, disabled=True
        )

    # Editable line-item grid
    edited_df = st.data_editor(
        st.session_state.items_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Unit Price": st.column_config.NumberColumn(
                format=f"{currency_symbol} %.2f"
            ),
            "Quantity": st.column_config.NumberColumn(
                min_value=0.1, step=1.0
            ),
            "Status": st.column_config.TextColumn(disabled=True),
        },
    )

    # Calculations
    edited_df["Line Total"] = edited_df["Quantity"] * edited_df["Unit Price"]
    subtotal = edited_df["Line Total"].sum()
    tax_amount = subtotal * (tax_rate / 100.0)
    grand_total = subtotal + tax_amount

    # Flag unpriced items
    unpriced_count = int((edited_df["Unit Price"] <= 0).sum())
    if unpriced_count > 0:
        st.warning(
            f"⚠️ {unpriced_count} item(s) have a price of \\$0. "
            "Enter unit prices before approving."
        )

    c1, c2, c3 = st.columns(3)
    c1.metric("Subtotal", f"{currency_symbol} {subtotal:,.2f}")
    c2.metric(f"Tax ({tax_rate}%)", f"{currency_symbol} {tax_amount:,.2f}")
    c3.metric("Grand Total", f"{currency_symbol} {grand_total:,.2f}")

    if st.button("✅ Approve & Generate Final Invoice", type="primary"):
        st.session_state.final_df = edited_df
        st.session_state.subtotal = subtotal
        st.session_state.tax_amount = tax_amount
        st.session_state.grand_total = grand_total
        st.session_state.invoice_approved = True


# ────────────────────────────────
# Step 3 – Final Invoice
# ────────────────────────────────
if st.session_state.invoice_approved:
    st.divider()
    st.subheader("3️⃣  Ready-to-Send Invoice")

    invoice_number = f"INV-{datetime.now().strftime('%Y%m%d%H%M')}"
    today_str = datetime.now().strftime("%d %b %Y")

    html_invoice = build_invoice_html(
        invoice_number=invoice_number,
        date_str=today_str,
        customer_name=st.session_state.customer_name,
        customer_email=st.session_state.customer_email,
        items_df=st.session_state.final_df,
        subtotal=st.session_state.subtotal,
        tax_rate=tax_rate,
        tax_amount=st.session_state.tax_amount,
        grand_total=st.session_state.grand_total,
        currency_symbol=currency_symbol,
    )

    st.components.v1.html(html_invoice, height=520, scrolling=True)

    st.download_button(
        label="📥 Download HTML Invoice",
        data=html_invoice,
        file_name=f"{invoice_number}.html",
        mime="text/html",
    )
