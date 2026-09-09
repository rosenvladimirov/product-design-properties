# Copyright 2024-2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later)
#      https://www.gnu.org/licenses/agpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the AGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the AGPL-3.0-or-later.
import re

from odoo import api, fields, models

# Цеховият баркод, както се сканира: две двойки цифри с наклонена черта.
BARCODE_RE = re.compile(r"\b(\d{2}/\d{2})\b")


class MrpRoutingWorkcenter(models.Model):
    _inherit = "mrp.routing.workcenter"

    # ── Shop floor context ───────────────────────────────────────────
    # Едно измерване на цеха носи ПЕТ неща за операцията, а Odoo има място
    # само за времето. Затова баркодът досега живееше в `name` (15 операции
    # го носят в скоби, една — два наведнъж), а честотата, източникът и
    # календарното време просто нямаше къде да влязат.
    # 🔑 `name` е преводимо поле: баркод в него не може да се сверява със
    # сканиранията, защото се мени с езика.

    shop_barcode = fields.Char(
        string="Shop Barcode",
        index=True,
        help="Operation barcode as scanned on the shop floor. One operation "
        "may cover several barcodes — list them comma separated "
        "(e.g. '01/29,02/05'). Kept out of the operation name, which is "
        "translatable and therefore cannot be matched against scan data.",
    )
    semi_finished = fields.Selection(
        selection=[
            ("frame_metal", "Metal frame"),
            ("leaf_metal", "Metal leaf"),
            ("profiles_metal", "Metal profiles"),
            ("leaf_wood", "Wood leaf"),
            ("frame_wood", "Wood frame"),
            ("frame_alu", "Aluminium frame"),
            ("edging", "Edging"),
            ("painted", "Painted parts"),
            ("final_assembly", "Final assembly"),
            ("quality", "Quality control"),
        ],
        string="Semi-finished Part",
        index=True,
        help="Which semi-finished part this operation works on. Operations "
        "follow the parts, not one row per work center, so a door reads as "
        "the sequence the shop floor actually runs.",
    )
    time_calendar = fields.Float(
        string="Calendar Time",
        help="Operation time including carrying and waiting, derived from a "
        "full operator day (480 min divided by the median number of doors). "
        "Use it for capacity planning; the clean operation time in Duration "
        "stays the basis for labour cost. Typically 1-2x the clean time.",
    )
    # 🔑 Два източника, защото едно време има две числа, а те рядко идват от
    # едно и също място: в маршрутите на Солид 26 от 60 операции (43%) носят
    # чисто време от норма или измерване И календарно от дневника на баркодовете.
    # С един етикет половината от реда получава чужд произход — точно обратното
    # на това, за което полето съществува.
    _TIME_SOURCES = [
        ("measured", "Measured (clean)"),
        ("shop_log", "Shop log (calendar)"),
        ("norm_2011", "Norm 2011 (structural)"),
        ("norm_2016", "Norm 2016 (wet paint)"),
        ("estimate", "Estimate"),
    ]

    time_source = fields.Selection(
        selection=_TIME_SOURCES,
        string="Time Source",
        help="Where the clean operation time in Duration comes from. A measured "
        "time and an estimate are not equally trustworthy, and that difference "
        "has to survive in the data instead of living in someone's memory.",
    )
    time_calendar_source = fields.Selection(
        selection=_TIME_SOURCES,
        string="Calendar Time Source",
        help="Where Calendar Time comes from. Usually the shop log, which is "
        "calendar by construction; kept separate because the clean time next to "
        "it often comes from a norm or a measurement instead.",
    )
    shop_frequency = fields.Float(
        string="Shop Frequency",
        help="Share of doors that actually pass this operation, measured from "
        "shop floor scans (1.0 = every door). Anything below 1.0 means the "
        "operation is conditional in practice, even when nothing marks it so.",
    )

    # ── Helpers ──────────────────────────────────────────────────────

    def _shop_barcode_list(self):
        """Return this operation's barcodes as a list."""
        self.ensure_one()
        if not self.shop_barcode:
            return []
        return [part.strip() for part in self.shop_barcode.split(",") if part.strip()]

    @api.model
    def _barcodes_in_name(self, name):
        """Return the barcodes written inside an operation *name*."""
        return BARCODE_RE.findall(name or "")

    def action_fill_shop_barcode_from_name(self):
        """Fill an empty ``shop_barcode`` from the barcodes in the name.

        Deliberately a manual action, not an upgrade hook: it writes on
        existing operations, and moving live data is a decision, not a
        migration side effect. Operations that already carry a barcode are
        left alone.
        """
        filled = self.env["mrp.routing.workcenter"]
        for operation in self.filtered(lambda o: not o.shop_barcode):
            found = self._barcodes_in_name(operation.name)
            if found:
                operation.shop_barcode = ",".join(found)
                filled |= operation
        return filled
