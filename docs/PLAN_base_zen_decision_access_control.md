# PLAN — kernel extraction (ВЪТРЕ mrp_design_matrix) + `access_control` consumer

> Detailed plan за review преди код. Спека: `/home/rosen/Свалени/CLAUDE_base_zen_decision.md`.
> Решения локирани от Rosen 2026-05-26:
> - Repo = **product-design-properties** (sibling на mrp_design_matrix)
> - **Move** `access.credential` от `hr_attendance_access_control` (НЕ re-define)
> - First step = този план за review
>
> **REVISED 2026-05-26 (втора итерация):** kernel-ът НЕ се отделя в отделен
> `base_zen_decision` модул сега. Извличаме 100% от ZEN логиката ВЪТРЕ
> `mrp_design_matrix` (моделите `zen.decision.table` + `zen.decision.log`,
> `ZenRunner`). `access_control` депенда **директно на `mrp_design_matrix`**
> като transitional kernel host. Когато Rosen реши, mrp_design_matrix се
> разделя на: `base_zen_decision` (базов) + `mrp_design_matrix` (наследник
> consumer). Двата модела се поддържат паралелно междувременно.
>
> **Отговори на Open Questions (Rosen 2026-05-26):**
> 1. `hr.rfid.card` → access.subject deprecation timeline = **Да, в бъдеще**
>    (но не сега; запазва се като bridge)
> 2. Multi-company ZEN graph = **per company own rule** (record rule, не global)
> 3. Calendar tolerance = **per-perimeter field** (на `access.perimeter`,
>    не глобален constant)
> 4. Direction derivation (ZEN vs Python) = **C — Hybrid** (агент анализ
>    2026-05-26): Python helper `_derive_direction(matrix, prev_event)`
>    в `access.context.builder` (sequence + timing memory ZEN не поддържа —
>    JDM е stateless); ZEN graph консумира `direction` + `anomaly_hint`
>    като context fields за accept/deny/violation решения. Същият Python
>    helper се deploy-ва в proxy-то (Phase 3) — версионира се отделно
>    от ZEN графата
> 5. `hr_attendance_access_control` end-state = **bridge layer завинаги**
>    (виж секция 11)

## 1. Контекст

Нов архитектурен kernel `base_zen_decision` извлича ZEN evaluator-а от
`mrp_design_matrix/models/zen_engine.py` (139 реда, 4 теста) — превръща го
в общ примитив „context → ZEN graph → result + trace + version".

Два първи консуматора с идентичен подход (T0–T3 ↔ A0–A3):
- `mrp_design_matrix` (existing — става consumer)
- `access_control` (нов — самостоятелен модул, различен от legacy
  `hr_attendance_access_control`)

`hr_attendance_access_control` остава legacy bridge (за стария
employee↔barcode↔attendance kiosk flow). Phase 2 работата от 2026-05-26
(`access.credential` _inherits + `hr.rfid.card` 5.10.0) се пренася в
`access_control` чрез **move + migration**.

## 2. Repo layout (product-design-properties)

```
product-design-properties/
├── design_param_base/          # existing
├── mrp_bom_line_formula_*/     # existing
├── mrp_design_matrix/          # existing pilot — става KERNEL HOST (transitional)
│   ├── models/
│   │   ├── zen_engine.py       # ZenRunner (existing — KEPT, internal)
│   │   ├── zen_decision_table.py    # NEW — generic; първоначално вътре в mrp_design_matrix
│   │   ├── zen_decision_log.py      # NEW — generic; append-only audit
│   │   ├── mrp_bom.py          # съществуващ consumer; refactor да ползва zen.decision.table
│   │   └── …
│   ├── tests/
│   │   ├── test_zen_engine.py        # EXISTING — запазен
│   │   ├── test_design_context.py    # EXISTING — запазен
│   │   ├── test_matrix_moves.py      # EXISTING — запазен
│   │   ├── test_ptav_resolution.py   # EXISTING — запазен
│   │   ├── test_decision_table.py    # NEW (kernel models)
│   │   ├── test_decision_log.py      # NEW
│   │   └── test_sync_contract.py     # NEW (proxy heartbeat sync)
│   ├── views/
│   │   ├── zen_decision_table_views.xml   # NEW
│   │   ├── zen_decision_log_views.xml     # NEW
│   │   └── menu_zen.xml                   # NEW
│   ├── security/
│   │   └── ir.model.access.csv            # +4 нови ACL за zen.decision.* модели
│   └── __manifest__.py                    # bump 19.0.1.9.0 → 19.0.2.0.0
│                                          # (major bump = добавени kernel модели)
└── access_control/             # НОВ
    ├── models/
    │   ├── access_subject.py
    │   ├── access_credential.py     # MOVED от hr_aac
    │   ├── access_perimeter.py
    │   ├── access_control_point.py
    │   ├── access_passage_event.py
    │   ├── access_violation.py
    │   ├── access_occupancy.py
    │   └── access_context_builder.py  # 3-dim contexts → ZEN input
    ├── migrations/
    │   └── 19.0.1.0.0/
    │       └── post-migration.py   # ir_model_data rename за credential
    ├── tests/
    ├── views/
    ├── data/                       # ZEN graph seed (A0–A3 starter)
    ├── security/
    ├── __manifest__.py             # depends: ['mrp_design_matrix', 'hr_attendance_access_control', …]
    └── __init__.py
```

v18 lockstep — същата структура в `~/Проекти/odoo/odoo-18.0/product-design-properties/`.

**Бъдещ split (when Rosen decides):**
```
base_zen_decision/    # промотиран отделен модул
├── models/zen_engine.py, zen_decision_table.py, zen_decision_log.py
├── tests/test_zen_engine.py, test_decision_table.py, test_decision_log.py, test_sync_contract.py
├── views/, security/, __manifest__.py
└── …

mrp_design_matrix/    # consumer (наследник)
├── depends на base_zen_decision
└── само матрица-специфичните модели + тестове остават

access_control/       # consumer (без промяна, само depends update)
├── depends: ['base_zen_decision', 'hr_attendance_access_control']
└── …
```

Split = чисто refactor (преместване на kernel файлове + depends update). Тестовете на access_control + mrp_design_matrix продължават да минават БЕЗ промяна освен import path. Това е критерий за успех на split-а.

## 3. Phase 1 — base_zen_decision (extract от mrp_design_matrix)

### 3.1 Module manifest

```python
{
    'name': 'Base ZEN Decision Engine',
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'summary': 'Shared ZEN/GoRules decision-table evaluator with versioning + sync',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/zen_decision_table_views.xml',
        'views/zen_decision_log_views.xml',
        'views/menu.xml',
    ],
    'external_dependencies': {'python': ['zen-engine']},
    'license': 'AGPL-3',
}
```

### 3.2 Models

**`zen.decision.table`**
```python
class ZenDecisionTable(models.Model):
    _name = 'zen.decision.table'
    _description = 'ZEN Decision Table (versioned graph)'

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    domain = fields.Char(required=True, index=True,
        help="Domain group: 'mrp_matrix', 'access', 'gfo'…")
    graph = fields.Json(required=True)
    version = fields.Integer(required=True, default=1, readonly=True)
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company)
    active = fields.Boolean(default=True)
    notes = fields.Text()

    _sql_constraints = [
        ('code_version_company_uniq',
         'unique(code, version, company_id)',
         'Each (code, version) must be unique per company.'),
    ]

    def evaluate(self, context, trace=True):
        """Public API.
        Returns {'result': dict, 'trace': dict|None, 'version': int}.
        Pure — no side effects. Caller logs via .log()."""

    def log(self, context, result, trace, executed_in='odoo'):
        return self.env['zen.decision.log'].sudo().create({...})

    def publish_new_version(self, new_graph):
        """Атомична нова версия — създава нов record със same code,
        version=current+1, archives стария."""

    # Sync контракт за Fleet proxy
    def _build_sync_payload(self):
        return {'code': ..., 'version': ..., 'graph': ..., 'hmac': ...}
```

**`zen.decision.log`** (append-only audit)
```python
class ZenDecisionLog(models.Model):
    _name = 'zen.decision.log'
    _description = 'ZEN Decision audit log'
    _order = 'id desc'

    table_id = fields.Many2one('zen.decision.table', required=True, index=True,
                                ondelete='restrict')
    table_version = fields.Integer(required=True)   # snapshot from table.version
    context_in = fields.Json(required=True)
    result_out = fields.Json(required=True)
    trace = fields.Json()
    executed_in = fields.Selection([('odoo', 'Odoo'), ('controller', 'Controller')],
                                    required=True, default='odoo')
    create_date = fields.Datetime(readonly=True)
    # No write — append-only (security via ACL: create only)
```

### 3.3 ZenRunner (internal, не публично)

`models/zen_engine.py` — moved + renamed клас:

```python
# Преименуван ZenWrapper → ZenRunner. API е identичен, само модулният път
# се смени. Запазваме soft-fallback за staged rollouts.
class ZenRunner:
    @classmethod
    def evaluate(cls, table_json, context, env=None) → dict:
        # unchanged логика
```

ZenDecisionTable.evaluate() → use ZenRunner.evaluate(self.graph, context).

### 3.4 mrp_design_matrix → consumer (минимална промяна)

Промяна **САМО на import път + version bump**:

```python
# мrp_design_matrix/models/mrp_bom.py (текущо):
from odoo.addons.mrp_design_matrix.models.zen_engine import ZenWrapper
result = ZenWrapper.evaluate(self.constraint_table, design_context)

# след refactor:
from odoo.addons.base_zen_decision.models.zen_engine import ZenRunner
result = ZenRunner.evaluate(self.constraint_table, design_context)
# OR (по-чисто, ползва registry):
result = self.env['zen.decision.table'].evaluate(code, context)['result']
```

**Success criterion:** 4-те теста на матрицата минават БЕЗ промяна на
логиката (само import path).

### 3.5 Migration на mrp_design_matrix
- Bump manifest 19.0.1.9.0 → 19.0.1.10.0
- Add depends: `base_zen_decision`
- Remove `external_dependencies.python.zen-engine` (вече в base_zen)
- Delete `models/zen_engine.py` (или оставя за 1 цикъл с deprecation warning)
- migrations/19.0.1.10.0/pre-migration.py — no-op (без data changes за матрицата)

### 3.6 Sync контракт към proxy (Phase 1 = Odoo side ready)

`zen.decision.table.action_push_to_proxies()` — за всеки активен
`erpnet.fp.proxy` от Fleet, POST graph+version+HMAC към
`/registry/zen_graph_sync`. (Proxy-side endpoint = Phase 3.)

## 4. Phase 2 — access_control модул

### 4.1 Manifest

```python
{
    'name': 'Access Control (ZEN-driven)',
    'version': '19.0.1.0.0',
    'depends': [
        'base',
        'base_zen_decision',
        'hr',          # for resource.calendar
        'fleet',       # для plate credentials
        'l10n_bg_erp_net_fp_bus_inject',  # за live notifications
        'hr_attendance_access_control',   # legacy bridge (за migration)
    ],
    'license': 'AGPL-3',
}
```

### 4.2 Models (схема)

**`access.subject`** — групира носители на 1 човек
```
name, partner_id (m2o res.partner), employee_id (m2o hr.employee, optional),
credential_ids (o2m access.credential), active
```

**`access.credential`** — MOVED от hr_aac
```
credential_kind [card/plate/biometric/nfc], subject_id (m2o access.subject),
controller_ids (m2m access.controller), perimeter_ids (m2m access.perimeter),
valid_from, valid_to, active, company_id
+ съществуващите fields от current Phase 2 hr_aac record
```

Migration **в access_control/migrations/19.0.1.0.0/post-migration.py**:
```python
# Rename ir_model record за access.credential:
#   model_id остава същия (model name access.credential е същият)
#   но modules='hr_attendance_access_control,access_control' → префиксиран
#   с access_control (или ownership prefix се сменя)
# Същата логика като при lpr→access.controller rename Phase 1.
# Existing data (2 cards backfilled) се запазва — table не се пипа.
openupgrade.update_module_names(cr, [
    ('hr_attendance_access_control.model_access_credential',
     'access_control.model_access_credential'),
    ('hr_attendance_access_control.access_access_credential_user',
     'access_control.access_access_credential_user'),
    # … 4 ACL xmlid-а
    ('hr_attendance_access_control.view_access_credential_list',
     'access_control.view_access_credential_list'),
    # … views
    ('hr_attendance_access_control.action_access_credential',
     'access_control.action_access_credential'),
    ('hr_attendance_access_control.menu_access_credential',
     'access_control.menu_access_credential'),
])
```

`hr_attendance_access_control` v18+v19 → bump 5.10.0 → 5.11.0:
- Remove model + view + ACL + menu definitions for access.credential
- depend на `access_control`
- `hr.rfid.card._inherits` остава, но target → `access.credential` в новия модул

**`access.perimeter`** — вложен периметър
```
name, code (uniq per company), parent_id (m2o self), child_ids (computed o2m),
requires_parent_presence (Boolean), enforcement (Selection: soft/strict),
calendar_id (m2o resource.calendar, optional — темпорален прозорец),
tolerance_minutes (Integer, default 15),
zen_table_id (m2o zen.decision.table, optional — A0–A3 graph specific)
```

**`access.control.point`** — physical access point
```
name, perimeter_id (m2o access.perimeter, required),
controller_id (m2o access.controller — keeps existing model from hr_aac),
direction_kind (Selection: 'in', 'out', 'bidirectional'),
external_reader_id (m2o access.controller.part — наследява от Phase 3 plan),
internal_reader_id (m2o access.controller.part),
magnet_id (m2o access.controller.part),
door_sensor_id (m2o access.controller.part, optional)
```

**`access.passage.event`** — append-only event log
```
control_point_id, credential_id, subject_id (computed),
direction (in/out/derived),
ts (Datetime), result (accept/deny/violation),
signal_matrix (Json),  # external_reader/internal_reader/magnet/door state
context_in (Json),     # what was sent to ZEN
result_out (Json),     # what ZEN returned
log_id (m2o zen.decision.log)
```

**`access.violation`** — incidents
```
event_id (m2o access.passage.event), violation_type (Selection:
forced/held/denied-but-opened/exit-without-entry/tailgating),
priority (low/medium/high/critical), push_sent (Boolean),
hr_review_state (none/pending/reviewed/dismissed),
hr_attendance_id (m2o hr.attendance, optional)
```

**`access.occupancy`** — current state per perimeter
```
perimeter_id (m2o), subject_id (m2o), entered_at, last_seen,
state (inside/outside/unknown)
SQL view OR computed table — TBD по performance
```

### 4.3 Context Builder (3 измерения)

`access.context.builder` (TransientModel или service). **Hybrid arch** —
Python derive-ва физически + stateful полета; ZEN graph консумира резултата
за business decisions (виж Open Q#4 отговор + агент анализ 2026-05-26):

```python
def build_context(self, control_point_id, credential, signal_matrix, ts=None):
    # Stateful preprocessing (изисква prev_event lookup; ZEN не може)
    prev_event = self._last_event_for_point(control_point_id, ts, window_sec=10)
    direction, anomaly_hint = self._derive_direction(signal_matrix, prev_event)
    # ↑ Python helper — пример output:
    #   ('in', None)                          — нормално влизане
    #   ('out', None)                          — нормален изход
    #   (None, 'forced')                       — магнит break без reader
    #   ('in', 'tailgating')                   — 2 в <3s с същата карта
    #   (None, 'exit_without_entry')           — internal без предходен external
    #   ('in', 'denied_but_opened')            — reader denied но door opened
    return {
        # Физическо (raw + derived)
        'signal': {
            'external_reader': signal_matrix['ext'],
            'internal_reader': signal_matrix['int'],
            'magnet': signal_matrix['magnet'],
            'door': signal_matrix.get('door'),
        },
        'direction': direction,             # ← Python derive
        'anomaly_hint': anomaly_hint,       # ← Python derive — ZEN ползва за violation routing
        # Пространствено
        'perimeter_chain': self._perimeter_path(control_point_id.perimeter_id),
        'requires_parent_presence': control_point_id.perimeter_id._requires_chain(),
        'parent_present': self._check_parent_occupancy(credential.subject_id, control_point_id.perimeter_id),
        # Темпорално
        'window': self._resolve_window(control_point_id.perimeter_id.calendar_id, ts),
        'window_tolerance_minutes': control_point_id.perimeter_id.tolerance_minutes,
        'within_window': self._within(ts, window, tolerance),
        # Credential
        'credential_active': credential.active and credential._is_valid_at(ts),
        'credential_kind': credential.credential_kind,
    }

def _derive_direction(self, signal_matrix, prev_event):
    """Pure-Python — определя direction + anomaly от сигнална матрица
    и последното събитие в short window. Може да се ползва offline в proxy.
    Тества се table-driven (виж test_context_builder.py)."""
    # Implementation table: 7+ (matrix, prev_event) → (direction, anomaly)
    # Pattern matching:
    # - ext=fire, int=idle, magnet=open, door=open  → ('in', None)
    # - int=fire, ext=idle, magnet=open, door=open  → ('out', None)
    # - magnet=break, ext=idle, int=idle             → (None, 'forced')
    # - ext=fire, prev_in same card <3s              → ('in', 'tailgating')
    # - int=fire, no prev external event             → (None, 'exit_without_entry')
    # - ext=denied, door=opened                      → ('in', 'denied_but_opened')
    # - magnet=open >held_threshold                  → (None, 'held')
    ...
```

**ZEN graph (A1–A3) консумира `direction` + `anomaly_hint`** като полета —
не ги изчислява. Това позволява:
- ZEN остава stateless (per JDM спецификация)
- Patterns изискващи sequence/timing memory са в Python там където могат
  да четат `access.passage.event` или proxy local buffer
- Test isolation: `test_context_builder.py` (table-driven Python tests) +
  `test_zen_engine.py` (ZEN правила) — установения idiom от
  mrp_design_matrix codebase

### 4.4 Decision flow
```
event @ control_point
  ↓
build_context(point, credential, signal_matrix, ts)
  ↓
zen_table = point.perimeter_id.zen_table_id or default
  ↓
result = zen_table.evaluate(context, trace=True)
  ↓
log_id = zen_table.log(context, result, trace, executed_in='odoo')
  ↓
match result['action']:
  case 'accept': command pulse → controller; passage.event(result='accept'); occupancy.update()
  case 'deny':                                passage.event(result='deny');   push notification
  case 'violation': passage.event + violation.create + push (priority-based)
```

### 4.5 ZEN graph seed (data/zen_graph_access_default.xml)

Минимална A0–A3 starter graph, която Rosen може да обогати в UI:
- A0: `credential.active && credential_active_at_ts` → guard
- A1: derive direction; window from calendar; require_parent если включен
- A2: `accept` if (within_window || tolerance) && (parent_present || !requires_parent)
- A3: ефекти според kind на violation

## 5. Phase 3 — Polimex offline ZEN (proxy-side)

Repo: `~/Проекти/odoo/iot/Odoo.ErpNet.FP/` (vladimirovrosen/odoo-erpnet-fp).

### 5.1 Embed zen-engine в proxy
- Python zen-engine package е bindings към Rust core
- Proxy image вече има Python — direct `pip install zen-engine` в Dockerfile

### 5.2 Heartbeat protocol extension
- Heartbeat включва `zen_graphs: [{code, version, sha256}]` — proxy reports
  loaded versions
- Odoo сравнява със `zen.decision.table` сегашни активни версии
- При mismatch: 200 OK + `pending_graphs: [{code, version, graph_blob, hmac}]`
  в отговора → proxy applies + caches under `/app/data/zen_graphs/<code>.json`

### 5.3 Routes/decisions.py (нов в proxy)
- `POST /access/<point_id>/evaluate` — приема signal_matrix + credential,
  builds local context, ZEN evaluates, executes (open/deny), returns result
- **Споделен Python helper** `_derive_direction()` от секция 4.3 живее
  в `Odoo.ErpNet.FP/proxy/access/context_builder.py` — БАЙТ-ИДЕНТИЧЕН
  с Odoo версията. Версия се pin-ва към ZEN graph version през heartbeat
  payload (`{builder_version, graph_version}`)
- Online: trace буферира локално; периодично POST към Odoo
  `/erp_net_fp/zen/decision_drain`
- Offline: full local evaluate, drain on reconnect with `executed_in='controller'`
- **Mismatch handling:** ако proxy builder_version != Odoo expected →
  fail-safe deny + push alert; не се прави decision до sync

### 5.4 Tests
- Unit: ZenRunner offline същия result като Odoo за идентичен context+graph+version
- Integration: graph push → proxy applies → evaluate works → reconnect drain

## 6. Migration map (от Phase 2 hr_aac → access_control)

| State 2026-05-26 (hr_aac 5.10.0) | След access_control v1.0.0 |
|----|----|
| `access.credential` model in hr_aac | Moved to access_control (ir_model_data rename) |
| `hr.rfid.card._inherits` → access.credential | Запазено — но access.credential е в access_control |
| 2 cards backfilled с credential_id | Без промяна, същите ID-та |
| `access.controller` minimum в hr_aac | Запазено там (хост на legacy bridge); access_control depend |
| Polimex iCON115 record (`Front Magnet`, id=1) | Без промяна — все още в access.controller |
| `access.controller.part` (Phase 3 plan) | Преосмислено като `access.control.point` parts |

## 7. Test plan

### Characterisation (Phase 1 success criterion)
- ВСИЧКИ 4 теста на mrp_design_matrix минават след import path сменен:
  - test_zen_engine.py
  - test_design_context.py
  - test_matrix_moves.py
  - test_ptav_resolution.py

### New tests (base_zen_decision)
- test_decision_table.py — CRUD, version uniqueness, publish_new_version atomicity
- test_log.py — append-only enforcement, query by code+version
- test_sync_contract.py — payload shape, HMAC, idempotent push

### New tests (access_control)
- test_context_builder.py — 3-dim composition: direction derive, perimeter chain,
  window resolution, parent presence check
- test_decision_flow.py — accept/deny/violation paths e2e
- test_credential_migration.py — pre/post migration: 2 cards survive
- test_perimeter_chain.py — requires_parent_presence enforcement
- test_violation_types.py — всеки от 5-те типа forced/held/etc

### Integration (proxy + Odoo)
- test_offline_evaluate.py — proxy локално решава, Odoo вижда trace при reconnect
- test_graph_version_sync.py — version mismatch → pull → apply → continue

## 8. Risks

| Risk | Mitigation |
|------|------------|
| Move на access.credential чупи foreign keys | Migration с ir_model_data rename (доказан pattern от lpr→access.controller Phase 1) |
| mrp_design_matrix тестове failing след refactor | Run цялата test suite ПРЕДИ commit; rollback ако дори 1 тест fail |
| Proxy ZEN runtime crash на offline решение | Fail-secure: при exception → deny + log; door стои затворена |
| Graph version mismatch — laptop vs k3s | version field в heartbeat; mismatch → pull в next cycle |
| `zen.decision.log` table бързо расте | Cron archive >30 days; partial index по create_date |
| HR review queue overflow от violations | Priority filtering — само high/critical → автомат notify; rest in queue |

## 9. Open questions — ALL ANSWERED 2026-05-26

1. **`hr.rfid.card` deprecation timeline?** = **Да, в бъдеще** — но card
   модел остава като bridge layer (виж секция 11). access.subject ще
   групира субект → носители, hr.rfid.card е един от вариантите носители.
   `hr.rfid.card._inherits` chain се запазва.
2. **Multi-company ZEN graph?** = **Per company own rule** — `zen.decision.table`
   има `company_id` + record rule. Различни компании имат различни графи
   за същия `code`. Global graphs не се поддържат.
3. **Calendar tolerance?** = **Per-perimeter field** `tolerance_minutes` на
   `access.perimeter` (виж секция 4.2). Не глобален constant.
4. **Direction derivation (ZEN vs Python)?** = **C — Hybrid** (виж секция 4.3):
   Python helper `_derive_direction(matrix, prev_event)` произвежда
   `direction` + `anomaly_hint` в context-а; ZEN consume-ва за
   business decisions. Причина (агент анализ 2026-05-26): JDM е
   stateless; sequence/timing patterns (tailgating, forced, held)
   изискват prev_event lookup което само Python може. Същият helper
   живее и в proxy (секция 5.3).
5. **`hr_attendance_access_control` end-state?** = **Bridge layer завинаги**
   (виж секция 11).

## 10. Suggested execution order (revised 2026-05-26)

1. ✅ Този план (this document) → review by Rosen → ✅ approved + revised
2. → **Phase 1 (ВЪТРЕ mrp_design_matrix)**: добавя zen.decision.table +
   zen.decision.log + ZenRunner exposure през registry; bump
   mrp_design_matrix 19.0.1.9.0 → 19.0.2.0.0. ZenWrapper остава като
   alias за back-compat (с deprecation warning).
3. → Verify 4 existing тестове на матрицата минават БЕЗ промяна
   (characterisation criterion).
4. → mrp.bom преминава да ползва `env['zen.decision.table'].evaluate()`
   вместо direct ZenWrapper.evaluate(). Тестовете пак трябва да минават.
5. → **Phase 2.1**: access_control module skeleton + manifest +
   depends=['mrp_design_matrix', 'hr_attendance_access_control', ...] +
   `access.credential` MOVE от hr_aac с post-migration (ir_model_data rename).
6. → access_control модели (subject, perimeter, control.point,
   passage.event, violation, occupancy).
7. → context builder + `_derive_direction()` Python helper + table-driven
   tests + decision flow (call zen.decision.table.evaluate → effects).
8. → ZEN graph seed (default A0–A3 starter).
9. → **Phase 3**: proxy zen-engine embed + heartbeat extension +
    `_derive_direction()` копие в `Odoo.ErpNet.FP/proxy/access/context_builder.py`.
10. → Production rollout (laptop proxy първо, после k3s).
11. → **Split decision** (Rosen решава): kernel-ът се промотира в
    отделен `base_zen_decision`. mrp_design_matrix + access_control стават
    consumers. Тестовете пак минават без промяна освен import path.

Estimated effort:
- Phase 1 (in-place extract): ~1 ден
- Phase 2 (access_control нов модул): ~3-5 дни
- Phase 3 (proxy embedding): ~2-3 дни
- Бъдещ split (когато Rosen реши): ~0.5 ден

Общо ~6-9 дни heads-down + 0.5 ден за бъдещия split.

## 11. `hr_attendance_access_control` end-state — bridge layer rationale

`hr_attendance_access_control` остава **постоянно** в production, не се
deprecate. Има 2 различни концептуални слоя:

| Слой | Модул | Отговорност |
|------|-------|-------------|
| **Identity + UX** | hr_attendance_access_control | hr.rfid.card, employee↔barcode sync, attendance kiosk, ONVIF camera, LPR plate camera, fleet vehicle binding, site_map (etage/zone visualisation), face auth |
| **Decision + spatial** | access_control | ZEN evaluation, access.subject (групира носители), access.perimeter (вложени), access.control.point (физика), access.passage.event, occupancy tracking, violation routing |

**Защо паралел, не replace:**
- hr_attendance_access_control е HR-coupled (employee + attendance flow) —
  бъдещ rewrite би разрушил attendance kiosk UX
- access_control е domain-pure (subjects + perimeters + decisions) —
  не зависи от HR семантика
- 2026-05-26 Phase 2 работата (access.credential _inherits + hr.rfid.card)
  ще се движи: credential модел се мести в access_control, hr.rfid.card
  остава в hr_aac и продължава да _inherits → access.credential (cross-module
  _inherits е поддържан в Odoo)
- access_control може да работи БЕЗ hr_aac (за чисто visitor / vehicle / IoT
  достъп). hr_aac остава нужен само за employee↔barcode HR scenarios.

**Bridge contracts:**
- hr_aac.hr.rfid.card._inherits → access_control.access.credential (cross-module)
- access_control.access.subject.employee_id → hr_aac.hr.employee (soft)
- access_control may consume hr_aac signals (face_verify, ONVIF events) като
  допълнителни context inputs за ZEN

## 12. Implementation notes за следваща сесия (Phase 1 kick-off)

Когато започваме Phase 1:

1. **ПЪРВО:** run всичките 4 теста на mrp_design_matrix чисто (baseline):
   ```bash
   cd ~/Проекти/odoo/odoo-19.0/product-design-properties/mrp_design_matrix
   pytest tests/ -v
   ```
   Запиши baseline резултат — никой тест не трябва да fail-не след refactor-а.

2. **МОДЕЛИ:** добавя `zen.decision.table` + `zen.decision.log` в
   `mrp_design_matrix/models/`. Не пипай `mrp.bom`/`mrp.routing.workcenter`
   моделите още. Тестове за новите модели.

3. **EXPOSURE:** `zen.decision.table.evaluate()` вътрешно вика
   `ZenRunner.evaluate()` (rename на ZenWrapper). Existing `ZenWrapper`
   остава като alias с deprecation warning за back-compat.

4. **PROOF:** създай unit test който показва че:
   ```python
   t = env['zen.decision.table'].create({'code': 'test', 'graph': JDM, ...})
   result = t.evaluate({'foo': 1})
   # result == ZenWrapper.evaluate(JDM, {'foo': 1})  ← същия резултат
   ```

5. **mrp.bom refactor (опционално в Phase 1):** ползвай нова table вместо
   field на bom-а. Може и да остане за по-късна итерация — Phase 1
   приоритет = kernel моделите готови + ZenWrapper остава работещ.

6. **Lockstep:** ВСИЧКО се прави в `~/Проекти/odoo/odoo-{18,19}.0/` —
   commit + push двата клона.

7. **Memory:** след всеки feature complete (Phase 1, Phase 2.x, Phase 3),
   update `project_base_zen_decision_2026_05_26.md` + `MEMORY.md`.
