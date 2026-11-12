import os
import pytest
from bs4 import BeautifulSoup
from src.tabs.pending_bills_tab import PendingBillsTab


def test_parse_pending_bills_table_from_html():
    htm_path = os.path.join(os.path.dirname(__file__), "..", "docs", "htm", "pending Bills.htm")
    assert os.path.exists(htm_path), f"Sample HTM file not found at {htm_path}"

    with open(htm_path, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()

    rows = PendingBillsTab.parse_bills_table(html, fy="2024-2025", panchayat="Burkundi")
    assert len(rows) == 2

    r0 = rows[0]
    assert r0["s_no"] == "1"
    assert r0["fy"] == "2024-2025"
    assert r0["panchayat"] == "Burkundi"
    assert r0["work_code"] == "3422003007/IF/7080902976925"
    assert "फाड़ासिमल" in r0["work_name"]
    assert r0["bill_no"] == "1120"
    assert r0["bill_date"] == "20/03/2025"
    assert r0["vendor_name"] == "SALAMAT ANSARI"
    assert r0["vendor_tin"] == "20BQRPA6750M1ZO"
    assert float(r0["bill_amount"]) == 80449.9
    assert float(r0["balance_to_paid"]) == 80449.9
    assert r0["material_list_no"] == "3422003-ML-3300"
    assert r0["is_rejected"] == "N"

    r1 = rows[1]
    assert r1["s_no"] == "2"
    assert r1["work_code"] == "3422003007/IF/7080902430313"
    assert r1["bill_no"] == "1263"
    assert float(r1["bill_amount"]) == 44287.68
    assert float(r1["balance_to_paid"]) == 44287.68


def test_parse_pending_bills_table_empty():
    empty_html = "<html><body><table id='gvbillpaid1'><tbody><tr><td colspan='21'>No data available</td></tr></tbody></table></body></html>"
    rows = PendingBillsTab.parse_bills_table(empty_html, fy="2024-2025", panchayat="TestPanchayat")
    assert rows == []


def test_write_excel(tmp_path):
    import openpyxl
    sample_rows = [
        {
            "s_no": "1",
            "fy": "2024-2025",
            "panchayat": "Burkundi",
            "work_code": "3422003007/IF/7080902976925",
            "work_name": "Test Work 1",
            "total_sanction": "396038",
            "mat_sanction": "80986",
            "total_mat_booked": "80449.9",
            "total_paid": "0",
            "balance_to_paid": "80449.9",
            "work_status": "On Going",
            "bill_no": "1120",
            "bill_date": "20/03/2025",
            "vendor_name": "SALAMAT ANSARI",
            "vendor_tin": "20BQRPA6750M1ZO",
            "bill_amount": "80449.9",
            "tax_amount": "0",
            "material_list_no": "3422003-ML-3300",
            "fto_no": "",
            "is_rejected": "N",
        },
        {
            "s_no": "2",
            "fy": "2024-2025",
            "panchayat": "Burkundi",
            "work_code": "3422003007/IF/7080902430313",
            "work_name": "Test Work 2",
            "total_sanction": "498498",
            "mat_sanction": "163932.4",
            "total_mat_booked": "154154.96",
            "total_paid": "109867.28",
            "balance_to_paid": "44287.68",
            "work_status": "On Going",
            "bill_no": "1263",
            "bill_date": "25/06/2024",
            "vendor_name": "SALAMAT ANSARI",
            "vendor_tin": "20BQRPA6750M1ZO",
            "bill_amount": "44287.68",
            "tax_amount": "0",
            "material_list_no": "3422003-ML-1301",
            "fto_no": "",
            "is_rejected": "N",
        }
    ]

    target_file = str(tmp_path / "pending_bills_test.xlsx")
    PendingBillsTab.write_excel_report(sample_rows, target_file)

    assert os.path.exists(target_file)
    wb = openpyxl.load_workbook(target_file)
    assert "Pending Bills Details" in wb.sheetnames
    assert "Panchayat Summary" in wb.sheetnames

    ws_details = wb["Pending Bills Details"]
    assert "PENDING MATERIAL BILLS" in str(ws_details["A1"].value).upper()
    # Check KPI row
    assert ws_details["A4"].value == "TOTAL PENDING BILLS"
    assert ws_details["A5"].value == 2

    ws_summary = wb["Panchayat Summary"]
    assert "SUMMARY" in str(ws_summary["A1"].value).upper()

