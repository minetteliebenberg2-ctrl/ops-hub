"""Export the pricing schedule to Excel: supplier costs, the per-structure
material breakdown, and the standard car-bay sizes.

Everything is read live from the app (the editable supplier_price_items
table and core/structure_catalog), so the sheet always matches what the
app would actually quote - it is a view of the real data, never a second
copy of it to keep in sync by hand.

Usage:  python tools/export_pricing_schedule.py [output.xlsx]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from core.structure_catalog import (
    CANTILEVER,
    CAR_BAY_SIZES,
    DEFAULT_HEIGHT_M,
    NOT_RECOMMENDED_CAR_BAYS,
    SHADE_SAIL_MAX_HEIGHT_M,
    SHADE_SAIL_POLE_DIAMETERS_MM,
    SHADE_SAIL_SHAPES,
    STANDARD,
    THREE_CAR_OPTIONAL_PROJECTION,
    structure_material_breakdown,
    structure_material_cost,
)
from core.supplier_pricing_repository import CATEGORIES
from core.supplier_pricing_service import SupplierPricingService

BRAND_GREEN = "1B7A3D"
FONT = "Arial"

# Read from the engine rather than restated here - the sheet showing a
# different margin to the app would be worse than useless.
from core.structure_quote import NETTING_GP, STRUCTURE_GP


def _header(sheet, headers, row=1):
    for column, title in enumerate(headers, start=1):
        cell = sheet.cell(row=row, column=column, value=title)
        cell.font = Font(name=FONT, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=BRAND_GREEN)
        cell.alignment = Alignment(horizontal="left", vertical="center")


def _widths(sheet, widths):
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width


def _text(sheet, row, column, value, bold=False):
    cell = sheet.cell(row=row, column=column, value=value)
    cell.font = Font(name=FONT, bold=bold)
    return cell


def _money(sheet, row, column, value, bold=False):
    cell = sheet.cell(row=row, column=column, value=value)
    cell.font = Font(name=FONT, bold=bold)
    cell.number_format = 'R#,##0.00'
    return cell


def build_supplier_sheet(workbook, service):
    sheet = workbook.active
    sheet.title = "Supplier Pricing"
    _header(sheet, ["Category", "Item", "Supplier", "Spec", "Unit", "Cost (R)", "Status"])

    row = 2
    for category in CATEGORIES:
        for item in service.list_items(category, include_inactive=True):
            _text(sheet, row, 1, item.category)
            _text(sheet, row, 2, item.item_name)
            _text(sheet, row, 3, item.supplier_name)
            _text(sheet, row, 4, item.spec)
            _text(sheet, row, 5, item.unit)
            _money(sheet, row, 6, item.cost_minor / 100)
            _text(sheet, row, 7, "Active" if item.is_active else "Inactive")
            row += 1

    _widths(sheet, [12, 30, 18, 46, 10, 13, 10])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:G{row - 1}"
    return row - 2


def build_structure_sheet(workbook):
    sheet = workbook.create_sheet("Structure Breakdown")
    _header(sheet, ["Structure", "Part", "Qty", "Spec", "Unit length", "Stock length",
                    "Cost / stock (R incl VAT)", "Line cost (R incl VAT)", "Price source", "Note"])

    row = 2
    for structure_type in (CANTILEVER, STANDARD):
        breakdown = structure_material_breakdown(structure_type)
        bom = {part[0]: part for part in __import__(
            "core.structure_catalog", fromlist=["STRUCTURE_BOM"]
        ).STRUCTURE_BOM[structure_type]}

        for entry in breakdown:
            source_part = bom.get(entry["part"])
            unit_length = source_part[3] if source_part else None
            stock_length = source_part[4] if source_part else None

            _text(sheet, row, 1, structure_type)
            _text(sheet, row, 2, entry["part"])
            _text(sheet, row, 3, entry["qty"])
            _text(sheet, row, 4, entry["spec"])
            _text(sheet, row, 5, f"{unit_length} m" if unit_length else "-")
            _text(sheet, row, 6, f"{stock_length} m" if stock_length else "-")
            _money(sheet, row, 7, entry["unit_cost"] if entry["unit_cost"] is not None else 0)
            _money(sheet, row, 8, entry["line_cost"] if entry["line_cost"] is not None else 0)
            _text(sheet, row, 9, entry["source"])
            _text(sheet, row, 10, entry["note"])
            row += 1

        cost = structure_material_cost(structure_type)
        _text(sheet, row, 2, f"{structure_type} material total (incl VAT - not reclaimable)", bold=True)
        _money(sheet, row, 8, cost or 0, bold=True)
        row += 1

        if cost:
            _text(sheet, row, 2, f"Sell price at {int(STRUCTURE_GP * 100)}% GP", bold=True)
            _money(sheet, row, 8, round(cost / (1 - STRUCTURE_GP), 2), bold=True)
            row += 1

        _text(sheet, row, 2, "Labour add-ons are flat (not GP-marked-up) - see Supplier Pricing > Labour")
        row += 2

    _widths(sheet, [14, 26, 7, 42, 12, 13, 17, 15, 17, 60])
    sheet.freeze_panes = "A2"
    return row


def build_sizes_sheet(workbook):
    sheet = workbook.create_sheet("Sizes")

    _header(sheet, ["Car bays", "Width (m)", "Projection (m)", "Notes"])
    row = 2
    for cars in sorted(CAR_BAY_SIZES):
        width, projection = CAR_BAY_SIZES[cars]
        notes = []
        if cars in NOT_RECOMMENDED_CAR_BAYS:
            notes.append("Rarely done - they don't last")
        if cars == 3:
            notes.append(f"Optional {THREE_CAR_OPTIONAL_PROJECTION}m projection as a client extra")
        _text(sheet, row, 1, cars)
        _text(sheet, row, 2, width)
        _text(sheet, row, 3, projection)
        _text(sheet, row, 4, "; ".join(notes))
        row += 1

    row += 1
    _text(sheet, row, 1, "Heights", bold=True)
    row += 1
    _text(sheet, row, 1, "Standard height")
    _text(sheet, row, 2, f"{DEFAULT_HEIGHT_M} m")
    _text(sheet, row, 4, "Included in base pricing; anything taller is a chargeable extra")
    row += 1

    row += 1
    _text(sheet, row, 1, "Shade sails", bold=True)
    row += 1
    _text(sheet, row, 1, "Shapes")
    _text(sheet, row, 2, ", ".join(SHADE_SAIL_SHAPES))
    row += 1
    _text(sheet, row, 1, "Pole diameters")
    _text(sheet, row, 2, ", ".join(f"{d}mm" for d in SHADE_SAIL_POLE_DIAMETERS_MM))
    row += 1
    _text(sheet, row, 1, "Max height")
    _text(sheet, row, 2, f"{SHADE_SAIL_MAX_HEIGHT_M} m")
    row += 1
    _text(sheet, row, 1, "Interim rate")
    _money(sheet, row, 2, 750.00)
    _text(sheet, row, 4, "R750 per square metre until real shade-sail costing is built")
    row += 2

    _text(sheet, row, 1, "Margins", bold=True)
    row += 1
    _text(sheet, row, 1, "Structures / cantilever")
    _text(sheet, row, 2, f"{int(STRUCTURE_GP * 100)}% GP")
    row += 1
    _text(sheet, row, 1, "Netting")
    _text(sheet, row, 2, f"{int(NETTING_GP * 100)}% GP")
    row += 1
    _text(sheet, row, 4, "Sell = cost / (1 - GP). Labour add-ons are flat, not marked up.")

    _widths(sheet, [24, 18, 16, 62])
    return row


def main():
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("FacilitiesCo_Supplier_Pricing.xlsx")

    service = SupplierPricingService()
    workbook = openpyxl.Workbook()

    supplier_rows = build_supplier_sheet(workbook, service)
    build_structure_sheet(workbook)
    build_sizes_sheet(workbook)

    workbook.save(destination)
    print(f"Wrote {destination} ({supplier_rows} supplier rows, 3 sheets)")


if __name__ == "__main__":
    main()
