# Copyright 2026 BL Consulting
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import os
from xml.etree import ElementTree as ET

from odoo import addons, fields, models
from odoo.exceptions import UserError

XML_FILENAME = "design_param_definitions.xml"


class MrpDesignParamDefinition(models.Model):
    """
    Defines a named set of design parameters for a specific industry.

    This model is the analogue of `component.definition.properties` from
    the `product_electrical_properties` module.

    Parameter definitions are loaded from a custom XML file shipped with
    each industry sub-module via `create_design_param_definitions()`.
    """

    _name = "mrp.design.param.definition"
    _description = "Design Parameter Definition"
    _rec_name = "code"
    _order = "sequence, code"

    sequence = fields.Integer(default=10)
    code = fields.Char(required=True)
    name = fields.Char(required=True)
    industry = fields.Char(
        help="Industry tag for filtering: bags, doors, corrugated, …"
    )
    parent_id = fields.Many2one(
        "mrp.design.param.definition",
        string="Parent Definition",
        help="Inherit parameter definitions from parent.",
    )
    design_params_definition = fields.PropertiesDefinition(
        "Design Parameter Definitions",
    )

    _sql_constraints = [
        ("code_unique", "UNIQUE(code)", "The code must be unique."),
    ]

    # ── XML loading ───────────────────────────────────────────────────────

    @staticmethod
    def _get_module_data_path(module_name):
        for adp in addons.__path__:
            mp = os.path.join(adp, module_name)
            if os.path.isdir(mp):
                return os.path.join(mp, "data")
        return ""

    @staticmethod
    def _process_item(item):
        attr = item.attrib
        return {attr.get("name"): item.text or ""}

    def _process_items(self, items):
        """Parse one <items> node into a PropertiesDefinition entry."""
        attr = items.attrib
        result = {
            "name": self._generate_uuid(),
            "string": attr.get("name"),
        }
        for item in items.iter("item"):
            result.update(self._process_item(item))
        return result

    def _process_properties(self, properties, sequence):
        """Parse one <properties> node into a create-values dict."""
        attr = properties.attrib
        props = [
            self._process_items(items)
            for items in properties.iter("items")
        ]
        return {
            "sequence": sequence,
            "code": attr.get("code"),
            "name": attr.get("name"),
            "industry": attr.get("industry", ""),
            "design_params_definition": props,
        }

    @staticmethod
    def _generate_uuid():
        import secrets
        return secrets.token_hex(8)

    def create_design_param_definitions(self, module_name, codes=False):
        """
        Load (or reload) parameter definitions from the XML file in
        ``<module_name>/data/design_param_definitions.xml``.

        Called from ``data/install_design_params.xml`` in each sub-module:

        .. code-block:: xml

            <function model="mrp.design.param.definition"
                      name="create_design_param_definitions">
                <value>mrp_design_matrix_bags</value>
            </function>

        :param module_name: Odoo module name whose data dir contains the XML.
        :param codes: optional list of codes to reload (empty = all).
        """
        data_path = self._get_module_data_path(module_name)
        if not data_path:
            raise UserError(f"Module data path not found: {module_name}")

        xml_path = os.path.join(data_path, XML_FILENAME)
        if not os.path.exists(xml_path):
            raise UserError(f"XML file not found: {xml_path}")

        try:
            root = ET.parse(xml_path).getroot()
        except ET.ParseError as e:
            raise UserError(f"Error parsing XML: {e}") from e

        values = []
        for seq, props in enumerate(root.iter("properties")):
            code = props.attrib.get("code")
            if codes and code not in codes:
                continue
            values.append(self._process_properties(props, seq))

        if values:
            to_delete = self.search(
                [("code", "in", [v["code"] for v in values])]
            )
            to_delete.unlink()
            self.create(values)
