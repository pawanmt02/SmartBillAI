import streamlit as st
import pandas as pd
import json
import re
import base64
import uuid
from datetime import datetime
from io import BytesIO
import google.generativeai as genai


# ──────────────────────────────────────────────
# Configuration & Page Setup
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="SmartBill AI - Invoice Generator",
    page_icon="⚡",
    layout="wide",
)

# Custom CSS for polished look
st.markdown("""
<style>
    .stMetric { background: #f8f9fa; padding: 12px; border-radius: 8px; }
    .status-matched { color: #2e7d32; font-weight: bold; }
    .status-review { color: #e65100; font-weight: bold; }
    div[data-testid="stDataEditor"] { border: 1px solid #e0e0e0; border-radius: 8px; }
    .invoice-header { font-size: 1.5rem; font-weight: 700; color: #4F46E5; }
</style>
""", unsafe_allow_html=True)


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

    Returns a dict with matched_name, unit_price, service_id, category, and status.
    Unmatched items are flagged as NEEDS_MANUAL_REVIEW with price 0.
    """
    raw_name_clean = raw_name.lower().strip()

    best_match = None
    best_score = 0

    for _, row in catalog.iterrows():
        service_name_lower = row["service_name"].lower()
        aliases = [
            a.strip().lower()
            for a in str(row.get("aliases", "")).split(",")
        ]

        score = 0
        # Exact match gets highest score
        if raw_name_clean == service_name_lower:
            score = 100
        # Substring match on service name
        elif service_name_lower in raw_name_clean or raw_name_clean in service_name_lower:
            score = 80
        # Alias match
        else:
            for alias in aliases:
                if alias and alias in raw_name_clean:
                    score = max(score, 60)
                if alias and raw_name_clean in alias:
                    score = max(score, 50)

        if score > best_score:
            best_score = score
            best_match = row

    if best_match is not None and best_score > 0:
        return {
            "matched_name": best_match["service_name"],
            "unit_price": float(best_match["unit_price"]),
            "service_id": best_match["service_id"],
            "category": best_match.get("category", ""),
            "confidence": best_score,
            "status": "MATCHED",
        }

    return {
        "matched_name": raw_name,
        "unit_price": 0.0,
        "service_id": "N/A",
        "category": "Uncategorised",
        "confidence": 0,
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
# Invoice HTML Generator (Enhanced)
# ──────────────────────────────────────────────
def build_invoice_html(
    invoice_number: str,
    date_str: str,
    customer_name: str,
    customer_email: str,
    notes: str,
    items_df: pd.DataFrame,
    subtotal: float,
    tax_rate: int,
    tax_amount: float,
    grand_total: float,
    currency_symbol: str,
) -> str:
    """Build a professional, print-ready HTML invoice with full styling."""
    table_rows = ""
    for idx, row in items_df.iterrows():
        bg = "#ffffff" if idx % 2 == 0 else "#f9fafb"
        table_rows += f"""
        <tr style="background:{bg};">
          <td style="padding:12px 10px; border-bottom:1px solid #e5e7eb;">{idx + 1}</td>
          <td style="padding:12px 10px; border-bottom:1px solid #e5e7eb;">{row['Service']}</td>
          <td style="padding:12px 10px; border-bottom:1px solid #e5e7eb; text-align:center;">{row['Quantity']:.1f}</td>
          <td style="padding:12px 10px; border-bottom:1px solid #e5e7eb; text-align:right;">{currency_symbol} {row['Unit Price']:,.2f}</td>
          <td style="padding:12px 10px; border-bottom:1px solid #e5e7eb; text-align:right; font-weight:600;">{currency_symbol} {row['Line Total']:,.2f}</td>
        </tr>"""

    notes_section = ""
    if notes:
        notes_section = f"""
        <div style="margin-top:20px; padding:12px; background:#fffbeb; border-left:4px solid #f59e0b; border-radius:4px;">
          <p style="margin:0; font-size:13px; color:#92400e;"><b>📋 Notes:</b> {notes}</p>
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Invoice {invoice_number}</title>
  <style>
    @media print {{
      body {{ margin: 0; }}
      .no-print {{ display: none; }}
    }}
    body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #1f2937; margin: 0; padding: 0; }}
  </style>
</head>
<body>
  <div style="max-width:800px; margin:auto; padding:40px; border:1px solid #e5e7eb; border-radius:12px; background:#fff;">

    <!-- Header -->
    <table style="width:100%; border-collapse:collapse; margin-bottom:30px;">
      <tr>
        <td style="vertical-align:top;">
          <div style="font-size:28px; font-weight:800; color:#4F46E5; letter-spacing:-0.5px;">KODNEXUS</div>
          <div style="font-size:12px; color:#6b7280; margin-top:4px;">
            Bengaluru, Karnataka, India<br>
            contact@kodnexus.com &bull; +91-9876543210
          </div>
        </td>
        <td style="text-align:right; vertical-align:top;">
          <div style="font-size:32px; font-weight:800; color:#111827; letter-spacing:2px;">INVOICE</div>
          <table style="margin-left:auto; margin-top:8px; font-size:13px; color:#6b7280;">
            <tr><td style="padding:2px 8px; text-align:right;"><b>Invoice No:</b></td><td>{invoice_number}</td></tr>
            <tr><td style="padding:2px 8px; text-align:right;"><b>Date:</b></td><td>{date_str}</td></tr>
            <tr><td style="padding:2px 8px; text-align:right;"><b>Due Date:</b></td><td>Upon receipt</td></tr>
          </table>
        </td>
      </tr>
    </table>

    <!-- Divider -->
    <div style="height:3px; background:linear-gradient(to right, #4F46E5, #818cf8, #c7d2fe); border-radius:2px; margin-bottom:25px;"></div>

    <!-- Bill To -->
    <div style="background:#f9fafb; padding:16px; border-radius:8px; margin-bottom:25px;">
      <div style="font-size:11px; text-transform:uppercase; color:#9ca3af; letter-spacing:1px; margin-bottom:6px;">Billed To</div>
      <div style="font-size:16px; font-weight:600; color:#111827;">{customer_name}</div>
      <div style="font-size:14px; color:#6b7280;">{customer_email}</div>
    </div>

    <!-- Line Items -->
    <table style="width:100%; border-collapse:collapse; margin-bottom:25px;">
      <thead>
        <tr style="background:#4F46E5;">
          <th style="padding:12px 10px; text-align:left; color:#fff; font-size:12px; text-transform:uppercase; letter-spacing:0.5px; border-radius:6px 0 0 0;">#</th>
          <th style="padding:12px 10px; text-align:left; color:#fff; font-size:12px; text-transform:uppercase; letter-spacing:0.5px;">Service Description</th>
          <th style="padding:12px 10px; text-align:center; color:#fff; font-size:12px; text-transform:uppercase; letter-spacing:0.5px;">Qty</th>
          <th style="padding:12px 10px; text-align:right; color:#fff; font-size:12px; text-transform:uppercase; letter-spacing:0.5px;">Unit Price</th>
          <th style="padding:12px 10px; text-align:right; color:#fff; font-size:12px; text-transform:uppercase; letter-spacing:0.5px; border-radius:0 6px 0 0;">Total</th>
        </tr>
      </thead>
      <tbody>{table_rows}</tbody>
    </table>

    <!-- Totals -->
    <table style="width:350px; margin-left:auto; border-collapse:collapse;">
      <tr>
        <td style="padding:8px 12px; color:#6b7280;">Subtotal</td>
        <td style="padding:8px 12px; text-align:right;">{currency_symbol} {subtotal:,.2f}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px; color:#6b7280;">Tax ({tax_rate}%)</td>
        <td style="padding:8px 12px; text-align:right;">{currency_symbol} {tax_amount:,.2f}</td>
      </tr>
      <tr style="border-top:2px solid #4F46E5;">
        <td style="padding:12px; font-size:18px; font-weight:700; color:#111827;">Total Due</td>
        <td style="padding:12px; text-align:right; font-size:18px; font-weight:700; color:#4F46E5;">{currency_symbol} {grand_total:,.2f}</td>
      </tr>
    </table>

    {notes_section}

    <!-- Footer -->
    <div style="margin-top:35px; padding-top:20px; border-top:1px solid #e5e7eb; text-align:center;">
      <p style="font-size:12px; color:#9ca3af; margin:0;">
        Thank you for your business! &bull; Generated by <b>SmartBill AI</b> &bull; Zero-hallucination invoice engine
      </p>
    </div>

  </div>
</body>
</html>"""


# ══════════════════════════════════════════════
# STREAMLIT UI
# ══════════════════════════════════════════════

st.title("⚡ SmartBill AI")
st.caption(
    "Transform natural language requirements into validated, audit-ready invoices — "
    "with **zero price hallucination**."
)

# ── Sidebar settings ──
with st.sidebar:
    st.header("⚙️ Settings")
    # Auto-load from secrets if available, otherwise manual input
    default_key = st.secrets.get("general", {}).get("GEMINI_API_KEY", "")
    api_key = st.text_input(
        "Gemini API Key",
        value=default_key,
        type="password",
        help="Get your key at https://aistudio.google.com/apikey",
    )
    if default_key:
        st.success("🔑 API key loaded from secrets")
    tax_rate = st.slider(
        "Tax Rate (GST / VAT %)", min_value=0, max_value=28, value=18
    )
    currency_symbol = st.selectbox("Currency", ["₹", "$", "€", "£"])

    st.divider()
    st.subheader("📖 Service Catalog")
    st.dataframe(
        catalog_df[["service_id", "service_name", "unit_price", "category"]],
        use_container_width=True,
        hide_index=True,
    )
    st.caption(f"**{len(catalog_df)}** services loaded from `services_catalog.csv`")

    st.divider()
    st.subheader("📊 Invoice History")
    if "invoice_history" not in st.session_state:
        st.session_state.invoice_history = []
    if st.session_state.invoice_history:
        for inv in reversed(st.session_state.invoice_history):
            st.markdown(
                f"**{inv['number']}** — {inv['customer']}  \n"
                f"`{inv['currency']}{inv['total']:,.2f}` • {inv['date']}"
            )
    else:
        st.caption("No invoices generated yet.")


# ── Session state initialisation ──
for key, default in [
    ("extracted_data", None),
    ("invoice_approved", False),
    ("raw_json", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ────────────────────────────────
# Step 1 – Natural-Language Input
# ────────────────────────────────
st.subheader("1️⃣  Customer Requirement Input")

# Sample message presets
SAMPLE_MESSAGES = {
    "🏢 Tech Startup": (
        "Hi, this is Rajesh Sharma from Bangalore (rajesh@techcorp.in). "
        "We need 2 responsive landing pages built, 1 Figma UI/UX redesign, "
        "and 3 blog articles on Cloud AI. "
        "Please also include a mobile app penetration test. "
        "We need this delivered within 10 days."
    ),
    "🎨 Design Agency": (
        "Hello! I'm Priya Menon (priya@designhub.co). We need logo & branding "
        "for our new product launch, plus 5 social media wireframes in Figma. "
        "Timeline is 2 weeks."
    ),
    "📈 Marketing Team": (
        "Dear team, this is Alex Johnson (alex.j@globalretail.com). "
        "We require SEO optimisation for 3 regional websites, "
        "10 blog posts for our Q1 content calendar, and an API integration "
        "with our CRM system. Budget approval pending."
    ),
    "✏️ Custom Input": "",
}

preset_col1, preset_col2 = st.columns([1, 3])
with preset_col1:
    preset = st.selectbox("Quick presets", list(SAMPLE_MESSAGES.keys()))

default_text = SAMPLE_MESSAGES[preset]
user_input = st.text_area(
    "Customer Message / Project Scope:",
    value=default_text,
    height=130,
    placeholder="Paste or type any customer message here…",
)

if st.button("🚀 Process & Extract Entities", type="primary", use_container_width=True):
    if not api_key:
        st.error("⛔ Please enter a valid Gemini API Key in the sidebar.")
    elif not user_input.strip():
        st.warning("Please enter a customer message first.")
    else:
        with st.spinner("🤖 Analysing message and looking up catalog prices…"):
            try:
                parsed = extract_invoice_details(api_key, user_input)
                st.session_state.raw_json = parsed  # Save for debug view

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

                # Success summary
                matched = sum(1 for i in processed_items if i["Status"] == "MATCHED")
                flagged = sum(1 for i in processed_items if i["Status"] == "NEEDS_MANUAL_REVIEW")
                st.success(
                    f"✅ Extracted **{len(processed_items)}** items — "
                    f"**{matched}** matched, **{flagged}** flagged for review."
                )

            except json.JSONDecodeError:
                st.error(
                    "❌ Could not parse LLM response as JSON. "
                    "Please try again — the model may have added extra text."
                )
            except Exception as e:
                st.error(f"❌ Extraction failed: {e}")


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
            "📋 Project Notes (extracted by AI)",
            value=st.session_state.notes,
            disabled=True,
        )

    # Editable line-item grid
    edited_df = st.data_editor(
        st.session_state.items_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Service": st.column_config.TextColumn("Service Description", width="large"),
            "Unit Price": st.column_config.NumberColumn(
                format=f"{currency_symbol} %.2f", min_value=0.0
            ),
            "Quantity": st.column_config.NumberColumn(
                min_value=0.1, step=1.0
            ),
            "Status": st.column_config.SelectboxColumn(
                "Status",
                options=["MATCHED", "NEEDS_MANUAL_REVIEW"],
                disabled=True,
            ),
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
            f"⚠️ **{unpriced_count}** item(s) still have a price of 0. "
            "Please enter unit prices before approving."
        )

    c1, c2, c3 = st.columns(3)
    c1.metric("Subtotal", f"{currency_symbol} {subtotal:,.2f}")
    c2.metric(f"Tax ({tax_rate}%)", f"{currency_symbol} {tax_amount:,.2f}")
    c3.metric("💰 Grand Total", f"{currency_symbol} {grand_total:,.2f}")

    # Debug expander — shows raw LLM JSON
    with st.expander("🔍 View Raw LLM Extraction (for audit / debugging)"):
        st.json(st.session_state.raw_json)

    if st.button("✅ Approve & Generate Final Invoice", type="primary", use_container_width=True):
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

    invoice_number = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    today_str = datetime.now().strftime("%d %b %Y")

    html_invoice = build_invoice_html(
        invoice_number=invoice_number,
        date_str=today_str,
        customer_name=st.session_state.customer_name,
        customer_email=st.session_state.customer_email,
        notes=st.session_state.notes,
        items_df=st.session_state.final_df,
        subtotal=st.session_state.subtotal,
        tax_rate=tax_rate,
        tax_amount=st.session_state.tax_amount,
        grand_total=st.session_state.grand_total,
        currency_symbol=currency_symbol,
    )

    # Render preview
    st.components.v1.html(html_invoice, height=600, scrolling=True)

    # Download buttons
    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            label="📥 Download HTML Invoice",
            data=html_invoice,
            file_name=f"{invoice_number}.html",
            mime="text/html",
            use_container_width=True,
        )
    with dl_col2:
        # JSON export for programmatic use / audit trail
        invoice_data = {
            "invoice_number": invoice_number,
            "date": today_str,
            "customer_name": st.session_state.customer_name,
            "customer_email": st.session_state.customer_email,
            "notes": st.session_state.notes,
            "items": st.session_state.final_df[
                ["Service", "Quantity", "Unit Price", "Line Total"]
            ].to_dict(orient="records"),
            "subtotal": st.session_state.subtotal,
            "tax_rate": tax_rate,
            "tax_amount": st.session_state.tax_amount,
            "grand_total": st.session_state.grand_total,
            "currency": currency_symbol,
        }
        st.download_button(
            label="📋 Download JSON (Audit Log)",
            data=json.dumps(invoice_data, indent=2, default=str),
            file_name=f"{invoice_number}.json",
            mime="application/json",
            use_container_width=True,
        )

    # Record in history
    hist_entry = {
        "number": invoice_number,
        "customer": st.session_state.customer_name,
        "total": st.session_state.grand_total,
        "currency": currency_symbol,
        "date": today_str,
    }
    if not any(h["number"] == invoice_number for h in st.session_state.invoice_history):
        st.session_state.invoice_history.append(hist_entry)

    st.success(f"🎉 Invoice **{invoice_number}** generated successfully!")

    # New invoice button
    if st.button("🔄 Create New Invoice"):
        st.session_state.extracted_data = None
        st.session_state.invoice_approved = False
        st.session_state.raw_json = None
        st.rerun()
