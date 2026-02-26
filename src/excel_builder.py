"""Excel workbook builder for Redfin listing analysis."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .config import EXCEL_DEFAULTS


ASSUMPTION_ROWS = [
    ("Interest Rate", "interest_rate", "0.00%"),
    ("Down Payment $", "down_payment", "$#,##0"),
    ("Loan Term Years", "loan_term_years", "#,##0"),
    ("Property Tax Rate", "property_tax_rate", "0.00%"),
    ("Insurance $/mo", "insurance_monthly", "$#,##0"),
    ("Utilities $/mo", "utilities_monthly", "$#,##0"),
    ("Internet $/mo", "internet_monthly", "$#,##0"),
]

LISTING_HEADERS = [
    "Address",          # A
    "Town",             # B
    "Listing URL",      # C
    "Price",            # D
    "HOA/mo",           # E
    "Beds",             # F
    "Baths",            # G
    "Sq Ft",            # H
    "In-Unit Laundry",  # I
    "Parking",          # J
    "Down Payment $",   # K
    "Loan Amount",      # L
    "Monthly Mortgage",  # M
    "Property Tax/mo",  # N
    "Insurance/mo",     # O
    "Utilities+Internet",  # P
    "Total Monthly Cost",  # Q
    "Area Rental Price (Roommate)",  # R
    "Net Monthly Cost",  # S
    "Drive to MBTA (min)",  # T
    "Drive to Seaport (min)",  # U
    "Drive to Google (min)",  # V
    "Rating Score",     # W
    "Rating",           # X
]


def _style_header_row(ws) -> None:
    header_fill = PatternFill(fill_type="solid", start_color="FFD9D9D9", end_color="FFD9D9D9")
    header_font = Font(bold=True)
    header_alignment = Alignment(horizontal="center", vertical="center")

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment


def _apply_auto_width(ws) -> None:
    for col_idx in range(1, ws.max_column + 1):
        letter = get_column_letter(col_idx)
        max_len = 0
        for row_idx in range(1, ws.max_row + 1):
            value = ws.cell(row=row_idx, column=col_idx).value
            if value is None:
                continue
            value_len = len(str(value))
            if value_len > max_len:
                max_len = value_len
        ws.column_dimensions[letter].width = min(max_len + 4, 50)


def build_workbook(listings: list[dict[str, object]], output_path: Path) -> None:
    """Build and save the Zillow tracker workbook to the provided path."""
    wb = Workbook()

    assumptions_ws = wb.active
    if assumptions_ws is None:
        assumptions_ws = wb.create_sheet("Assumptions")
    assumptions_ws.title = "Assumptions"
    assumptions_ws.append(["Assumption", "Value"])
    assumptions_ws.freeze_panes = "A2"
    _style_header_row(assumptions_ws)

    for row_idx, (label, key, number_format) in enumerate(ASSUMPTION_ROWS, start=2):
        assumptions_ws.cell(row=row_idx, column=1, value=label)
        value_cell = assumptions_ws.cell(row=row_idx, column=2, value=EXCEL_DEFAULTS[key])
        value_cell.number_format = number_format

    listings_ws = wb.create_sheet("Listings")
    listings_ws.append(LISTING_HEADERS)
    listings_ws.freeze_panes = "A2"
    _style_header_row(listings_ws)

    light_green_fill = PatternFill(fill_type="solid", start_color="FFE2F0D9", end_color="FFE2F0D9")
    light_yellow_fill = PatternFill(fill_type="solid", start_color="FFFFF2CC", end_color="FFFFF2CC")
    light_red_fill = PatternFill(fill_type="solid", start_color="FFF4CCCC", end_color="FFF4CCCC")

    for row_idx, listing in enumerate(listings, start=2):
        listings_ws.cell(row=row_idx, column=1, value=listing["address"])
        listings_ws.cell(row=row_idx, column=2, value=listing["town"])

        url_cell = listings_ws.cell(row=row_idx, column=3, value=listing["url"])
        url_cell.hyperlink = listing["url"]
        url_cell.style = "Hyperlink"

        listings_ws.cell(row=row_idx, column=4, value=listing["price"])
        listings_ws.cell(row=row_idx, column=5, value=listing["hoa"] or 0)
        listings_ws.cell(row=row_idx, column=6, value=listing.get("beds"))
        listings_ws.cell(row=row_idx, column=7, value=listing.get("baths"))
        listings_ws.cell(row=row_idx, column=8, value=listing.get("sqft"))
        listings_ws.cell(
            row=row_idx,
            column=9,
            value="Yes" if listing["in_unit_laundry"] else "No",
        )
        listings_ws.cell(row=row_idx, column=10, value=listing["parking"])

        listings_ws.cell(row=row_idx, column=11, value=f"=Assumptions!B3")
        listings_ws.cell(row=row_idx, column=12, value=f"=D{row_idx}-K{row_idx}")
        listings_ws.cell(
            row=row_idx,
            column=13,
            value=f"=-PMT(Assumptions!B2/12,Assumptions!B4*12,L{row_idx})",
        )
        listings_ws.cell(row=row_idx, column=14, value=f"=D{row_idx}*Assumptions!B5/12")
        listings_ws.cell(row=row_idx, column=15, value="=Assumptions!B6")
        listings_ws.cell(row=row_idx, column=16, value="=Assumptions!B7+Assumptions!B8")
        listings_ws.cell(row=row_idx, column=17, value=f"=M{row_idx}+E{row_idx}+N{row_idx}+O{row_idx}+P{row_idx}")
        listings_ws.cell(row=row_idx, column=18, value=listing["rental_estimate"])
        listings_ws.cell(row=row_idx, column=19, value=f"=Q{row_idx}-R{row_idx}")

        listings_ws.cell(row=row_idx, column=20, value=listing["drive_mbta_min"])
        listings_ws.cell(row=row_idx, column=21, value=listing["drive_seaport_min"])
        listings_ws.cell(row=row_idx, column=22, value=listing["drive_google_min"])
        listings_ws.cell(row=row_idx, column=23, value=listing["rating_score"])
        listings_ws.cell(row=row_idx, column=24, value=listing["rating_color"])

        rating = listing["rating_color"]
        address_cell = listings_ws.cell(row=row_idx, column=1)
        if rating == "Green":
            address_cell.fill = light_green_fill
        elif rating == "Yellow":
            address_cell.fill = light_yellow_fill
        elif rating == "Red":
            address_cell.fill = light_red_fill

    for row_idx in range(2, listings_ws.max_row + 1):
        listings_ws.cell(row=row_idx, column=4).number_format = "$#,##0"
        listings_ws.cell(row=row_idx, column=5).number_format = "$#,##0"
        listings_ws.cell(row=row_idx, column=8).number_format = "#,##0"
        for col_idx in range(11, 20):
            listings_ws.cell(row=row_idx, column=col_idx).number_format = "$#,##0"
        listings_ws.cell(row=row_idx, column=23).number_format = "0.00"

    green_fill = PatternFill(fill_type="solid", start_color="FF92D050", end_color="FF92D050")
    yellow_fill = PatternFill(fill_type="solid", start_color="FFFFFF00", end_color="FFFFFF00")
    red_fill = PatternFill(fill_type="solid", start_color="FFFF0000", end_color="FFFF0000")

    rating_range = f"X2:X{max(2, listings_ws.max_row)}"
    listings_ws.conditional_formatting.add(
        rating_range,
        CellIsRule(operator="equal", formula=['"Green"'], fill=green_fill),
    )
    listings_ws.conditional_formatting.add(
        rating_range,
        CellIsRule(operator="equal", formula=['"Yellow"'], fill=yellow_fill),
    )
    listings_ws.conditional_formatting.add(
        rating_range,
        CellIsRule(
            operator="equal",
            formula=['"Red"'],
            fill=red_fill,
            font=Font(color="FFFFFFFF"),
        ),
    )

    _apply_auto_width(assumptions_ws)
    _apply_auto_width(listings_ws)

    wb.save(output_path)
