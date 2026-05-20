1.  Създайте XML файл в `data/` директорията на вашия модул, с име
    `design_param_definitions.xml`.

2.  Декларирайте дефиниция със списъка параметри:

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

3.  Регистрирайте я през data function call в
    `install_design_params.xml`:

    ```xml
    <odoo noupdate="1">
        <function model="design.param.definition"
                  name="create_design_param_definitions">
            <value>my_module</value>
        </function>
    </odoo>
    ```

4.  Свържете дефиницията към BoM през полето
    `design_param_definition_id` на `mrp.bom`.
