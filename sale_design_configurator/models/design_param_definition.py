# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import os
import secrets
from xml.etree import ElementTree as ET

from odoo import addons, fields, models
from odoo.exceptions import UserError

XML_FILENAME = "design_param_definitions.xml"


class DesignParamDefinition(models.Model):
    """
    Defines a named set of design parameters for a specific industry.

    Parameter definitions are loaded from a custom XML file shipped with
    each industry data file via ``create_design_param_definitions()``.

    Uses ``design.param.definition`` as model name to avoid conflict
    with ``mrp.design.param.definition`` from the mrp_design_matrix module.
    """

    _name = "design.param.definition"
    _description = "Design Parameter Definition"
    _rec_name = "code"
    _order = "sequence, code"

    sequence = fields.Integer(default=10)
    code = fields.Char(required=True)
    name = fields.Char(required=True)
    industry = fields.Char(
        help="Industry tag for filtering: bags, doors, corrugated, etc."
    )
    parent_id = fields.Many2one(
        "design.param.definition",
        string="Parent Definition",
        help="Inherit parameter definitions from parent.",
    )
    design_params_definition = fields.PropertiesDefinition(
        "Design Parameter Definitions",
    )

    _sql_constraints = [
        ("code_unique", "UNIQUE(code)", "The code must be unique."),
    ]

    # -- XML loading ---------------------------------------------------------

    @staticmethod
    def _get_module_data_path(module_name):
        """Return the absolute path to the ``data/`` directory of *module_name*."""
        for adp in addons.__path__:
            mp = os.path.join(adp, module_name)
            if os.path.isdir(mp):
                return os.path.join(mp, "data")
        return ""

    @staticmethod
    def _process_item(item):
        """Parse a single ``<item>`` node."""
        attr = item.attrib
        return {attr.get("name"): item.text or ""}

    @staticmethod
    def _generate_uuid():
        return secrets.token_hex(8)

    def _process_items(self, items):
        """Parse one ``<items>`` node into a PropertiesDefinition entry."""
        attr = items.attrib
        result = {
            "name": self._generate_uuid(),
            "string": attr.get("name"),
        }
        for item in items.iter("item"):
            result.update(self._process_item(item))
        return result

    def _process_properties(self, properties, sequence):
        """Parse one ``<properties>`` node into a create-values dict."""
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

    def create_design_param_definitions(self, module_name, codes=False):
        """
        Load (or reload) parameter definitions from the XML file in
        ``<module_name>/data/design_param_definitions.xml``.

        Called from ``data/install_design_params.xml``:

        .. code-block:: xml

            <function model="design.param.definition"
                      name="create_design_param_definitions">
                <value>sale_design_configurator</value>
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
