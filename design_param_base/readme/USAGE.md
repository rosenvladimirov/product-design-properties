1.  Create an XML file in your module's `data/` directory named
    `design_param_definitions.xml`.

2.  Declare a definition with its parameter list:

    ```xml
    <odoo>
        <definition code="my_product_family" name="My Product Family">
            <properties>
                <item name="width" type="float" default="900"/>
                <item name="height" type="float" default="2100"/>
                <item name="material" type="selection">
                    <selection>
                        <item>["wood", "Wood"]</item>
                        <item>["steel", "Steel"]</item>
                    </selection>
                </item>
            </properties>
        </definition>
    </odoo>
    ```

3.  Register it via a data function call in `install_design_params.xml`:

    ```xml
    <odoo noupdate="1">
        <function model="design.param.definition"
                  name="create_design_param_definitions">
            <value>my_module</value>
        </function>
    </odoo>
    ```

4.  Link the definition to a BoM via the `design_param_definition_id`
    field on `mrp.bom`.
