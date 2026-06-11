import streamlit as st
import pdfplumber
import re

# -----------------------------
# Extract text from PDF
# -----------------------------
def extract_text(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text


# -----------------------------
# Generic Field Finder
# -----------------------------
def find_field(patterns, text):
    for p in patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


# -----------------------------
# Extract Invoice Data
# -----------------------------
def extract_invoice_data(text):
    data = {}

    data["invoice_no"] = find_field([
        r"Invoice\s*No[:\-]?\s*(\S+)"
    ], text)

    data["invoice_date"] = find_field([
        r"Date[:\-]?\s*(\S+)"
    ], text)

    data["gstin"] = find_field([
        r"GSTIN[:\-]?\s*(\S+)"
    ], text)

    data["iec"] = find_field([
        r"IEC[:\-]?\s*(\S+)"
    ], text)

    data["country_origin"] = find_field([
        r"Country\s*of\s*Origin[:\-]?\s*(.+)"
    ], text)

    data["total"] = find_field([
        r"Total\s*Amount[:\-]?\s*([\d,\.]+)",
        r"Grand\s*Total[:\-]?\s*([\d,\.]+)"
    ], text)

    return data


# -----------------------------
# Extract Packing Data
# -----------------------------
def extract_packing_data(text):
    data = {}

    data["gross_weight"] = find_field([
        r"Gross\s*Weight[:\-]?\s*([\d\.]+)"
    ], text)

    data["net_weight"] = find_field([
        r"Net\s*Weight[:\-]?\s*([\d\.]+)"
    ], text)

    data["cartons"] = find_field([
        r"Cartons[:\-]?\s*(\d+)"
    ], text)

    return data


# -----------------------------
# Validation Engine
# -----------------------------
def validate(invoice, packing):

    results = []

    def check(field_name, value):
        if value:
            return {"Field": field_name, "Status": "✅ Matched", "Value": value}
        else:
            return {"Field": field_name, "Status": "⚠️ Missing", "Value": "Not Found"}

    results.append(check("Invoice Number", invoice.get("invoice_no")))
    results.append(check("Invoice Date", invoice.get("invoice_date")))
    results.append(check("GSTIN", invoice.get("gstin")))
    results.append(check("IEC", invoice.get("iec")))
    results.append(check("Country of Origin", invoice.get("country_origin")))
    results.append(check("Total Value", invoice.get("total")))

    results.append(check("Gross Weight", packing.get("gross_weight")))
    results.append(check("Net Weight", packing.get("net_weight")))
    results.append(check("Cartons", packing.get("cartons")))

    return results


# -----------------------------
# Summary Generator
# -----------------------------
def generate_summary(results):
    matched = sum(1 for r in results if "✅" in r["Status"])
    missing = sum(1 for r in results if "⚠️" in r["Status"])
    mismatch = sum(1 for r in results if "❌" in r["Status"])

    return matched, missing, mismatch


# -----------------------------
# UI
# -----------------------------
st.title("📦 Export Checklist Verifier")

invoice_file = st.file_uploader("Upload Invoice PDF", type=["pdf"])
packing_file = st.file_uploader("Upload Packing List PDF", type=["pdf"])
checklist_file = st.file_uploader("Upload Checklist", type=["pdf", "xlsx"])

if st.button("Verify Documents"):

    if invoice_file and packing_file and checklist_file:

        inv_text = extract_text(invoice_file)
        pack_text = extract_text(packing_file)

        invoice = extract_invoice_data(inv_text)
        packing = extract_packing_data(pack_text)

        results = validate(invoice, packing)

        st.subheader("📊 Field Validation")

        for r in results:
            st.write(r)

        matched, missing, mismatch = generate_summary(results)

        st.subheader("📈 Summary")
        st.success(f"✅ Matched: {matched}")
        st.warning(f"⚠️ Missing: {missing}")
        st.error(f"❌ Mismatch: {mismatch}")

        # Critical warning
        if missing > 0 or mismatch > 0:
            st.error("🚨 Critical issues detected — fix before export clearance")

    else:
        st.warning("Upload all 3 documents")
``
