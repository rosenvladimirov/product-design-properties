# MRP BoM Formula — Forced Lot Consumption (BG)

> Двоен лиценз: AGPL-3.0-or-later (по подразбиране) или комерсиален лиценз от
> Rosen Vladimirov — виж `LICENSE-COMMERCIAL.md` в корена на репото
> (контакт: vladimirov.rosen@gmail.com).

Мост между `mrp_bom_line_formula_template` и `stock_move_forced_lot_multi`:
формулата на BoM реда решава **от кои forced лотове** консумира raw move-ът —
и по желание **по колко от всеки лот**.

## Изходна променлива

```python
forced_lots = lot_model.search([...])      # recordset
forced_lots = [lot_a, lot_b]               # списък
forced_lots = {lot_a: 3.0, lot_b: 1.0}     # лот → точно количество
```

- списък/recordset → попълва `forced_lot_ids` на move-а; резервацията на
  базовия модул пълни move line-овете (pro-rata при няколко лота);
- dict → допълнително пази количествата по лотове и ги налага при
  резервация **вместо** pro-rata делението.

## Допълнителен контекст

| Променлива | Какво е |
|---|---|
| `lot_model` | моделът `stock.lot` — search/browse |
| `mo_forced_lots` | форсираните лотове на MO-то, филтрирани до продукта на реда |
| + всичко от базовия engine | `production`, `env`, design параметрите… |

## Пример

```python
result = width / 1000 * 4
main = lot_model.search([('product_id', '=', product.id),
                         ('name', 'ilike', 'W%d' % int(width))], limit=1)
forced_lots = {main: result}
```

## Бележки

- матричният път (`mrp_design_matrix`) ползва собствения си child-lot /
  matching механизъм — този модул покрива стандартната експлозия;
- ръчна инсталация (без auto_install); изисква и двата родителски модула
  в addons path (`stock_move_forced_lot_multi` е в репото `manufacture`).
