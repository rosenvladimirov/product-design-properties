Foundation layer for design-driven manufacturing. Defines reusable design
parameter sets (via Odoo Properties) that describe what parameters are
available for a given product family — dimensions, material choices,
feature flags — together with SVG profile templates for 2D/3D
visualization.

The module is a prerequisite for:

- `stock_lot_properties` — stores per-lot design parameter values
- `mrp_design_matrix` — the matrix-driven MO generator
- `sale_design_configurator` — the SO line configurator

Parameter sets are authored in XML (`design_param_definitions.xml`) and
loaded via a small XML → PropertiesDefinition parser.  The parser
supports inheritance chains so industry sub-modules can extend a base set
without duplicating fields.
