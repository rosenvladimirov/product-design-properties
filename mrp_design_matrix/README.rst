=================
MRP Design Matrix
=================

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/license-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3
.. |badge3| image:: https://img.shields.io/badge/github-rosenvladimirov%2Fproduct--design--properties-lightgray.png?logo=github
    :target: https://github.com/rosenvladimirov/product-design-properties/tree/19.0/mrp_design_matrix
    :alt: rosenvladimirov/product-design-properties

|badge1| |badge2| |badge3|

Ядро на design-driven производството. Превръща параметричен BoM в
конкретна производствена поръчка (MO) чрез оценка на четири GoRules DMN
таблици (T0/T1/T2/T3) спрямо плосък design контекст, събран от
производствения lot:

- **T0 — Constraints** (``constraint_table``) — блокира или предупреждава
  при невалидни комбинации от параметри.
- **T1 — Geometry** (``geometry_table``) — изчислява производни размери
  и forced стойности, които стават налични за T2/T3 и BoM формулите.
- **T2 — Materials** (``material_table``) — съставът на ведомостта
  (coefficient / direct ref / PTAV).
- **T3 — Operations** (``operation_table``) — условни work order-и.

Engine-ът е stateless — чете матрицата JSON от BoM-а и design контекста
от lot-а, после генерира raw moves и workorder-и върху MO-то.

Допълнителни функционалности: визуален OWL DMN widget
(``DesignMatrixField``), live Matrix Preview диалог, semi-finished верига
с ``mto_stop``. Виж ``readme/DESCRIPTION.md`` за пълно описание,
``readme/CONFIGURE.md`` за инсталация и конфигурация, ``readme/USAGE.md``
за работния поток, ``readme/HISTORY.md`` за changelog.

**Съдържание**

.. contents::
   :local:

Зависимости
===========

Външна Python зависимост: ``zen-engine`` (GoRules JDM evaluator).

Industry таксономия (от 19.0.1.9.0)
===================================

``mrp.matrix.template.industry`` (Char) преминава в ``industry_id``
Many2one към ``design.industry`` (виж ``design_param_base``). 8-те
индустриални под-модула остават непокътнати — ``create``/``write``
override прихваща легитимното ``industry="…"`` от data файловете и го
резолва.

Bug Tracker
===========

Bug-овете се проследяват в `GitHub Issues
<https://github.com/rosenvladimirov/product-design-properties/issues>`_.

Лиценз
======

AGPL-3.

Този модул е част от проекта `rosenvladimirov/product-design-properties
<https://github.com/rosenvladimirov/product-design-properties/tree/19.0/mrp_design_matrix>`_
на GitHub.
