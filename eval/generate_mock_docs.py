import os
import sys
import json
from fpdf import FPDF
from typing import Dict, Any

class RobustFPDF(FPDF):
    def cell(self, w=None, h=None, txt=None, text=None, *args, **kwargs):
        val = text if text is not None else txt
        if val is not None:
            val = str(val).replace("\u2014", "-").replace("\u2013", "-").replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
            val = val.encode("latin-1", errors="replace").decode("latin-1")
        if text is not None:
            kwargs["text"] = val
        else:
            kwargs["txt"] = val
        return super().cell(w, h, *args, **kwargs)

def generate_prescription(data: Dict[str, Any], filepath: str) -> None:
    """Generate a mock prescription PDF matching the structure in sample_documents_guide.md."""
    pdf = RobustFPDF()
    pdf.add_page()
    
    # Hospital/Doctor Header
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(190, 8, txt=data.get("doctor_name", "Dr. Arun Sharma"), ln=True, align="C")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(190, 5, txt="MBBS, MD (Internal Medicine)", ln=True, align="C")
    pdf.cell(190, 5, txt=f"Registration No: {data.get('doctor_registration', 'KA/45678/2015')}", ln=True, align="C")
    pdf.cell(190, 5, txt=data.get("hospital_name", "City Medical Centre, Bengaluru"), ln=True, align="C")
    pdf.line(10, 36, 200, 36)
    pdf.ln(10)
    
    # Patient info
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(30, 6, txt="Patient Name:")
    pdf.set_font("helvetica", "", 11)
    pdf.cell(100, 6, txt=data.get("patient_name", "Rajesh Kumar"))
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(20, 6, txt="Date:")
    pdf.set_font("helvetica", "", 11)
    pdf.cell(40, 6, txt=data.get("date", "2024-11-01"), ln=True)
    
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(30, 6, txt="Age / Gender:")
    pdf.set_font("helvetica", "", 11)
    pdf.cell(160, 6, txt=f"{data.get('patient_age', '39')} years / {data.get('patient_gender', 'M')}", ln=True)
    pdf.line(10, 55, 200, 55)
    pdf.ln(8)
    
    # Diagnosis
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(190, 6, txt="Diagnosis:", ln=True)
    pdf.set_font("helvetica", "I", 11)
    pdf.cell(190, 6, txt=data.get("diagnosis", "Viral Fever"), ln=True)
    pdf.ln(5)
    
    # Treatment if present
    if "treatment" in data and data["treatment"]:
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(190, 6, txt="Treatment / Therapy Plan:", ln=True)
        pdf.set_font("helvetica", "", 11)
        pdf.cell(190, 6, txt=data["treatment"], ln=True)
        pdf.ln(5)
        
    # Medicines Rx
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(190, 8, txt="Rx:", ln=True)
    pdf.set_font("helvetica", "", 11)
    medicines = data.get("medicines", [])
    for idx, med in enumerate(medicines, 1):
        if isinstance(med, dict):
            med_str = f"{med.get('name')} - {med.get('dosage')} ({med.get('frequency')} x {med.get('duration')})"
        else:
            med_str = str(med)
        pdf.cell(190, 6, txt=f"{idx}. {med_str}", ln=True)
        
    # Tests ordered
    if "tests_ordered" in data and data["tests_ordered"]:
        pdf.ln(5)
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(190, 6, txt="Investigations / Tests Ordered:", ln=True)
        pdf.set_font("helvetica", "", 11)
        tests = data["tests_ordered"]
        tests_list = tests if isinstance(tests, list) else [tests]
        for t in tests_list:
            pdf.cell(190, 6, txt=f"- {t}", ln=True)
            
    # Signatures
    pdf.ln(20)
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(120, 6, txt="")
    pdf.cell(70, 6, txt="[Authorized Signature & Stamp]", ln=True, align="R")
    
    pdf.output(filepath)

def generate_hospital_bill(data: Dict[str, Any], filepath: str) -> None:
    """Generate a mock hospital bill PDF."""
    pdf = RobustFPDF()
    pdf.add_page()
    
    # Header
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(190, 8, txt=data.get("hospital_name", "CITY MEDICAL CENTRE"), ln=True, align="C")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(190, 5, txt="12 MG Road, Bengaluru - 560001", ln=True, align="C")
    pdf.cell(190, 5, txt="GSTIN: 29XXXXX1234X1ZX | Ph: 080-XXXXXXXX", ln=True, align="C")
    pdf.line(10, 32, 200, 32)
    pdf.ln(8)
    
    # Bill details
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(190, 6, txt="BILL / RECEIPT", ln=True, align="C")
    pdf.ln(3)
    
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(25, 5, txt="Bill Number:")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(70, 5, txt=data.get("bill_number", "CMC/2024/08321"))
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(25, 5, txt="Date:")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(70, 5, txt=data.get("date", "2024-11-01"), ln=True)
    
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(25, 5, txt="Patient Name:")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(165, 5, txt=data.get("patient_name", "Rajesh Kumar"), ln=True)
    pdf.line(10, 58, 200, 58)
    pdf.ln(5)
    
    # Table headers
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(140, 6, txt="DESCRIPTION", border=1)
    pdf.cell(50, 6, txt="AMOUNT (INR)", border=1, ln=True, align="R")
    
    # Line items
    pdf.set_font("helvetica", "", 10)
    line_items = data.get("line_items", [])
    for item in line_items:
        pdf.cell(140, 6, txt=item.get("description", "Item"), border=1)
        pdf.cell(50, 6, txt=f"{item.get('amount', 0.0):,.2f}", border=1, ln=True, align="R")
        
    # Totals
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(140, 6, txt="Subtotal", border=1, align="R")
    pdf.cell(50, 6, txt=f"{data.get('total', 0.0):,.2f}", border=1, ln=True, align="R")
    
    pdf.cell(140, 6, txt="GST (0% on medical)", border=1, align="R")
    pdf.cell(50, 6, txt="0.00", border=1, ln=True, align="R")
    
    pdf.cell(140, 6, txt="Total Amount Payable", border=1, align="R")
    pdf.cell(50, 6, txt=f"{data.get('total', 0.0):,.2f}", border=1, ln=True, align="R")
    
    pdf.ln(10)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(100, 5, txt=f"Payment Mode: {data.get('payment_mode', 'UPI / Cash')}")
    pdf.cell(90, 5, txt="Authorized Signatory Stamp", ln=True, align="R")
    
    pdf.output(filepath)

def generate_lab_report(data: Dict[str, Any], filepath: str) -> None:
    """Generate a mock diagnostic lab report PDF."""
    pdf = RobustFPDF()
    pdf.add_page()
    
    # Header
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(190, 8, txt=data.get("lab_name", "PRECISION DIAGNOSTICS PVT LTD"), ln=True, align="C")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(190, 5, txt="NABL Accredited Laboratory | Lab ID: KA-NABL-1234", ln=True, align="C")
    pdf.cell(190, 5, txt="45 Jayanagar, Bengaluru | Ph: 080-XXXXXXXX", ln=True, align="C")
    pdf.line(10, 32, 200, 32)
    pdf.ln(8)
    
    # Patient Info
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(30, 5, txt="Patient Name:")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(100, 5, txt=data.get("patient_name", "Rajesh Kumar"))
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(30, 5, txt="Sample Date:")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(30, 5, txt=data.get("sample_date", "2024-11-01"), ln=True)
    
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(30, 5, txt="Ref Doctor:")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(100, 5, txt=data.get("referring_doctor", "Dr. Arun Sharma"))
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(30, 5, txt="Report Date:")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(30, 5, txt=data.get("report_date", "2024-11-01"), ln=True)
    pdf.line(10, 52, 200, 52)
    pdf.ln(5)
    
    # Table headers
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(70, 6, txt="TEST NAME", border=1)
    pdf.cell(40, 6, txt="RESULT", border=1, align="C")
    pdf.cell(40, 6, txt="UNIT", border=1, align="C")
    pdf.cell(40, 6, txt="REFERENCE RANGE", border=1, ln=True, align="C")
    
    # Report Results
    pdf.set_font("helvetica", "", 10)
    tests = data.get("tests", [])
    if not tests and "test_name" in data:
        # Construct single test from test_name
        tests = [{"name": data["test_name"], "result": "NEGATIVE", "unit": "-", "normal_range": "NEGATIVE"}]
        
    for t in tests:
        pdf.cell(70, 6, txt=t.get("name", "Test"), border=1)
        pdf.cell(40, 6, txt=t.get("result", ""), border=1, align="C")
        pdf.cell(40, 6, txt=t.get("unit", ""), border=1, align="C")
        pdf.cell(40, 6, txt=t.get("normal_range", ""), border=1, ln=True, align="C")
        
    # Signature
    pdf.ln(20)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(120, 5, txt="Pathologist: Dr. Meena Pillai, MD (Pathology)")
    pdf.cell(70, 5, txt="[Signature & Stamp]", ln=True, align="R")
    
    pdf.output(filepath)

def generate_pharmacy_bill(data: Dict[str, Any], filepath: str) -> None:
    """Generate a mock pharmacy bill PDF."""
    pdf = RobustFPDF()
    pdf.add_page()
    
    # Header
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(190, 8, txt=data.get("pharmacy_name", "HEALTH FIRST PHARMACY"), ln=True, align="C")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(190, 5, txt="Drug Lic. No: KA-BLR-XXXX | GSTIN: 29XXXXX", ln=True, align="C")
    pdf.cell(190, 5, txt="22 Brigade Road, Bengaluru - 560001", ln=True, align="C")
    pdf.line(10, 32, 200, 32)
    pdf.ln(8)
    
    # Bill Details
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(25, 5, txt="Bill Number:")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(70, 5, txt=data.get("bill_number", "HFP-24-09821"))
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(25, 5, txt="Date:")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(70, 5, txt=data.get("date", "2024-11-01"), ln=True)
    
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(25, 5, txt="Patient Name:")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(70, 5, txt=data.get("patient_name", "Rajesh Kumar"))
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(25, 5, txt="Presc. Dr:")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(70, 5, txt=data.get("prescribing_doctor", "Dr. Arun Sharma"), ln=True)
    pdf.line(10, 52, 200, 52)
    pdf.ln(5)
    
    # Table headers
    pdf.set_font("helvetica", "B", 9)
    pdf.cell(70, 6, txt="MEDICINE NAME", border=1)
    pdf.cell(24, 6, txt="BATCH", border=1, align="C")
    pdf.cell(24, 6, txt="EXP", border=1, align="C")
    pdf.cell(24, 6, txt="QTY", border=1, align="C")
    pdf.cell(24, 6, txt="MRP", border=1, align="C")
    pdf.cell(24, 6, txt="AMOUNT", border=1, ln=True, align="R")
    
    # Items
    pdf.set_font("helvetica", "", 9)
    items = data.get("items", [])
    total_val = data.get("total", 0.0)
    
    if not items:
        # Default fallback
        items = [{"name": "Medicines", "batch": "B123", "exp": "12/26", "quantity": 1, "mrp": total_val, "amount": total_val}]
        
    for item in items:
        pdf.cell(70, 6, txt=item.get("name", "Medicine"), border=1)
        pdf.cell(24, 6, txt=item.get("batch", "B123"), border=1, align="C")
        pdf.cell(24, 6, txt=item.get("exp", "12/26"), border=1, align="C")
        pdf.cell(24, 6, txt=str(item.get("quantity", 1)), border=1, align="C")
        pdf.cell(24, 6, txt=f"{item.get('mrp', 0.0):,.2f}", border=1, align="C")
        pdf.cell(24, 6, txt=f"{item.get('amount', 0.0):,.2f}", border=1, ln=True, align="R")
        
    # Total
    pdf.set_font("helvetica", "B", 9)
    pdf.cell(166, 6, txt="Net Amount Paid (INR)", border=1, align="R")
    pdf.cell(24, 6, txt=f"{total_val:,.2f}", border=1, ln=True, align="R")
    
    pdf.ln(10)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(100, 5, txt="Pharmacist Signature")
    
    pdf.output(filepath)

def generate_all_test_docs(test_cases_path: str, output_dir: str) -> None:
    """Generate all document files for each test case in test_cases.json."""
    os.makedirs(output_dir, exist_ok=True)
    with open(test_cases_path, "r") as f:
        data = json.load(f)
        
    for tc in data.get("test_cases", []):
        case_id = tc["case_id"]
        tc_input = tc["input"]
        print(f"Generating documents for {case_id}...")
        
        for doc in tc_input.get("documents", []):
            dtype = doc.get("actual_type")
            file_id = doc.get("file_id")
            filename = doc.get("file_name") or f"{file_id}.pdf"
            if not filename.endswith((".pdf", ".jpg", ".png")):
                filename += ".pdf"
            # Ensure output is PDF for pdf generation
            filename = filename.rsplit(".", 1)[0] + ".pdf"
            
            filepath = os.path.join(output_dir, filename)
            doc_content = doc.get("content") or {}
            
            # Populate basic fields from case metadata if missing
            doc_content["patient_name"] = doc_content.get("patient_name") or doc.get("patient_name_on_doc") or "Test Patient"
            doc_content["date"] = doc_content.get("date") or tc_input.get("treatment_date")
            doc_content["total"] = doc_content.get("total") or tc_input.get("claimed_amount")
            
            if dtype == "PRESCRIPTION":
                generate_prescription(doc_content, filepath)
            elif dtype == "HOSPITAL_BILL":
                generate_hospital_bill(doc_content, filepath)
            elif dtype == "LAB_REPORT":
                generate_lab_report(doc_content, filepath)
            elif dtype == "PHARMACY_BILL":
                generate_pharmacy_bill(doc_content, filepath)
            else:
                # General fallback
                generate_hospital_bill(doc_content, filepath)

if __name__ == "__main__":
    test_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../test_cases.json"))
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/mock_documents"))
    generate_all_test_docs(test_path, out_path)
