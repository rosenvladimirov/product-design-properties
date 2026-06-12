=====================
Design Parameter Base
=====================

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/license-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3
.. |badge3| image:: https://img.shields.io/badge/github-rosenvladimirov%2Fproduct--design--properties-lightgray.png?logo=github
    :target: https://github.com/rosenvladimirov/product-design-properties/tree/19.0/design_param_base
    :alt: rosenvladimirov/product-design-properties

|badge1| |badge2| |badge3|

.. note::
   Dual-licensed: available under AGPL-3.0-or-later (default) or under a
   commercial license from Rosen Vladimirov — see ``LICENSE-COMMERCIAL.md``
   at the repository root (contact: vladimirov.rosen@gmail.com).

Фундаментен слой за design-driven производство. Дефинира преизползваеми
набори от design параметри (през Odoo Properties), които описват кои
параметри са налични за дадено продуктово семейство — размери, избор на
материал, feature флагове — заедно с SVG profile шаблони за 2D/3D
визуализация.

Модулът е предпоставка за:

- ``stock_lot_properties`` — съхранява per-lot стойностите на design
  параметрите
- ``mrp_design_matrix`` — matrix-driven генератор на производствени
  поръчки
- ``sale_design_configurator`` — конфигуратор на SO линиите

Наборите параметри се описват в XML (``design_param_definitions.xml``) и
се зареждат през малък XML → PropertiesDefinition парсер. Парсерът
поддържа вериги на наследяване, така че индустриалните под-модули могат
да разширяват базов набор без да дублират полета.

**Съдържание**

.. contents::
   :local:

Употреба
========

Виж ``readme/USAGE.md`` за пълни стъпки — добавяне на нов design
parameter набор (XML дефиниция + ``install_design_params.xml`` data
function + свързване към BoM през ``design_param_definition_id``).

Industry таксономия (от 19.0.1.1.0)
===================================

Свободният ``industry`` Char е заменен от Many2one към ``design.industry``
(canonical модел + alias map за full-normalization). Текстовите
``industry="…"`` тагове в data файловете се auto-резолват през
``design.industry._resolve``. Не се налагат промени в data файловете на
индустриалните под-модули — резолверът прихваща стринга в ``create``/
``write`` override-а преди ORM.

Bug Tracker
===========

Bug-овете се проследяват в `GitHub Issues
<https://github.com/rosenvladimirov/product-design-properties/issues>`_.

Лиценз
======

AGPL-3.

Този модул е част от проекта `rosenvladimirov/product-design-properties
<https://github.com/rosenvladimirov/product-design-properties/tree/19.0/design_param_base>`_
на GitHub.
