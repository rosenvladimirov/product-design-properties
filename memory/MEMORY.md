# Memory Index

- [Product Properties & Design Matrix стек](project_design_matrix_stack.md) — 15-модулен стек Odoo 18/19: PoliGroup (торби), Konex Tiva (консерви), SolidDoor (врати), Teolino (дограма); T0-T3 матрица, wizard, v19 fixes, deploy patterns
- [Teolino Blinds Import](teolino_blinds_import.md) — 17 product.template + 46 варианта щори в dev-teo-accounting; attr Color/Finish id=31, Control id=56; KAMAX OOD доставчик; скрипт odoo_import_teolino.ps1
- [Praktiker ценова листа](teolino_praktiker_pricelist.md) — pricelist id=4, валута EUR, 46 реда за щорите (pricelist.item ids 1–46) в dev-teo-accounting
- [Odoo достъп и API ключове](teolino_odoo_access.md) — credentials за erp.teolinobisness.com и www.teolinobisness.com/teo-engineering (API ключ за 2FA)
- [teo-engineering настройка](teolino_teoeng_setup.md) — прехвърляне на бланка, щори, pricelist, reorder rules; PROFORMA fix в view 765; encoding fix за кирилица
- [Odoo Studio скрит Edit панел](feedback_studio_panel_scroll.md) — Studio панелът отдясно често е по-дълъг от viewport — Edit/Add Field бутоните са под fold-а; провери скрол преди алтернативи
- [Glass Code Mapping](project_glass_code_mapping.md) — logikal.glass.code.mapping v8.0.7: SQL-инжектиран default_code (G44IM.6S.6C.6K); pane/configuration/panel + aliases; `_pre_seed_cleanup` за slug 8.0.5→8.0.7 collisions
- [teo-engineering hr_payroll schema fix](project_teoeng_hr_payroll_schema.md) — 2026-04-30: l10n_be_hr_payroll нечист uninstall дропна `hr_contract_history.time_credit`; `button_immediate_upgrade(hr_payroll)` пресъздаде колоната
- [teo-engineering Knowledge Share OwlError](project_teoeng_knowledge_share_owl.md) — handoff: Share popover гърми VToggler/VList; root cause = `markdown_viewer_locale` v18.0.3.0.4 FormController patch; нужен fix от автора
- [teo-engineering Employees access + birthday kanban](project_teoeng_employees_access.md) — група 131 премахната от Internal User (1) implied + от 21 users (dev); план за x_birthday поле + kanban edit чака одобрение; бял екран за user 21 = same Owl bug като knowledge share
- [Ролетна щора Teolino Roll matrix](project_roller_shutter_matrix.md) — RS-ROLL parametric design в dev; tmpl 943 + def 2 (roller_door); BoM 200 без формули; `sale_design_configurator_summary_fix` v18.0.1.0.0 fixes summary+description+view widgets; upstream без JS widget за properties_definition
