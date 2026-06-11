import streamlit as st
import pdfplumber
import re

# Extract Invoice Data
def extract_invoice_data(file):
    text = ""

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t

    data = {}

    # Invoice number
    match = re.search(r"Invoice\s*No[:\-]?\s*(\S+)", text, re.IGNORECASE)
    if match:
        data["invoice_no"] = match.group(1)

    # Total (multiple formats)
    patterns = [
        r"Total\s*Amount[:\-]?\s*([\d,\.]+)",
        r"Grand\s*Total[:\-]?\s*([\d,\.]+)",
        r"Invoice\s*Value[:\-]?\s*([\d,\.]+)",
        r"TOTAL\s+([\d,\.]+)"
    ]

    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            try:
                data["total"] = float(m.group(1).replace(",", ""))
                break
            except:
                pass

    return data


# Extract Packing Data
def extract_packing_data(file):
    text = ""

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t

    data = {}

    g = re.search(r"Gross\s*Weight[:\-]?\s*([\d\.]+)", text, re.IGNORECASE)
    if g:
        data["gross_weight"] = float(g.group(1))

    n = re.search(r"Net\s*Weight[:\-]?\s*([\d\.]+)", text, re.IGNORECASE)
    if n:
        data["net_weight"] = float(n.group(1))

    return data


# Validation
def validate(invoice, packing):
    errors = []
    comparison = []

    if not invoice.get("invoice_no"):
        errors.append("❌ Invoice Number not found")

    if not invoice.get("total"):
        errors.append("⚠️ Total value not detected from invoice")

    if packing.get("net_weight") and packing.get("gross_weight"):
        if packing["net_weight"] > packing["gross_weight"]:
            errors.append("❌ Net weight > Gross weight")

    comparison.append({
        "Field": "Invoice Number",
        "Value": invoice.get("invoice_no", "Not Found")
    })

    comparison.append({
        "Field": "Total Value",
        "Value": invoice.get("total", "Not Found")
    })

    return errors, comparison


# Report
def generate_report(errors, comparison):
    txt = "EXPORT REPORT\n\n"

    txt += "Errors:\n"
    for e in errors:
        txt += f"- {e}\n"

    txt += "\nData:\n"
    for c in comparison:
        txt += f"{c['Field']} : {c['Value']}\n"

    return txt


# UI
st.title("📦 Export Checklist Verifier")

invoice_file = st.file_uploader("Upload Invoice PDF", type=["pdf"])
packing_file = st.file_uploader("Upload Packing List PDF", type=["pdf"])
checklist_file = st.file_uploader("Upload Checklist", type=["pdf", "xlsx"])

if st.button("Verify Documents"):

    if invoice_file and packing_file and checklist_file:

        invoice = extract_invoice_data(invoice_file)
        packing = extract_packing_data(packing_file)

        errors, comparison = validate(invoice, packing)

        st.subheader("Errors")
        if errors:
            for e in errors:
                st.error(e)
        else:
            st.success("No errors")

        st.subheader("Data Extracted")
