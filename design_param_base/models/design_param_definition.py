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
    # Четим read-only преглед на параметрите. PropertiesDefinition widget-ът НЕ се
    # рендерира самостоятелно във формата (показва схема само сдвоен с Properties
    # поле), затова дефиниционната форма изглежда празна — тук се вижда какво
    # съдържа дефиницията (име + тип на всеки параметър).
    params_overview = fields.Text(
        "Parameters",
        compute="_compute_params_overview",
    )

    @api.depends("design_params_definition")
    def _compute_params_overview(self):
        for rec in self:
            lines = []
            for it in rec.design_params_definition or []:
                label = it.get("string") or it.get("name") or "?"
                typ = it.get("type") or "?"
                extra = ""
                if typ == "selection" and it.get("selection"):
                    extra = " [%s]" % ", ".join(
                        v[1] if isinstance(v, (list, tuple)) and len(v) > 1
                        else str(v)
                        for v in it["selection"])
                lines.append("• %s  (%s)%s" % (label, typ, extra))
            rec.params_overview = "\n".join(lines)

    full_design_params_definition = fields.PropertiesDefinition(
        "Full Design Parameter Definitions (with inherited)",
        compute="_compute_full_design_params_definition",
        search="_search_full_design_params_definition",
    )

    def _search_full_design_params_definition(self, operator, value):
        """Полето е computed (merge на parent chain + BoM компоненти) и НЕ е
        stored → не може да влезе в SQL WHERE. Odoo 19 при резолюция на
        Properties дефиницията го търси → ValueError „not stored".

        Връщаме безопасен match-all домейн (всеки запис има id), за да не
        гърми; реалната дефиниция се резолвва през m2o design_param_definition_id,
        не по стойността на това поле.
        """
        return [("id", "!=", False)]

    # NEW fields:
    company_ids = fields.Many2many(
        "res.company",
        string="Enabled Companies",
        help="If empty, available for all companies.",
    )
    validation_rules = fields.Json(
        help="JSON array of validation rules for client-side evaluation.",
    )
    param_levels = fields.Json(
        help="Maps each design parameter (by name) to its access level: "
        "sales | technical | production. Authored per-parameter in the data "
        "XML via <item name=\"level\">…</item> and extracted here, because "
        "Odoo PropertiesDefinition rejects unknown keys inside a parameter. "
        "Drives configurator field visibility and the "
        "sales -> technical -> production workflow; the matrix is unaffected.",
    )
    # Семантични роли per параметър (същия shape като param_levels: label →
    # role). Каналът, който маха хардкоднатите (кирилски) label-сравнения от
    # конфигуратора: JS търси по РОЛЯ, не по надпис. Роли: width | height |
    # wall_width | opening_direction | rebuild | numeric | operation |
    # hide_in_description | lip_overlap | lip_depth.
    param_roles = fields.Json(
        help="Maps a design parameter label to its semantic role for the "
        "configurator (width, height, wall_width, opening_direction, "
        "rebuild, numeric, operation, hide_in_description, lip_overlap, "
        "lip_depth). Lets the UI resolve parameters by ROLE instead of "
        "hardcoded display labels, so any industry vertical can drive the "
        "same 3D/cost logic with its own parameter names.",
    )
    param_dictionary = fields.Json(
        help="Canonical name registry, replicated to matrix/product/bom. Shape:\n"
        "  {formula_name: {\"uuid\": <property key>,\n"
        "                  \"name\": {\"en_US\": ..., \"bg_BG\": ...},\n"
        "                  \"aliases\": [<legacy/display names>]}}\n"
        "Three decoupled roles: UUID = storage key in the lot JSONB; formula_name "
        "= the ONLY identifier formulas read (stable, snake_case ASCII); name = a "
        "jsonb translation map for the UI (free to change without touching formulas). "
        "Authored in the data XML via <item name=\"formula_name\">/<item name=\"name_bg\">"
        "/<item name=\"alias\">, extracted here because Odoo PropertiesDefinition "
        "rejects unknown keys inside a parameter.",
    )
    legacy_aliases = fields.Json(
        help="Flat projection {alias: formula_name} for fast lookup when building "
        "the design context — lets legacy c_* (and Cyrillic display) formulas "
        "resolve to canonical formula_names WITHOUT rewriting the formulas.",
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

    # -- Canonical name registry resolution ----------------------------------
    # Речникът се наследява по parent chain: vertical (напр. security_door)
    # дефинира канона, client overlay (solid_door) само добавя/разширява aliases.

    def _chain_bottom_up(self):
        """Return the parent chain as a list [self, parent, grandparent, ...]."""
        self.ensure_one()
        chain = []
        current = self
        while current:
            chain.append(current)
            current = current.parent_id
        return chain

    def _get_merged_param_dictionary(self):
        """Merge ``param_dictionary`` along the parent chain (child wins per
        formula_name). Returns {formula_name: {uuid, name:{lang}, aliases:[]}}."""
        merged = {}
        for defn in reversed(self._chain_bottom_up()):
            if defn.param_dictionary:
                merged.update(defn.param_dictionary)
        return merged

    def _get_merged_legacy_aliases(self):
        """Merge ``legacy_aliases`` along the parent chain (child wins).
        Returns the flat {alias: formula_name} map used to expand the design
        context so legacy c_* / display-name formulas resolve to canonical."""
        merged = {}
        for defn in reversed(self._chain_bottom_up()):
            if defn.legacy_aliases:
                merged.update(defn.legacy_aliases)
        return merged

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
        props = []
        param_levels = {}
        param_dictionary = {}
        legacy_aliases = {}
        for items in properties.iter("items"):
            prop = self._process_items(items)
            # Всички ключове извън схемата на Odoo PropertiesDefinition (тя отхвърля
            # непознати ключове) се изваждат настрана ПРЕДИ create — същият патърн
            # като `level`. Матрицата/формулите не се влияят от display промени.
            level = prop.pop("level", None)
            formula_name = prop.pop("formula_name", None)
            name_en = prop.pop("name_en", None)
            name_bg = prop.pop("name_bg", None)
            aliases = prop.pop("aliases", None)
            single_alias = prop.pop("alias", None)
            if level:
                param_levels[prop["string"]] = level
            if formula_name:
                # Събери алиасите (списък или единичен) в чист списък.
                alias_list = []
                if isinstance(aliases, list):
                    alias_list.extend(aliases)
                elif aliases:
                    alias_list.append(aliases)
                if single_alias:
                    alias_list.append(single_alias)
                # display = jsonb превод; en база = name_en или string, bg = name_bg.
                name_map = {"en_US": name_en or prop.get("string")}
                if name_bg:
                    name_map["bg_BG"] = name_bg
                param_dictionary[formula_name] = {
                    "uuid": prop["name"],
                    "name": name_map,
                    "aliases": alias_list,
                }
                # Плоска проекция за бърз резолв; формулното име резолва и към себе си.
                legacy_aliases[formula_name] = formula_name
                for a in alias_list:
                    legacy_aliases[a] = formula_name
            props.append(prop)
        vals = {
            "sequence": sequence,
            "code": attr.get("code"),
            "name": attr.get("name"),
            "industry": attr.get("industry", ""),
            "design_params_definition": props,
        }
        if param_levels:
            vals["param_levels"] = param_levels
        if param_dictionary:
            vals["param_dictionary"] = param_dictionary
        if legacy_aliases:
            vals["legacy_aliases"] = legacy_aliases
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

    @api.model
    def load_param_bridge(self, module_name, filename):
        """Apply a name-bridge (``param_dictionary`` + ``legacy_aliases``) onto
        EXISTING definitions, keyed by ``code``, WITHOUT touching their
        ``design_params_definition`` — so the stored Property UUIDs (and thus
        every existing lot's values) stay intact.

        Used for ``solid_door_full`` (def3), which was created manually on
        staging (not from XML); re-creating it would mint new UUIDs and orphan
        the lots. This loader only writes the two side registries.

        JSON shape (``<module>/data/<filename>``)::

            {"solid_door_full": {"param_dictionary": {...},
                                 "legacy_aliases": {...}}}

        Json fields serialize via json.dumps (not the translate-jsonb repr
        path), so writing a Python dict here is safe.
        """
        data_path = self._get_module_data_path(module_name)
        path = os.path.join(data_path, filename)
        if not os.path.exists(path):
            _logger.warning("Param bridge file not found: %s", path)
            return False
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        applied = 0
        for code, payload in data.items():
            defn = self.search([("code", "=", code)], limit=1)
            if not defn:
                _logger.warning(
                    "Param bridge: definition %r not found — skipped "
                    "(expected on a fresh DB where def3 is not yet declarative).",
                    code,
                )
                continue
            vals = {}
            if payload.get("param_dictionary"):
                merged = dict(defn.param_dictionary or {})
                merged.update(payload["param_dictionary"])
                vals["param_dictionary"] = merged
            if payload.get("legacy_aliases"):
                merged = dict(defn.legacy_aliases or {})
                merged.update(payload["legacy_aliases"])
                vals["legacy_aliases"] = merged
            if vals:
                defn.write(vals)
                applied += 1
                _logger.info(
                    "Param bridge applied to %r: %d formula_names, %d aliases.",
                    code,
                    len(payload.get("param_dictionary") or {}),
                    len(payload.get("legacy_aliases") or {}),
                )
        return applied

    @api.model
    def add_new_params(self, module_name, filename):
        """Append NEW design parameters to existing definitions (keyed by code)
        — for formulas that read a token with no def3 equivalent (e.g. generic
        ``optionsN`` checkboxes). Mints a fresh Property UUID per new param and
        APPENDS it to ``design_params_definition`` (existing UUIDs untouched),
        then registers it in ``param_dictionary`` + ``legacy_aliases``.

        Idempotent: a formula_name already present is skipped, so re-running on
        ``-u`` is safe and won't duplicate Properties.

        JSON shape (``<module>/data/<filename>``)::

            {"solid_door_full": [
              {"formula_name": "options4", "name_bg": "Опция 4",
               "type": "boolean", "default": false,
               "aliases": ["c_checkOptions4"]}
            ]}
        """
        data_path = self._get_module_data_path(module_name)
        path = os.path.join(data_path, filename)
        if not os.path.exists(path):
            _logger.warning("New-params file not found: %s", path)
            return False
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        added = 0
        for code, params in data.items():
            defn = self.search([("code", "=", code)], limit=1)
            if not defn:
                _logger.warning(
                    "add_new_params: definition %r not found — skipped.", code
                )
                continue
            props = list(defn.design_params_definition or [])
            registry = dict(defn.param_dictionary or {})
            aliases = dict(defn.legacy_aliases or {})
            changed = False
            for spec in params:
                fn = spec["formula_name"]
                if fn in registry:
                    continue  # idempotent — вече добавен
                uuid = self._generate_uuid()
                name_bg = spec.get("name_bg")
                prop = {
                    "name": uuid,
                    "string": name_bg or fn,
                    "type": spec.get("type", "boolean"),
                }
                if "default" in spec:
                    prop["default"] = spec["default"]
                props.append(prop)
                name_map = {"en_US": fn}
                if name_bg:
                    name_map["bg_BG"] = name_bg
                registry[fn] = {
                    "uuid": uuid,
                    "name": name_map,
                    "aliases": spec.get("aliases", []),
                }
                aliases[fn] = fn
                for a in spec.get("aliases", []):
                    aliases[a] = fn
                changed = True
                added += 1
            if changed:
                defn.write({
                    "design_params_definition": props,
                    "param_dictionary": registry,
                    "legacy_aliases": aliases,
                })
                _logger.info(
                    "add_new_params: %r — appended new params (total now %d).",
                    code, len(props),
                )
        return added
