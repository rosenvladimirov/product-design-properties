# Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json
import logging
import os
import secrets
from xml.etree import ElementTree as ET

from odoo import addons, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

XML_FILENAME = "design_param_definitions.xml"


class DesignParamDefinition(models.Model):
    """
    Defines a named set of design parameters for a specific industry.

    Parameter definitions are loaded from a custom XML file shipped with
    each industry data file via ``create_design_param_definitions()``.

    Uses ``design.param.definition`` as model name, shared across
    all modules that depend on ``design_param_base``.
    """

    _name = "design.param.definition"
    _description = "Design Parameter Definition"
    _rec_name = "code"
    _order = "sequence, code"

    sequence = fields.Integer(default=10)
    code = fields.Char(required=True)
    name = fields.Char(required=True)
    industry_id = fields.Many2one(
        "design.industry",
        string="Industry",
        ondelete="restrict",
        index=True,
        help="Canonical industry classification. Resolved automatically "
        "from the data tag (e.g. industry=\"bags\") via "
        "design.industry._resolve — no data-file changes needed.",
    )
    parent_id = fields.Many2one(
        "design.param.definition",
        string="Parent Definition",
        help="Inherit parameter definitions from parent.",
    )
    design_params_definition = fields.PropertiesDefinition(
        "Design Parameter Definitions",
    )
    full_design_params_definition = fields.PropertiesDefinition(
        "Full Design Parameter Definitions (with inherited)",
        compute="_compute_full_design_params_definition",
    )

    # NEW fields:
    company_ids = fields.Many2many(
        "res.company",
        string="Enabled Companies",
        help="If empty, available for all companies.",
    )
    validation_rules = fields.Json(
        help="JSON array of validation rules for client-side evaluation.",
    )
    profile_ids = fields.One2many(
        "design.param.profile",
        "definition_id",
        string="SVG Profiles",
    )

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "The code must be unique.",
    )

    # -- Zero-churn industry resolution --------------------------------------
    # Историческият парсер и data файловете подават `industry` като свободен
    # стринг (attr.get("industry","")). Тук го прехващаме и резолваме към
    # design.industry → 8-те sibling модула остават непокътнати.

    @api.model
    def _pop_industry_tag(self, vals):
        """Translate a string ``industry`` key in *vals* to ``industry_id``."""
        if "industry" in vals and not isinstance(vals.get("industry"), int):
            tag = vals.pop("industry")
            industry = self.env["design.industry"].sudo()._resolve(tag)
            vals["industry_id"] = industry.id or False
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._pop_industry_tag(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._pop_industry_tag(vals)
        return super().write(vals)

    def _compute_full_design_params_definition(self):
        """Merge parent chain properties with own properties.

        Base definition (e.g. 'base_dimensions') provides width/height/thickness.
        Industry definition (e.g. 'interior_door') adds its own properties.
        Full = parent chain properties + own properties (own overrides parent by name).
        """
        for record in self:
            merged = []
            seen_strings = set()
            # Collect parent chain (bottom-up, then reverse)
            chain = []
            current = record
            while current:
                chain.append(current)
                current = current.parent_id
            # Apply top-down (base first, then child overrides)
            for defn in reversed(chain):
                for prop in defn.design_params_definition or []:
                    prop_string = prop.get("string", "")
                    if prop_string in seen_strings:
                        # Override: replace existing
                        merged = [
                            p if p.get("string") != prop_string else prop
                            for p in merged
                        ]
                    else:
                        merged.append(prop)
                        seen_strings.add(prop_string)
            record.full_design_params_definition = merged

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
        text = item.text or ""
        if text.startswith("[") or text.startswith("{"):
            try:
                text = json.loads(text)
            except json.JSONDecodeError:
                _logger.debug(
                    "Failed to JSON-parse item text %r — using as string",
                    text,
                )
        return {attr.get("name"): text}

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
        # Coerce default value to the declared type so Owl widgets
        # (formatInteger/formatFloat/Boolean checkbox) don't crash on strings.
        type_ = result.get("type")
        default = result.get("default")
        if isinstance(default, str):
            try:
                if type_ == "integer":
                    result["default"] = int(default)
                elif type_ == "float":
                    result["default"] = float(default)
                elif type_ == "boolean":
                    result["default"] = default.strip().lower() in (
                        "true",
                        "1",
                        "yes",
                    )
            except (TypeError, ValueError):
                pass
        return result

    def _process_properties(self, properties, sequence):
        """Parse one ``<properties>`` node into a create-values dict.

        Supports ``parent="code"`` attribute to link to a parent definition.
        The parent must already exist in the database.

        Example::

            <properties code="interior_door" name="Interior Door"
                        industry="doors" parent="base_dimensions">
                <items name="construction">...</items>
            </properties>
        """
        attr = properties.attrib
        props = [self._process_items(items) for items in properties.iter("items")]
        vals = {
            "sequence": sequence,
            "code": attr.get("code"),
            "name": attr.get("name"),
            "industry": attr.get("industry", ""),
            "design_params_definition": props,
        }
        parent_code = attr.get("parent")
        if parent_code:
            parent = self.search([("code", "=", parent_code)], limit=1)
            if parent:
                vals["parent_id"] = parent.id
        return vals

    @api.model
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
            to_delete = self.search([("code", "in", [v["code"] for v in values])])
            to_delete.unlink()
            self.create(values)
