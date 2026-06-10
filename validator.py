import pdfplumber

def validate(invoice, packing):
    errors = []
    comparison = []

    # Invoice check
    if not invoice.get("invoice_no"):
        errors.append({
            "field": "Invoice No",
            "issue": "Missing",
            "source": "Invoice"
        })

    # Total check
    if not invoice.get("total"):
        errors.append({
            "field": "Total",
            "issue": "Missing",
            "source": "Invoice"
        })

    # Add comparison row
    comparison.append({
        "field": "Invoice Number",
        "invoice": invoice.get("invoice_no", "N/A"),
        "packing": "N/A",
        "status": "✅" if invoice.get("invoice_no") else "❌"
    })

    return errors, comparison

