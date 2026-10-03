// Copyright 2026 Rosen Vladimirov, Terraros Commerce Ltd.
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

// Таблицата се намира по тип, не по позиция: нормализираният граф започва с
// inputNode (normalize_jdm_graph), заварената плоска таблица — с таблицата.
import { expect, test } from "@odoo/hoot";
import {
    evaluateT0,
    findDecisionNode,
    getTableContent,
} from "@mrp_design_matrix/components/rule_matrix_preview/t0_evaluate";

// правило като r1 на T0 на BoM 36: ширина под 900 е грешка
const CONTENT = {
    hitPolicy: "collect",
    inputs: [{ id: "width", name: "width", field: "width" }],
    outputs: [
        { id: "level", name: "level", field: "level" },
        { id: "message", name: "message", field: "message" },
    ],
    rules: [{ _id: "r1", width: "< 900", level: '"error"', message: '"Too narrow"' }],
};

// каквото връща normalize_jdm_graph (base_zen_decision/models/zen_engine.py)
const NORMALIZED = {
    nodes: [
        { id: "t0-in", type: "inputNode", name: "Request" },
        { id: "t0", type: "decisionTableNode", name: "T0", content: CONTENT },
        { id: "t0-out", type: "outputNode", name: "Response" },
    ],
    edges: [
        { id: "e1", sourceId: "t0-in", targetId: "t0" },
        { id: "e2", sourceId: "t0", targetId: "t0-out" },
    ],
};

const FLAT = { nodes: [{ id: "t0", type: "decisionTable", name: "T0", content: CONTENT }] };

test("нормализираният граф дава таблицата, не входния възел", () => {
    expect(findDecisionNode(NORMALIZED).id).toBe("t0");
    expect(getTableContent(NORMALIZED)).toBe(CONTENT);
});

test("заварената плоска таблица се чете както преди", () => {
    expect(getTableContent(FLAT)).toBe(CONTENT);
});

test("граф, записан като низ, също се чете", () => {
    expect(getTableContent(JSON.stringify(NORMALIZED)).rules[0]._id).toBe("r1");
});

test("T0 блокира тясна врата при нормализиран граф", () => {
    const narrow = evaluateT0({ width: 700 }, NORMALIZED);
    expect(narrow.results[0].matched).toBe(true);
    expect(narrow.results[0].level).toBe("error");
    expect(narrow.results[0].message).toBe("Too narrow");
    const wide = evaluateT0({ width: 1000 }, NORMALIZED);
    expect(wide.results[0].matched).toBe(false);
});

test("граф без таблица не връща нищо", () => {
    const empty = { nodes: [{ id: "in", type: "inputNode", name: "Request" }] };
    expect(getTableContent(empty)).toBe(null);
    expect(evaluateT0({ width: 700 }, empty)).toBe(null);
});
