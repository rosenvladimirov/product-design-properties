/** @odoo-module **/
// Copyright 2026 BL Consulting
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

// Both legacy (≤ 0.49) and modern (≥ 0.50) zen-engine decision-table
// node types — `_migrate_node_types` rewrites the legacy form on every
// evaluate, but the widget must read both so we don't break editors of
// records that have already been normalised.
const DECISION_TABLE_TYPES = new Set(["decisionTable", "decisionTableNode"]);

/**
 * DMN decision table widget for GoRules JDM JSON fields.
 *
 * Read mode: visual grid with input (blue) and output (green) columns.
 * Edit mode: inline cell editing, add/remove rows and columns.
 */
export class DesignMatrixField extends Component {
    static template = "mrp_design_matrix.DesignMatrixField";
    static props = {
        ...standardFieldProps,
        tableType: { type: String, optional: true },
    };

    setup() {
        this.state = useState({
            collapsed: false,
            viewMode: "table", // "table" | "json"
            addingInput: false,
            addingOutput: false,
            newColName: "",
            dragIndex: null,
            dropIndex: null,
        });
    }

    // ── Mode ──────────────────────────────────────────────────────────

    get isEditing() {
        return !this.props.readonly;
    }

    get isJsonView() {
        return this.state.viewMode === "json";
    }

    // ── Getters ────────────────────────────────────────────────────────

    get rawValue() {
        return this.props.record.data[this.props.name];
    }

    /** Extract the first decision-table node from the JDM structure.
     *
     *  Tolerates both the legacy bare-table layout (single node with
     *  ``type: "decisionTable"`` at ``nodes[0]``) and the modern
     *  ``inputNode → decisionTableNode → outputNode`` graph from
     *  zen-engine ≥ 0.50 — in which case ``nodes[0]`` is the inputNode
     *  and we must filter by type to find the actual table.
     */
    get table() {
        const raw = this.rawValue;
        if (!raw) return null;
        if (raw.nodes && raw.nodes.length) {
            return raw.nodes.find((n) => DECISION_TABLE_TYPES.has(n?.type)) || null;
        }
        if (raw.content) {
            return raw;
        }
        return null;
    }

    get tableName() {
        return this.table?.name || "";
    }

    get inputs() {
        return this.table?.content?.inputs || [];
    }

    get outputs() {
        return this.table?.content?.outputs || [];
    }

    get rules() {
        return this.table?.content?.rules || [];
    }

    get hitPolicy() {
        return this.table?.content?.hitPolicy || "collect";
    }

    get hitPolicyLabel() {
        const labels = {
            collect: "COLLECT",
            first: "FIRST",
            priority: "PRIORITY",
        };
        return labels[this.hitPolicy] || this.hitPolicy.toUpperCase();
    }

    get hitPolicyClass() {
        const classes = {
            collect: "o_dmn_hp_collect",
            first: "o_dmn_hp_first",
            priority: "o_dmn_hp_priority",
        };
        return classes[this.hitPolicy] || "";
    }

    get hasData() {
        return this.table !== null && this.rules.length > 0;
    }

    get hasTable() {
        return this.table !== null;
    }

    get isEmpty() {
        return !this.rawValue;
    }

    get totalColumns() {
        return this.inputs.length + this.outputs.length;
    }

    /** All column ids in order: inputs then outputs. */
    get allColumns() {
        const cols = [];
        for (const inp of this.inputs) {
            cols.push({ ...inp, isInput: true });
        }
        for (const out of this.outputs) {
            cols.push({ ...out, isInput: false });
        }
        return cols;
    }

    // ── Cell display helpers ───────────────────────────────────────────

    formatCell(value) {
        if (value === undefined || value === null || value === "") {
            return { display: "--", cssClass: "o_dmn_cell_empty" };
        }
        const str = String(value);

        if (str.startsWith('"') && str.endsWith('"') && str.length > 1) {
            try {
                const parsed = JSON.parse(str);
                return { display: parsed, cssClass: "" };
            } catch {
                // pass
            }
        }

        if (str === "true") return { display: "true", cssClass: "o_dmn_cell_bool" };
        if (str === "false") return { display: "false", cssClass: "o_dmn_cell_bool" };

        if (!isNaN(str) && str.trim() !== "") {
            return { display: str, cssClass: "o_dmn_cell_num" };
        }

        if (/^[><!]=?\s/.test(str)) {
            return { display: str, cssClass: "o_dmn_cell_op" };
        }

        if (str.startsWith("{")) {
            try {
                const obj = JSON.parse(str);
                const keys = Object.keys(obj);
                if (keys.length === 0) return { display: "{}", cssClass: "o_dmn_cell_json" };
                return {
                    display: `{${keys.join(", ")}}`,
                    cssClass: "o_dmn_cell_json",
                    title: str,
                };
            } catch {
                // pass
            }
        }

        return { display: str, cssClass: "" };
    }

    levelBadgeClass(value) {
        if (!value) return "";
        const str = String(value);
        let level = str;
        if (str.startsWith('"')) {
            try { level = JSON.parse(str); } catch { /* pass */ }
        }
        if (level === "error") return "o_dmn_badge_error";
        if (level === "warning") return "o_dmn_badge_warning";
        return "";
    }

    getRuleCells(rule) {
        const cells = [];
        for (const input of this.inputs) {
            cells.push({
                ...this.formatCell(rule[input.id]),
                isInput: true,
                colId: input.id,
            });
        }
        for (const output of this.outputs) {
            const formatted = this.formatCell(rule[output.id]);
            if (output.id === "level") {
                formatted.badgeClass = this.levelBadgeClass(rule[output.id]);
            }
            formatted.isInput = false;
            formatted.colId = output.id;
            cells.push(formatted);
        }
        return cells;
    }

    // ── JDM cell encoding/decoding ───────────────────────────────────

    /**
     * Decode a JDM cell value to human-readable form for editing.
     *
     * JDM stores:  "\"error\""   → user sees: error
     *              "true"        → user sees: true
     *              "> 3000"      → user sees: > 3000
     *              "1.0"         → user sees: 1.0
     *              ""            → user sees: (empty)
     */
    decodeCell(value) {
        if (value === undefined || value === null || value === "") return "";
        const str = String(value);
        // Quoted string → unquote: "\"error\"" → error
        if (str.startsWith('"') && str.endsWith('"') && str.length > 1) {
            try {
                return JSON.parse(str);
            } catch {
                // malformed, return as-is
            }
        }
        return str;
    }

    /**
     * Encode a human-readable value back to JDM cell format.
     *
     * user types: error     → stored: "\"error\""   (quoted string)
     *             true      → stored: "true"         (boolean)
     *             1.0       → stored: "1.0"          (number)
     *             > 3000    → stored: "> 3000"       (operator)
     *             {key: v}  → stored: "{key: v}"     (JSON object)
     *             (empty)   → stored: ""             (wildcard)
     */
    encodeCell(value) {
        if (value === "") return "";
        // Boolean
        if (value === "true" || value === "false") return value;
        // Number
        if (!isNaN(value) && value.trim() !== "") return value;
        // Operator expression
        if (/^[><!]=?\s/.test(value)) return value;
        // JSON object
        if (value.startsWith("{")) return value;
        // Already JDM-quoted (user manually typed quotes)
        if (value.startsWith('"') && value.endsWith('"') && value.length > 1) {
            return value;
        }
        // Plain text → wrap in JDM quotes
        return JSON.stringify(value);
    }

    /** Get decoded cell value for edit input display. */
    getCellRaw(rule, colId) {
        const val = rule[colId];
        return this.decodeCell(val);
    }

    // ── Drag & drop row reorder ──────────────────────────────────────

    onDragStart(ruleIndex, ev) {
        this.state.dragIndex = ruleIndex;
        ev.dataTransfer.effectAllowed = "move";
        ev.dataTransfer.setData("text/plain", String(ruleIndex));
        // Make the dragged row semi-transparent
        ev.target.closest("tr").classList.add("o_dmn_dragging");
    }

    onDragOver(ruleIndex, ev) {
        ev.preventDefault();
        ev.dataTransfer.dropEffect = "move";
        if (this.state.dropIndex !== ruleIndex) {
            this.state.dropIndex = ruleIndex;
        }
    }

    onDragLeave(ruleIndex, ev) {
        if (this.state.dropIndex === ruleIndex) {
            this.state.dropIndex = null;
        }
    }

    onDrop(ruleIndex, ev) {
        ev.preventDefault();
        const from = this.state.dragIndex;
        const to = ruleIndex;
        this.state.dragIndex = null;
        this.state.dropIndex = null;
        if (from === null || from === to) return;

        const jdm = this._cloneJDM();
        const content = this._getContent(jdm);
        if (!content) return;
        const [moved] = content.rules.splice(from, 1);
        content.rules.splice(to, 0, moved);
        this._save(jdm);
    }

    onDragEnd(ev) {
        this.state.dragIndex = null;
        this.state.dropIndex = null;
        // Clean up class from any lingering row
        const el = ev.target.closest("tr");
        if (el) el.classList.remove("o_dmn_dragging");
    }

    getDragClass(ruleIndex) {
        if (this.state.dropIndex === ruleIndex && this.state.dragIndex !== ruleIndex) {
            return this.state.dragIndex < ruleIndex ? "o_dmn_drop_below" : "o_dmn_drop_above";
        }
        return "";
    }

    // ── JSON rebuild & save ────────────────────────────────────────────

    /** Deep-clone the current JDM structure for mutation. */
    _cloneJDM() {
        const raw = this.rawValue;
        if (!raw) return null;
        return JSON.parse(JSON.stringify(raw));
    }

    /** Get mutable content from a cloned JDM. Same tolerance as :py:meth:`table`. */
    _getContent(jdm) {
        if (jdm.nodes && jdm.nodes.length) {
            const node = jdm.nodes.find((n) => DECISION_TABLE_TYPES.has(n?.type));
            return node ? node.content : null;
        }
        if (jdm.content) {
            return jdm.content;
        }
        return null;
    }

    /** Persist the modified JDM to the record. */
    _save(jdm) {
        this.props.record.update({ [this.props.name]: jdm });
    }

    // ── Edit actions ──────────────────────────────────────────────────

    toggleCollapse() {
        this.state.collapsed = !this.state.collapsed;
    }

    toggleViewMode() {
        this.state.viewMode = this.state.viewMode === "table" ? "json" : "table";
    }

    /** Change hitPolicy and persist to JDM. */
    onHitPolicyChange(ev) {
        ev.stopPropagation();
        const jdm = this._cloneJDM();
        const content = this._getContent(jdm);
        if (!content) return;
        content.hitPolicy = ev.target.value;
        this._save(jdm);
    }

    /** Get formatted JSON string for display/editing. */
    get jsonString() {
        const raw = this.rawValue;
        if (!raw) return "";
        return JSON.stringify(raw, null, 2);
    }

    /** Update field value from raw JSON textarea. */
    onJsonChange(ev) {
        const text = ev.target.value.trim();
        if (!text) return;
        try {
            const parsed = JSON.parse(text);
            this._save(parsed);
        } catch {
            // Invalid JSON — do not save
        }
    }

    /** Update a single cell value with smart encoding. */
    onCellChange(ruleIndex, colId, ev) {
        const jdm = this._cloneJDM();
        const content = this._getContent(jdm);
        if (!content) return;
        content.rules[ruleIndex][colId] = this.encodeCell(ev.target.value.trim());
        this._save(jdm);
    }

    /** Add an empty rule row. */
    addRule() {
        const jdm = this._cloneJDM() || this._createEmptyJDM();
        const content = this._getContent(jdm);
        if (!content) return;
        const row = {};
        for (const inp of content.inputs) {
            row[inp.id] = "";
        }
        for (const out of content.outputs) {
            row[out.id] = "";
        }
        content.rules.push(row);
        this._save(jdm);
    }

    /** Remove a rule row by index. */
    removeRule(ruleIndex) {
        const jdm = this._cloneJDM();
        const content = this._getContent(jdm);
        if (!content) return;
        content.rules.splice(ruleIndex, 1);
        this._save(jdm);
    }

    /** Start adding input column — show name field. */
    startAddInput() {
        this.state.addingInput = true;
        this.state.addingOutput = false;
        this.state.newColName = "";
    }

    /** Start adding output column — show name field. */
    startAddOutput() {
        this.state.addingInput = false;
        this.state.addingOutput = true;
        this.state.newColName = "";
    }

    /** Cancel adding a column. */
    cancelAddCol() {
        this.state.addingInput = false;
        this.state.addingOutput = false;
        this.state.newColName = "";
    }

    onNewColNameInput(ev) {
        this.state.newColName = ev.target.value;
    }

    /** Confirm adding the new column. */
    confirmAddCol(ev) {
        if (ev.type === "keydown" && ev.key !== "Enter") return;
        const name = this.state.newColName.trim();
        if (!name) return;

        const colId = name.toLowerCase().replace(/\s+/g, "_");
        const jdm = this._cloneJDM() || this._createEmptyJDM();
        const content = this._getContent(jdm);
        if (!content) return;

        // ``field`` мирори ``id`` — изисквано от zen-engine ≥ 0.50.
        const colDef = { id: colId, name: name, field: colId };

        if (this.state.addingInput) {
            // Check duplicate
            if (content.inputs.some((c) => c.id === colId)) return;
            content.inputs.push(colDef);
        } else {
            if (content.outputs.some((c) => c.id === colId)) return;
            content.outputs.push(colDef);
        }

        // Add empty key to all existing rules
        for (const rule of content.rules) {
            if (!(colId in rule)) {
                rule[colId] = "";
            }
        }

        this.cancelAddCol();
        this._save(jdm);
    }

    /** Remove an input or output column. */
    removeColumn(colId, isInput) {
        const jdm = this._cloneJDM();
        const content = this._getContent(jdm);
        if (!content) return;

        if (isInput) {
            content.inputs = content.inputs.filter((c) => c.id !== colId);
        } else {
            content.outputs = content.outputs.filter((c) => c.id !== colId);
        }

        // Remove key from all rules
        for (const rule of content.rules) {
            delete rule[colId];
        }

        this._save(jdm);
    }

    /** Create a blank JDM structure when field is empty.
     *
     *  Emits the modern zen-engine ≥ 0.50 graph: ``inputNode →
     *  decisionTableNode → outputNode`` with edges. Avoids the runtime
     *  patches that ``ZenWrapper._migrate_node_types`` applies for the
     *  legacy bare-table layout.
     */
    _createEmptyJDM() {
        const tableType = this.props.tableType || "t0";
        const names = {
            t0: "T0 Constraints",
            t1: "T1 Geometry",
            t2: "T2 Materials",
            t3: "T3 Operations",
            tpi: "TΠ Availability",
            tphi: "TΦ Cascade",
        };
        return {
            nodes: [
                { id: "zen_input", name: "Input", type: "inputNode" },
                {
                    id: tableType,
                    name: names[tableType] || "Decision Table",
                    type: "decisionTableNode",
                    content: {
                        hitPolicy: "collect",
                        inputs: [],
                        outputs: [],
                        rules: [],
                    },
                },
                { id: "zen_output", name: "Output", type: "outputNode" },
            ],
            edges: [
                { id: "zen_edge_in", sourceId: "zen_input", targetId: tableType },
                { id: "zen_edge_out", sourceId: tableType, targetId: "zen_output" },
            ],
        };
    }

    /** Create initial table for empty field in edit mode. */
    createTable() {
        const jdm = this._createEmptyJDM();
        this._save(jdm);
    }
}

export const designMatrixField = {
    component: DesignMatrixField,
    displayName: "Design Matrix",
    supportedTypes: ["json"],
    extractProps: ({ options }) => ({
        tableType: options?.table_type,
    }),
};

registry.category("fields").add("design_matrix", designMatrixField);
