import pdfplumber
import re

def extract_invoice_data(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""

    data = {}

    match = re.search(r"Invoice\s*No[:\-]?\s*(\S+)", text)
    if match:
        data["invoice_no"] = match.group(1)

    total_match = re.search(r"Total[:\-]?\s*([\d,\.]+)", text)
    if total_match:
        data["total"] = float(total_match.group(1).replace(",", ""))

    return data


def extract_packing_data(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""

    data = {}

    gw_match = re.search(r"Gross\s*Weight[:\-]?\s*([\d\.]+)", text)
    if gw_match:
        data["gross_weight"] = float(gw_match.group(1))

    nw_match = re.search(r"Net\s*Weight[:\-]?\s*([\d\.]+)", text)
    if nw_match:
        data["net_weight"] = float(nw_match.group(1))

    return data
