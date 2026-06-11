import streamlit as st
import pdfplumber
import pandas as pd
import re
import io

st.set_page_config(
    page_title="Export Checklist Verifier",
    page_icon="🚢",
    layout="wide",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #F0F4F8; }

.app-header {
    background: linear-gradient(135deg, #0F2D52 0%, #1A5276 100%);
    color: white;
    padding: 1.5rem 2rem;
    border-radius: 12px;
    margin-bottom: 1.5rem;
}
.app-header h1 { margin: 0; font-size: 1.6rem; font-weight: 700; }
.app-header p  { margin: 0; font-size: 0.85rem; opacity: 0.75; }

.section-head {
    background: #1A5276;
    color: white;
    padding: 0.55rem 1rem;
    border-radius: 6px 6px 0 0;
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}

.tile { border-radius: 10px; padding: 1rem 1.2rem; text-align: center; }
.tile-matched  { background: #D5F5E3; border: 1px solid #27AE60; }
.tile-mismatch { background: #FEF9E7; border: 1px solid #F39C12; }
.tile-missing  { background: #FADBD8; border: 1px solid #E74C3C; }
.tile h2 { margin: 0; font-size: 2rem; font-weight: 700; }
.tile p  { margin: 0.2rem 0 0; font-size: 0.8rem; font-weight: 500; color: #444; }

.critical-box {
    background: #FDF2F8;
    border: 1.5px solid #C0392B;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin-top: 1rem;
}
.critical-box h4 { margin: 0 0 0.5rem; color: #C0392B; font-size: 0.9rem; }
.critical-item { font-size: 0.82rem; color: #333; margin: 4px 0; }
.raw-text { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; white-space: pre-wrap; color: #555; }
</style>
""", unsafe_allow_html=True)


def extract_text(uploaded_file):
    if uploaded_file is None:
        return ""
    try:
        with pdfplumber.open(io.BytesIO(uploaded_file.read())) as pdf:
            pages = []
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    pages.append(t)
        return "\n".join(pages)
    except Exception as e:
        st.warning(f"Could not read PDF: {e}")
        return ""


def find(patterns, text):
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if val and val not in ("&", "-", "–", "/", ""):
                return val
    return ""


def extract_fields(text):
    t = text
    fields = {}

    fields["Exporter Name"] = find([
        r"(?:exporter|shipper|seller|from)[:\s]+([A-Z][A-Z0-9 &.,\-]+(?:LTD|PVT|LLC|INC|CORP|CO\.?)?)",
        r"^([A-Z][A-Z0-9 &.,\-]{5,50}(?:LTD|PVT|LLC|INC|CORP)\.?)",
    ], t)

    fields["IEC"] = find([
        r"IEC\s*[:\-#]?\s*([A-Z0-9]{10})",
        r"Import\s+Export\s+Code[:\s]+([A-Z0-9]{10})",
        r"\bIEC\b\D{0,5}([A-Z0-9]{10})",
    ], t)

    fields["GSTIN"] = find([
        r"GSTIN?\s*[:\-#]?\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})",
        r"GST\s+No\.?\s*[:\-]?\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})",
    ], t)

    fields["PAN"] = find([
        r"PAN\s*[:\-#]?\s*([A-Z]{5}[0-9]{4}[A-Z]{1})",
    ], t)

    fields["AD Code"] = find([
        r"AD\s*Code\s*[:\-]?\s*([0-9]{7,14})",
        r"Authorised\s+Dealer\s*[:\-]?\s*([0-9]{7,14})",
    ], t)

    fields["Invoice No"] = find([
        r"Invoice\s*(?:No|Number|#)\s*[:\-]?\s*([A-Z0-9/\-]{3,25})",
        r"Inv\.?\s*No\.?\s*[:\-]?\s*([A-Z0-9/\-]{3,25})",
    ], t)

    fields["Invoice Date"] = find([
        r"Invoice\s+Date\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
        r"Date\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
        r"Dated?\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
    ], t)

    fields["Buyer / Consignee"] = find([
        r"(?:buyer|consignee|bill\s+to|sold\s+to)[:\s]+([A-Z][A-Z0-9 &.,\-]{4,60})",
    ], t)

    fields["Buyer PO No"] = find([
        r"(?:P\.?O\.?\s*(?:No|Number|#)|Purchase\s+Order)\s*[:\-]?\s*([A-Z0-9/\-]{3,25})",
    ], t)

    fields["Country of Origin"] = find([
        r"Country\s+of\s+Origin\s*[:\-]?\s*([A-Za-z ]{3,30})",
    ], t)

    fields["Country of Destination"] = find([
        r"Country\s+of\s+(?:Destination|Final\s+Destination)\s*[:\-]?\s*([A-Za-z ]{3,30})",
        r"(?:Destination|Final\s+Destination)\s+Country\s*[:\-]?\s*([A-Za-z ]{3,30})",
    ], t)

    fields["Port of Loading"] = find([
        r"Port\s+of\s+Loading\s*[:\-]?\s*([A-Za-z ,()]{3,40})",
        r"Loading\s+Port\s*[:\-]?\s*([A-Za-z ,()]{3,40})",
        r"POL\s*[:\-]?\s*([A-Za-z ,()]{3,40})",
    ], t)

    fields["Port of Discharge"] = find([
        r"Port\s+of\s+(?:Discharge|Destination)\s*[:\-]?\s*([A-Za-z ,()]{3,40})",
        r"POD\s*[:\-]?\s*([A-Za-z ,()]{3,40})",
    ], t)

    fields["Delivery Terms (Incoterm)"] = find([
        r"\b(FOB|CIF|CFR|EXW|DAP|DDP|FCA|CPT|CIP|DAT)\b(?:\s+[A-Za-z, ]{2,30})?",
    ], t)

    fields["Payment Terms"] = find([
        r"Payment\s+Terms?\s*[:\-]?\s*([A-Za-z0-9 ,/\-]{3,50})",
        r"(?:T\/T|L\/C|DP|DA|CAD|Advance|Sight)\b(.{0,30})",
    ], t)

    fields["Mode of Transport"] = find([
        r"(?:Mode\s+of\s+)?Transport(?:ation)?\s*[:\-]?\s*([A-Za-z ]{3,25})",
        r"\b(Sea|Air|Road|Rail|Multimodal)\b",
    ], t)

    fields["Marks & Nos"] = find([
        r"Marks?\s*(?:&|and)\s*No[s.]?\s*[:\-]?\s*([^\n]{3,60})",
    ], t)

    fields["Currency"] = find([
        r"\b(USD|EUR|GBP|INR|AED|JPY|CNY|SGD)\b",
        r"Currency\s*[:\-]?\s*([A-Z]{3})",
    ], t)

    fields["Total Invoice Value"] = find([
        r"(?:Total|Grand\s+Total|Invoice\s+Value|Amount\s+Due)\s*[:\-]?\s*(?:[A-Z]{0,3}\s*)?([0-9,]+\.?[0-9]{0,2})",
    ], t)

    fields["FOB Value"] = find([
        r"FOB\s+Value\s*[:\-]?\s*(?:[A-Z]{0,3}\s*)?([0-9,]+\.?[0-9]{0,2})",
        r"FOB\s+Amount\s*[:\-]?\s*(?:[A-Z]{0,3}\s*)?([0-9,]+\.?[0-9]{0,2})",
    ], t)

    fields["Gross Weight"] = find([
        r"Gross\s+(?:Weight|Wt\.?)\s*[:\-]?\s*([0-9,]+\.?[0-9]{0,3}\s*(?:KGS?|MT|LBS?|KG)?)",
        r"G\.?\s*W\.?\s*[:\-]?\s*([0-9,]+\.?[0-9]{0,3}\s*(?:KGS?|MT|LBS?|KG)?)",
    ], t)

    fields["Net Weight"] = find([
        r"Net\s+(?:Weight|Wt\.?)\s*[:\-]?\s*([0-9,]+\.?[0-9]{0,3}\s*(?:KGS?|MT|LBS?|KG)?)",
        r"N\.?\s*W\.?\s*[:\-]?\s*([0-9,]+\.?[0-9]{0,3}\s*(?:KGS?|MT|LBS?|KG)?)",
    ], t)

    fields["No. of Packages"] = find([
        r"(?:No\.?\s+of\s+)?(?:Packages?|Cartons?|Boxes|Cases)\s*[:\-]?\s*([0-9]+)",
        r"Total\s+(?:Cartons?|Packages?)\s*[:\-]?\s*([0-9]+)",
    ], t)

    fields["LUT / Bond"] = find([
        r"LUT\s+(?:No\.?|Number|#)?\s*[:\-]?\s*([A-Z0-9/\-]{4,30})",
        r"Letter\s+of\s+Undertaking\s*[:\-]?\s*([A-Z0-9/\-]{4,30})",
    ], t)

    fields["DBK / Drawback"] = find([
        r"(?:DBK|Drawback)\s*(?:Scheme|No\.?)?\s*[:\-]?\s*([A-Za-z0-9 /\-]{2,30})",
    ], t)

    fields["RoDTEP"] = find([
        r"RoDTEP\s*(?:Rate|%|No\.?)?\s*[:\-]?\s*([A-Za-z0-9 .%/\-]{2,20})",
    ], t)

    fields["IGST Refund"] = find([
        r"IGST\s*(?:Refund|Paid|Amount)?\s*[:\-]?\s*(?:Rs\.?\s*)?([0-9,]+\.?[0-9]{0,2})",
    ], t)

    fields["HSN Code"] = find([
        r"HSN\s*(?:Code|No\.?)?\s*[:\-]?\s*([0-9]{4,8})",
        r"HS\s+Code\s*[:\-]?\s*([0-9]{4,8})",
    ], t)

    fields["Bank Name"] = find([
        r"Bank\s*[:\-]?\s*([A-Za-z ]{3,50}(?:Bank|BANK))",
        r"(?:Banker|Through\s+Bank)\s*[:\-]?\s*([A-Za-z ]{3,50})",
    ], t)

    return {k: v.strip() if v else "" for k, v in fields.items()}


CRITICAL_FIELDS = {
    "IEC", "GSTIN", "Invoice No", "Invoice Date",
    "Total Invoice Value", "FOB Value", "HSN Code",
    "Port of Loading", "Port of Discharge",
    "Country of Destination", "Gross Weight",
}

def normalise(val):
    return re.sub(r"[\s,./\-]", "", val).upper()

def compare(inv_val, pack_val, chk_val):
    vals = [normalise(v) for v in (inv_val, pack_val, chk_val) if v]
    if not vals:
        return "❌ Missing"
    if len(set(vals)) == 1:
        return "✅ Match"
    return "⚠️ Mismatch"

def build_comparison_table(inv, pack, chk):
    rows = []
    for field in inv.keys():
        i = inv.get(field, "")
        p = pack.get(field, "")
        c = chk.get(field, "")
        status = compare(i, p, c)
        rows.append({
            "Field": field,
            "Invoice": i or "—",
            "Packing List": p or "—",
            "Checklist": c or "—",
            "Status": status,
        })
    return pd.DataFrame(rows)


STATUS_COLOR = {
    "✅ Match":    "background-color:#D5F5E3;color:#1E8449",
    "⚠️ Mismatch": "background-color:#FEF9E7;color:#B7770D",
    "❌ Missing":  "background-color:#FADBD8;color:#C0392B",
}

def style_row(row):
    style = STATUS_COLOR.get(row["Status"], "")
    return [""] * (len(row) - 1) + [style]

SECTIONS = {
    "🏭 Exporter & Registration":  ["Exporter Name", "IEC", "GSTIN", "PAN", "AD Code", "Bank Name"],
    "📄 Invoice Reference":        ["Invoice No", "Invoice Date", "Buyer / Consignee", "Buyer PO No"],
    "🚢 Shipment Details":         ["Country of Origin", "Country of Destination",
                                    "Port of Loading", "Port of Discharge",
                                    "Delivery Terms (Incoterm)", "Payment Terms",
                                    "Mode of Transport", "Marks & Nos"],
    "💰 Financial Details":        ["Currency", "Total Invoice Value", "FOB Value",
                                    "Gross Weight", "Net Weight", "No. of Packages",
                                    "HSN Code"],
    "📋 Export Scheme / Duty":     ["LUT / Bond", "DBK / Drawback", "RoDTEP", "IGST Refund"],
}

def render_section(title, fields, df):
    subset = df[df["Field"].isin(fields)]
    if subset.empty:
        return
    st.markdown(f'<div class="section-head">{title}</div>', unsafe_allow_html=True)
    st.dataframe(
        subset.style.apply(style_row, axis=1),
        use_container_width=True,
        hide_index=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)


# ── APP STARTS HERE ──

st.markdown("""
<div class="app-header">
  <h1>🚢 Export Checklist Verifier</h1>
  <p>Compare Invoice · Packing List · Export Checklist — field by field</p>
</div>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    inv_file  = st.file_uploader("📄 Commercial Invoice (PDF)", type="pdf", key="inv")
with col2:
    pack_file = st.file_uploader("📦 Packing List (PDF)", type="pdf", key="pack")
with col3:
    chk_file  = st.file_uploader("✅ Export Checklist / SB (PDF)", type="pdf", key="chk")

st.markdown("---")

if not any([inv_file, pack_file, chk_file]):
    st.info("Upload at least one document above to begin verification.")
    st.stop()

with st.spinner("Reading documents…"):
    inv_text  = extract_text(inv_file)  if inv_file  else ""
    pack_text = extract_text(pack_file) if pack_file else ""
    chk_text  = extract_text(chk_file)  if chk_file  else ""

    inv_data  = extract_fields(inv_text)
    pack_data = extract_fields(pack_text)
    chk_data  = extract_fields(chk_text)

    df = build_comparison_table(inv_data, pack_data, chk_data)

matched   = (df["Status"] == "✅ Match").sum()
mismatch  = (df["Status"] == "⚠️ Mismatch").sum()
missing   = (df["Status"] == "❌ Missing").sum()
total     = len(df)

t1, t2, t3, t4 = st.columns(4)
with t1:
    st.markdown(f'<div class="tile tile-matched"><h2>{matched}</h2><p>✅ Matched</p></div>', unsafe_allow_html=True)
with t2:
    st.markdown(f'<div class="tile tile-mismatch"><h2>{mismatch}</h2><p>⚠️ Mismatched</p></div>', unsafe_allow_html=True)
with t3:
    st.markdown(f'<div class="tile tile-missing"><h2>{missing}</h2><p>❌ Missing</p></div>', unsafe_allow_html=True)
with t4:
    pct = int(matched / total * 100) if total else 0
    st.metric("Completeness", f"{pct}%", delta=f"{total} fields checked")

st.markdown("---")

critical_issues = df[
    (df["Field"].isin(CRITICAL_FIELDS)) &
    (df["Status"] != "✅ Match")
]
if not critical_issues.empty:
    lines = ""
    for _, row in critical_issues.iterrows():
        icon = "⚠️" if row["Status"] == "⚠️ Mismatch" else "❌"
        lines += f'<div class="critical-item">{icon} <b>{row["Field"]}</b> — {row["Status"]}'
        if row["Status"] == "⚠️ Mismatch":
            lines += f' &nbsp;|&nbsp; Invoice: <code>{row["Invoice"]}</code> Packing: <code>{row["Packing List"]}</code> Checklist: <code>{row["Checklist"]}</code>'
        lines += '</div>'
    st.markdown(f"""
    <div class="critical-box">
        <h4>🚨 Critical Issues — Resolve before export clearance</h4>
        {lines}
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
else:
    st.success("🎉 No critical issues found. All mandatory fields match.")

for section_title, field_list in SECTIONS.items():
    render_section(section_title, field_list, df)

with st.expander("🔍 View extracted raw text (debug)"):
    tabs = st.tabs(["Invoice", "Packing List", "Checklist"])
    for tab, txt in zip(tabs, [inv_text, pack_text, chk_text]):
        with tab:
            if txt:
                st.markdown(f'<div class="raw-text">{txt[:4000]}</div>', unsafe_allow_html=True)
            else:
                st.caption("No document uploaded.")

st.markdown("---")
csv = df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="⬇️ Download Full Report (CSV)",
    data=csv,
    file_name="export_verification_report.csv",
    mime="text/csv",
)
