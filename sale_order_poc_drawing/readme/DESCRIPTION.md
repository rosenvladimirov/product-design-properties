Product drawing of a production configuration (POC), managed as data of the
configuration template instead of code of a vertical.

A template shows, in this order of precedence:

1. an uploaded picture (`drawing_picture`);
2. an SVG template from the library *Sales → Configuration → Product Drawings*,
   drawn with the drawing defaults of the template, overridden by the saved
   values of the configuration and by the unsaved values of the Point of Sale;
3. the hook `_poc_drawing_fallback(values)` of a vertical;
4. nothing.

The SVG template is QWeb. It sees only `v` (simple values by parameter code:
numbers, texts, selection keys, record names and `v["<code>__color"]`) and `d`
(pure drawing helpers). Only the group *Drawing Designer* (implied by
Settings) writes the library and the drawing fields of a template.

The drawing never writes and never influences prices, BoMs or dielines.
PDF reports call `sale_order_poc_drawing.poc_drawing_block` with `poc`.
