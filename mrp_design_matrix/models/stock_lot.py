# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    # width / height / thickness come from stock_move_forced_lot_multi_dim

    # ── helpers ──────────────────────────────────────────────────────────

    def _get_design_context(self) -> dict:
        """
        Return a flat dict suitable for GoRules / formula evaluation.

        Merges the three real dimension fields (from _dim sub-module)
        with all entries from ``design_params`` Properties.
        """
        self.ensure_one()
        ctx = {
            "width": getattr(self, "width", 0.0),
            "height": getattr(self, "height", 0.0),
            "thickness": getattr(self, "thickness", 0.0),
        }
        for key, value in (self.design_params or {}).items():
            ctx[key] = value
        return ctx

    @api.model
    def _create_child_lot(self, parent_lot, bom_line, product):
        """
        Create a child lot for a semi-finished product by extracting
        parameters from *parent_lot* according to *bom_line.param_extraction_map*.

        :param parent_lot:  ``stock.lot`` of the parent MO product.
        :param bom_line:    ``mrp.bom.line`` with ``param_extraction_map``
                            and ``child_definition_id`` set.
        :param product:     ``product.product`` for the child lot.
        :returns:           Newly created ``stock.lot``.
        """
        param_map = bom_line.param_extraction_map or {}
        parent_ctx = parent_lot._get_design_context()
        child_params = {}

        for child_key, source in param_map.items():
            if source in parent_ctx:
                # Direct copy
                child_params[child_key] = parent_ctx[source]
            else:
                # Formula — safe_eval against parent context
                try:
                    from odoo.tools.safe_eval import safe_eval

                    child_params[child_key] = safe_eval(source, parent_ctx)
                except Exception:
                    child_params[child_key] = None

        return self.create(
            {
                "name": self._generate_child_lot_name(parent_lot, product),
                "product_id": product.id,
                "company_id": parent_lot.company_id.id,
                "design_param_definition_id": (
                    bom_line.child_definition_id.id
                    if bom_line.child_definition_id
                    else False
                ),
                "design_params": child_params or False,
            }
        )

    @api.model
    def _generate_child_lot_name(self, parent_lot, product):
        return self.env["ir.sequence"].next_by_code("stock.lot.serial") or (
            f"{parent_lot.name}-{product.default_code or product.id}"
        )

    def _find_matching_stock_lot(self, product, required_params: dict):
        """
        Find an existing lot whose ``design_params`` match *required_params*.

        Used when ``mto_stop=True`` on a BoM line — the system looks for
        stock instead of triggering a new MO.

        :returns: matching ``stock.lot`` or empty recordset.
        """
        candidates = self.search(
            [
                ("product_id", "=", product.id),
                ("design_param_definition_id", "!=", False),
            ]
        )
        for lot in candidates:
            lot_params = dict(lot.design_params or {})
            if all(lot_params.get(k) == v for k, v in required_params.items()):
                return lot
        return self.browse()
