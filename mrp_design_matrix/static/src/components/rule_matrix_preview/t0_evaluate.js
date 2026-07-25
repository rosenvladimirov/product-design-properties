/** @odoo-module **/
// Copyright 2026 Rosen Vladimirov, Terraros Commerce Ltd.
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

/**
 * Shared T0 evaluation utilities.
 *
 * Pure functions extracted from RuleMatrixPreview so both the inline
 * BoM preview and the SO line widget can evaluate T0 constraints
 * without instantiating a full OWL component.
 */

/**
 * Coerce a matrix table field value to an object (or false).
 * Handles double-encoded JSON strings that occasionally land in jsonb
 * columns when serializers stringify already-serialized values.
 */
export function coerceTable(raw) {
    if (!raw) return false;
    if (typeof raw === "string") {
        try {
            const parsed = JSON.parse(raw);
            return parsed && typeof parsed === "object" ? parsed : false;
        } catch {
            return false;
        }
    }
    return typeof raw === "object" ? raw : false;
}

/**
 * Extract the first decision table content from a JDM structure.
 */
export function getTableContent(table) {
    const obj = coerceTable(table);
    if (!obj) return null;
    if (obj.nodes && obj.nodes.length) {
        return obj.nodes[0].content || null;
    }
    if (obj.content) {
        return obj.content;
    }
    return null;
}

/**
 * Evaluate a single rule against current params.
 * Returns true if ALL input conditions match (rule fires).
 * Empty cell = wildcard (always matches).
 */
export function evaluateRule(rule, params, inputs) {
    for (const input of inputs) {
        const ruleVal = rule[input.id];
        if (!ruleVal && ruleVal !== false && ruleVal !== 0) continue;

        const paramVal = params[input.id];
        if (paramVal === undefined) continue;

        if (!matchCell(ruleVal, paramVal)) return false;
    }
    return true;
}

/**
 * Match a single JDM cell value against a param value.
 */
export function matchCell(ruleVal, paramVal) {
    const str = String(ruleVal);

    // Empty = wildcard
    if (str === "") return true;

    // Quoted string: exact match
    if (str.startsWith('"') && str.endsWith('"') && str.length > 1) {
        try {
            return paramVal === JSON.parse(str);
        } catch {
            return false;
        }
    }

    // Boolean
    if (str === "true") return paramVal === true;
    if (str === "false") return paramVal === false;

    // Comparison operators
    if (str.startsWith(">= ")) return Number(paramVal) >= parseFloat(str.slice(3));
    if (str.startsWith("<= ")) return Number(paramVal) <= parseFloat(str.slice(3));
    if (str.startsWith("> "))  return Number(paramVal) > parseFloat(str.slice(2));
    if (str.startsWith("< "))  return Number(paramVal) < parseFloat(str.slice(2));

    // Not-equal
    if (str.startsWith("!= ")) {
        const cmp = str.slice(3).trim();
        if (cmp.startsWith('"')) {
            try { return paramVal !== JSON.parse(cmp); } catch { return false; }
        }
        return paramVal !== cmp;
    }

    // Contains
    if (str.startsWith("contains ")) {
        const needle = str.slice(9).trim();
        const unquoted = needle.startsWith('"') && needle.endsWith('"')
            ? JSON.parse(needle)
            : needle;
        return String(paramVal).includes(unquoted);
    }

    // Numeric equality
    if (!isNaN(str) && str.trim() !== "") {
        return Number(paramVal) === parseFloat(str);
    }

    // Fallback: string equality
    return String(paramVal) === str;
}

/**
 * Extract an output value from a rule, decoding JDM quoting.
 */
export function extractOutput(rule, outputs, outputId) {
    const out = outputs.find(o => o.id === outputId);
    if (!out) return "";
    const val = rule[out.id];
    if (!val && val !== false && val !== 0) return "";
    const str = String(val);
    if (str.startsWith('"') && str.endsWith('"') && str.length > 1) {
        try { return JSON.parse(str); } catch { /* pass */ }
    }
    return str;
}

/**
 * Decode a JDM value to its native form.
 * "\"error\"" -> "error", "3.5" -> 3.5, "true" -> true
 */
export function decodeJDMValue(raw) {
    if (raw === undefined || raw === null) return "";
    const str = String(raw);
    if (str.startsWith('"') && str.endsWith('"') && str.length > 1) {
        try { return JSON.parse(str); } catch { /* pass */ }
    }
    if (str === "true") return true;
    if (str === "false") return false;
    if (!isNaN(str) && str.trim() !== "") return parseFloat(str);
    return str;
}

/**
 * Build a human-readable description of a rule's input conditions.
 * e.g., "width < 600" or "construction = glass, leaf_type = double"
 */
export function buildRuleDescription(rule, inputs) {
    const parts = [];
    for (const input of inputs) {
        const val = rule[input.id];
        if (!val && val !== false && val !== 0) continue;
        const str = String(val);
        if (str === "") continue;

        const name = input.name || input.id;
        let display = str;
        if (str.startsWith('"') && str.endsWith('"') && str.length > 1) {
            try { display = `= ${JSON.parse(str)}`; } catch { /* pass */ }
        } else if (/^[><!]=?\s/.test(str)) {
            display = str;
        } else if (str === "true" || str === "false") {
            display = `= ${str}`;
        } else {
            display = `= ${str}`;
        }
        parts.push(`${name} ${display}`);
    }
    return parts.join(", ") || "\u2014";
}

/**
 * Evaluate T0 constraints. Returns { results, hitPolicy } or null.
 *
 * Each result: { matched, level, message, description, icon, cssClass }
 */
export function evaluateT0(params, constraintTable) {
    const table = getTableContent(constraintTable);
    if (!table) return null;

    const inputs = table.inputs || [];
    const outputs = table.outputs || [];
    const rules = table.rules || [];
    const hitPolicy = table.hitPolicy || "collect";

    const results = [];
    for (const rule of rules) {
        const matched = evaluateRule(rule, params, inputs);
        const level = extractOutput(rule, outputs, "level");
        const message = extractOutput(rule, outputs, "message");
        const description = buildRuleDescription(rule, inputs);

        results.push({
            matched,
            level: matched ? level : "ok",
            message: matched ? message : description,
            description,
            icon: matched
                ? level === "error" ? "fa-times-circle" : "fa-exclamation-triangle"
                : "fa-check-circle",
            cssClass: matched
                ? level === "error" ? "error" : "warning"
                : "ok",
        });
    }
    return { results, hitPolicy };
}
