import streamlit as st
import pdfplumber
import re

# -----------------------------
# Extract Invoice Data
# -----------------------------
def extract_invoice_data(file):
    text = ""

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    data = {}

    # Try multiple patterns for invoice number
    inv_patterns = [
        r"Invoice\s*No[:\-]?\s*(\S+)",
        r"Inv\s*No[:\-]?\s*(\S+)",
        r"Invoice\s*Number[:\-]?\s*(\S+)"
    ]

    for pattern in inv_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data["invoice_no"] = match.group(1)
            break

    # Try multiple patterns for total value
    total_patterns = [
        r"Total\s*Amount[:\-]?\s*([\d,\.]+)",
        r"Grand\s*Total[:\-]?\s*([\d,\.]+)",
        r"Invoice\s*Value[:\-]?\s*([\d,\.]+)",
        r"TOTAL\s+([\d,\.]+)",
        r"Total[:\-]?\s*([\d,\.]+)"
    ]

    for pattern in total_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                data["total"] = float(match.group(1).replace(",", ""))
                break
            except:
                pass

    return data


# -----------------------------
# Extract Packing Data
# -----------------------------
def extract_packing_data(file):
    text = ""

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    data = {}

    gross = re.search(r"Gross\s*Weight[:\-]?\s*([\d\.]+)", text, re.IGNORECASE)
    if gross:
        data["gross_weight"] = float(gross.group(1))

    net = re.search(r"Net\s*Weight[:\-]?\s*([\d\.]+)", text, re.IGNORECASE)
    if net:
        data["net_weight"] = float(net.group(1))

    return data


# -----------------------------
# Validation Logic
# -----------------------------
def validate(invoice, packing):
    errors = []
    comparison = []

    # Invoice checks
    if not invoice.get("invoice_no"):
        errors.append("❌ Invoice Number not detected")

    if not invoice.get("total"):
