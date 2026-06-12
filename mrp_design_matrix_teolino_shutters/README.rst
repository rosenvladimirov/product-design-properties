========================================================
MRP Design Matrix — Параметрични ролетни щори (5 модела)
========================================================

.. note::
   Dual-licensed: available under AGPL-3.0-or-later (default) or under a
   commercial license from Rosen Vladimirov — see ``LICENSE-COMMERCIAL.md``
   at the repository root (contact: vladimirov.rosen@gmail.com).

Параметрична design матрица за ролетни щори с 5 модела
(Standard / Round / T-Roll / Built-In / Thermo Comfort).
Подобен на ``mrp_design_matrix_roller_door`` (който носи един опростен
template) — този модул кодира **петте реални модела** в **един
model-aware T0–T3 темплейт**: ``shutter_model`` е decision-table вход и
per-model правилата живеят в T0 (ограничения) и T1 (геометрия). Без
variant explosion, без пет отделни темплейта.

Параметри
=========

Наследени от ``base_dimensions`` (parent):

* ``width`` — отвор по дължина L (mm)
* ``height`` — отвор по височина H (mm)

Модулно-специфични:

* ``shutter_model`` — Standard / Round / T-Roll / Built-In / Thermo Comfort
* ``box_size`` — none / 137 / 165 / 180 / 205 / 170 / 210
* ``slat_size`` — 40 / 50
* ``axis_size`` — 40 / 60
* ``control_type`` — rope / shirit / motor
* ``guide_type`` — standard / feather (feather е САМО за Thermo Comfort)
* ``shutter_count`` — 1..4 (per-model максимум, налаган в T0)

Per-model правила (T0/T1/T2/T3)
===============================

**T0 — ограничения** (24 правила, ``hitPolicy: collect``): глобални L/H
лимити; per-model семейство кутии (Standard/Round → 137/165/180/205;
T-Roll/Thermo → 170/210; Built-In → без кутия); feather guide само за
Thermo; per-model максимум брой щори (Standard 1-4, T-Roll 1-2,
Round/Thermo/Built-In = 1); предупреждение при ``H > 2800``.

**T1 — геометрия** (10 правила, ``hitPolicy: first`` по ``shutter_model``
+ ``slat_size``): връща per-model offset-и (``slat_len_offset``,
``terminal_offset``, ``axis_off_40/60``, ``box_form_offset``), режим на
броене на ламелите (``slat_count_mode``: ``std`` / ``builtin`` /
``thermo``), режим на caps (``caps_mode``: ``n1`` / ``equal`` /
``direct``) и тип на водача (``guide_mode``).

**T2 — материали** (5 правила, ``hitPolicy: collect``): O-варианти за
управлението — ``rope-o`` (въжен комплект), ``shirit-o`` (ширит),
``motor-o`` (стандартен мотор за не-Thermo), ``motor_safety-o`` (мотор
със safety профил за Thermo Comfort), ``guide_feather-o`` (водач с перо
за Thermo).

**T3 — операции** (2 правила, ``hitPolicy: collect``): добавя workorder
за инсталация на мотор; стандартен 45 мин, safety вариант 60 мин.

Покритие — потвърдено vs TBD
============================

**Потвърдено** (от заключените production проби):

* per-model offset-и (slat / terminal / axis / box) — T1
* slat-count modes: ``std``: ``floor((H−Box/2)/S)−1``; ``builtin``:
  ``ceil(H/S)−1``; ``thermo``: ``floor((H−Box/2)/S) + (1 if S==50)``
* caps modes: Standard/Round/T-Roll → ``n+1``; Built-In → ``=n``;
  Thermo Comfort → директен брой
* O-варианти за управление; за Thermo Comfort = мотор със safety профил;
  feather guide само за Thermo

**TBD** (липсва в спецификацията — кодирано като warning, не hard limit):

* Пълна ``H_MAX`` таблица per ``(model, box, slat, axis)`` (max ever
  2800; T-Roll Lamella 50 ``H_MAX``). T0 налага глобални L/H лимити и
  предупреждава при ``H > 2800``.
* Точни Odoo SKU номера — demo продуктите са описателни placeholder-и
  (индикативен код в името), консистентно с
  ``mrp_design_matrix_roller_door``. Реалното SKU мапиране е
  отговорност на downstream BoM модул (отделен проект).

Известни ограничения
====================

* **Резолване на ``industry`` тага.** Data файловете декларират
  ``industry="doors"`` като свободен стринг (zero-churn конвенция).
  От ``design_param_base`` 19.0.1.1.0 / ``mrp_design_matrix`` 19.0.1.9.0
  стрингът се auto-резолва към канонично ``design.industry`` чрез
  ``design.industry._resolve`` (full-normalization alias map;
  ``doors → doors``). Не се налагат промени в data файловете.

* **Demo BoM xml-id / table-copy fragility (repo-wide).** Demo-то
  следва установената sibling конвенция (``ref="<module>.<code>"`` за
  ``design_param_definition_id`` и
  ``eval="ref('tmpl').constraint_table"`` за четирите таблици).
  ``design.param.definition.create_design_param_definitions`` не
  регистрира ``ir.model.data``, а ``ref()`` в eval връща ``int`` — така
  че тази конвенция е технически крехка в stock Odoo (``bags`` дори
  заглушава ``material_table`` с ``{}``). Огледано 1:1 с референтния
  модул заради консистентност; коректното решение е repo-wide задача,
  не специфична за този модул.

Лиценз
======

AGPL-3.
