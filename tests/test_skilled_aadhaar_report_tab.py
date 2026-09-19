import pytest
from pathlib import Path

from src.tabs.skilled_aadhaar_report_tab import parse_skilled_aadhaar_table


SAMPLE_HTML = """
<table class="table table-bordered table-striped cust-tbl small" id="ctl00_ContentPlaceHolder1_Grid_debarred">
    <tbody>
        <tr>
            <td colspan="7"><table><tr><td><span>1</span></td><td><a href="javascript:__doPostBack('ctl00$ContentPlaceHolder1$Grid_debarred','Page$2')">2</a></td></tr></table></td>
        </tr>
        <tr>
            <th>S.No</th><th>Job Card No</th><th>Worker Name</th><th>Gender</th><th>Aadhaar No</th><th>Name as per Aadhaar Card</th><th>Update</th>
        </tr>
        <tr>
            <td><span id="ctl00_ContentPlaceHolder1_Grid_debarred_ctl03_sno">1</span></td>
            <td><span id="ctl00_ContentPlaceHolder1_Grid_debarred_ctl03_lbljcno">S-JH-22-003-008-001/222288</span></td>
            <td><span id="ctl00_ContentPlaceHolder1_Grid_debarred_ctl03_lblapp_name">MANOJ KUMAR SINGH</span></td>
            <td><span id="ctl00_ContentPlaceHolder1_Grid_debarred_ctl03_lblgender">M</span></td>
            <td><span id="ctl00_ContentPlaceHolder1_Grid_debarred_ctl03_lb_UID_No">XXXXXXXX1234</span></td>
            <td><span>MANOJ KUMAR SINGH</span></td>
            <td><a href="#">Edit</a></td>
        </tr>
        <tr>
            <td><span id="ctl00_ContentPlaceHolder1_Grid_debarred_ctl04_sno">2</span></td>
            <td><span id="ctl00_ContentPlaceHolder1_Grid_debarred_ctl04_lbljcno">S-JH-22-003-008-001/222291</span></td>
            <td><span id="ctl00_ContentPlaceHolder1_Grid_debarred_ctl04_lblapp_name">TARNI RANA</span></td>
            <td><span id="ctl00_ContentPlaceHolder1_Grid_debarred_ctl04_lblgender">F</span></td>
            <td><span id="ctl00_ContentPlaceHolder1_Grid_debarred_ctl04_lb_UID_No"></span></td>
            <td><span></span></td>
            <td><a href="#">Edit</a></td>
        </tr>
    </tbody>
</table>
"""


def test_parse_skilled_aadhaar_table():
    fixture_path = Path("docs/htm/SkilledBulkAadhaarUpdate.aspx.html")
    if fixture_path.exists():
        html_content = fixture_path.read_text(encoding="utf-8")
    else:
        html_content = SAMPLE_HTML
    
    data, summary = parse_skilled_aadhaar_table(html_content)
    
    assert summary["total"] > 0
    assert summary["total"] == summary["male"] + summary["female"] + summary["other"]
    assert summary["total"] == summary["seeded"] + summary["pending"]
    assert len(data) == summary["total"]
    
    # Check specific fields of first row
    first = data[0]
    assert first["sno"] == "1"
    assert first["job_card_no"] == "S-JH-22-003-008-001/222288"
    assert first["worker_name"] == "MANOJ KUMAR SINGH"
    assert first["gender"] == "M"
    assert first["status"] in ("Seeded", "Pending")


