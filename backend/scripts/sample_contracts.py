"""Write the invented sample contracts as PDFs.

    .venv/Scripts/python scripts/sample_contracts.py ../frontend/public/samples

sample-lease.pdf is the one the frontend's "Try a sample contract" button uploads.
sample-services-agreement.pdf is a longer one for checking review quality by hand.
Every name, address and number in them is made up.
"""

import sys
from pathlib import Path

from fpdf import FPDF

NOTE = "SAMPLE CONTRACT. All names, places and figures are fictional."

LEASE = [
    (
        "Residential Lease Agreement",
        [
            "This Residential Lease Agreement (the \"Lease\") is made on 1 March 2026 between Harbor Homes LLC, "
            "12 Kestrel Quay, Port Elsby (the \"Landlord\") and Jordan Vale (the \"Tenant\").",
            "1. Premises. The Landlord leases to the Tenant the apartment at Flat 4B, 88 Linden Row, Port Elsby "
            "(the \"Premises\"), together with one parking space in the rear lot.",
            "2. Term. The Lease begins on 1 April 2026 and ends on 31 March 2027. Unless either party gives written "
            "notice at least 90 days before the end of the term, this Lease renews automatically for further "
            "periods of twelve months on the same terms, except that the Landlord may increase the rent.",
            "3. Rent. Monthly rent is 1,450 USD, payable in advance on the first day of each month by bank transfer. "
            "Rent received after the fifth day of the month incurs a late fee of 75 USD, plus 10 USD for each "
            "further day the rent remains unpaid.",
            "4. Security deposit. The Tenant pays a security deposit of 2,900 USD before moving in. The Landlord "
            "returns the deposit within 45 days after the Lease ends, less any amounts the Landlord, in its sole "
            "discretion, considers necessary for cleaning, repairs or unpaid charges.",
        ],
    ),
    (
        None,
        [
            "5. Repairs and maintenance. The Tenant is responsible for all repairs to the Premises, including "
            "plumbing, heating and electrical systems, whatever the cause, except damage to the structure of "
            "the building.",
            "6. Access. The Landlord and its agents may enter the Premises at any reasonable time to inspect, "
            "repair or show the Premises to prospective tenants or buyers. The Landlord will try to give notice "
            "but is not required to do so.",
            "7. Pets. The Tenant may keep one cat or one small dog with the Landlord's prior written consent. "
            "A non-refundable pet fee of 300 USD applies.",
            "8. Early termination. After the first six months, the Tenant may end this Lease by giving 60 days' "
            "written notice and paying a termination fee equal to two months' rent. The Landlord may end this "
            "Lease at any time by giving 30 days' written notice.",
        ],
    ),
    (
        None,
        [
            "9. Liability. The Landlord is not liable for any loss, injury or damage to the Tenant, the Tenant's "
            "guests or their property, however caused, including through the Landlord's negligence. The Tenant "
            "must hold renter's insurance with liability cover of at least 100,000 USD.",
            "10. Disputes. Any dispute arising out of this Lease shall be resolved by binding arbitration in Port "
            "Elsby. The Tenant waives any right to a jury trial or to join a class action.",
            "11. Governing law. This Lease is governed by the laws of the State of Westmarch.",
            "Signed by Harbor Homes LLC, by its manager Priya Okafor, and by Jordan Vale, on 1 March 2026.",
        ],
    ),
]

SERVICES = [
    (
        "Master Services Agreement",
        [
            "This Master Services Agreement (the \"Agreement\") is entered into as of 15 January 2026 (the "
            "\"Effective Date\") by and between Quillfeather Logistics Inc., a Delmora corporation with offices "
            "at 400 Canal Street, Vantry (the \"Client\"), and Northwind Pixel Studio Ltd, a company registered "
            "in Ostrava Bay with offices at 7 Mill Lane, Harrowgate (the \"Supplier\").",
            "1. Definitions. \"Deliverables\" means all software, designs, documents and other materials the "
            "Supplier creates for the Client under a Statement of Work. \"Statement of Work\" or \"SOW\" means a "
            "document signed by both parties describing specific services, fees and timelines. \"Confidential "
            "Information\" means any non-public information disclosed by one party to the other, in any form, "
            "that is marked confidential or that a reasonable person would understand to be confidential.",
            "2. Services. The Supplier will provide the services described in each SOW (the \"Services\"). If a "
            "SOW conflicts with this Agreement, this Agreement prevails unless the SOW expressly states otherwise. "
            "The Supplier will assign suitably qualified personnel and may not subcontract any part of the "
            "Services without the Client's prior written consent.",
            "3. Change requests. Either party may request changes to a SOW in writing. The Supplier will respond "
            "with the impact on fees and timeline within five business days. No change is binding until both "
            "parties sign a change order.",
        ],
    ),
    (
        None,
        [
            "4. Fees and payment. The Client will pay the fees set out in each SOW. The Supplier will invoice "
            "monthly in arrears. Invoices are payable within sixty (60) days of receipt. The Client may withhold "
            "payment of any amount it disputes in good faith, and need not pay any undisputed amount until the "
            "dispute is resolved. Late payments bear interest at 1% per month.",
            "5. Expenses. The Client will reimburse reasonable travel expenses that it has approved in writing in "
            "advance, at cost and without mark-up.",
            "6. Acceptance. The Client has thirty (30) days after delivery to test each Deliverable. If the Client "
            "rejects a Deliverable, the Supplier will correct it at no additional charge and redeliver it within "
            "ten (10) business days. A Deliverable is accepted only when the Client confirms acceptance in writing.",
            "7. Term and renewal. This Agreement begins on the Effective Date and continues for two (2) years. "
            "It then renews automatically for successive one-year periods unless either party gives notice of "
            "non-renewal at least one hundred and twenty (120) days before the end of the then-current term.",
        ],
    ),
    (
        None,
        [
            "8. Termination. The Client may terminate this Agreement or any SOW for convenience at any time on "
            "fifteen (15) days' written notice. The Supplier may terminate this Agreement only if the Client fails "
            "to pay an undisputed invoice within ninety (90) days after written notice of non-payment. On "
            "termination, the Client pays only for Services performed and accepted up to the termination date.",
            "9. Intellectual property. All Deliverables, and all intellectual property rights in them, vest in the "
            "Client on creation. The Supplier also assigns to the Client all rights in any tools, libraries, "
            "methods or know-how that the Supplier uses in performing the Services, whether created before or "
            "after the Effective Date, and waives all moral rights in them.",
            "10. Confidentiality. Each party will keep the other's Confidential Information secret and use it only "
            "to perform this Agreement. These obligations survive for five (5) years after this Agreement ends, "
            "except for trade secrets, which remain protected for as long as they remain trade secrets.",
        ],
    ),
    (
        None,
        [
            "11. Non-solicitation and non-compete. During the term and for twenty-four (24) months afterwards, "
            "the Supplier will not provide services similar to the Services to any business that competes with "
            "the Client anywhere in the world, and will not solicit any employee of the Client.",
            "12. Warranties. The Supplier warrants that the Services will be performed with reasonable skill and "
            "care, and that the Deliverables will not infringe any third party's intellectual property rights.",
            "13. Indemnity. The Supplier will defend, indemnify and hold harmless the Client and its affiliates "
            "from and against any and all claims, losses, damages, fines and costs, including legal fees, arising "
            "out of or relating to the Services or this Agreement, howsoever caused.",
            "14. Limitation of liability. The Client's total liability under this Agreement shall not exceed the "
            "fees paid in the three (3) months before the claim. Nothing in this Agreement limits the Supplier's "
            "liability. Neither party is liable for indirect or consequential loss, except under clause 13.",
        ],
    ),
    (
        None,
        [
            "15. Insurance. The Supplier will maintain professional indemnity insurance of at least 2,000,000 USD "
            "per claim throughout the term and for six (6) years afterwards.",
            "16. Data protection. The Supplier will process personal data only on the Client's documented "
            "instructions and will notify the Client of any personal data breach within twenty-four (24) hours.",
            "17. Governing law and disputes. This Agreement is governed by the laws of Delmora. The courts of "
            "Vantry have exclusive jurisdiction over any dispute, and the Supplier submits to that jurisdiction.",
            "18. Assignment. The Client may assign this Agreement to any affiliate or successor without consent. "
            "The Supplier may not assign it without the Client's prior written consent.",
            "19. Entire agreement. This Agreement and the SOWs are the entire agreement between the parties and "
            "replace all earlier discussions.",
            "Signed for Quillfeather Logistics Inc. by Dana Whitlock, Chief Operating Officer, and for Northwind "
            "Pixel Studio Ltd by Tomas Reyna, Director.",
        ],
    ),
]


def write(pages, path: Path) -> None:
    pdf = FPDF(format="Letter")
    pdf.set_margins(22, 22)
    pdf.set_auto_page_break(False)
    for title, paragraphs in pages:
        pdf.add_page()
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(0, 5, NOTE, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        if title:
            pdf.set_font("Helvetica", "B", 15)
            pdf.cell(0, 9, title, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)
        pdf.set_font("Helvetica", size=10.5)
        for paragraph in paragraphs:
            pdf.multi_cell(0, 5.4, paragraph, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)
        if pdf.get_y() > pdf.h - 22:
            raise SystemExit(f"{path.name}: page {pdf.page} overflows; move a paragraph to the next page")
        pdf.set_y(-16)
        pdf.set_font("Helvetica", size=8)
        pdf.cell(0, 5, f"Page {pdf.page} of {len(pages)}", align="C")
    pdf.output(str(path))


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    write(LEASE, out / "sample-lease.pdf")
    write(SERVICES, out / "sample-services-agreement.pdf")
