# -*- coding: utf-8 -*-
"""Разбивката по парчета, обявена от формулата на BoM реда.

Договорът дотук позволяваше само `n_pieces` × `piece_length_mm`, тоест N
ЕДНАКВИ парчета с ЕДНА дължина. Два реални случая не се побират:

    профил на комарник   2 × 1150 + 2 × 850   смесени дължини
    мрежа                1 × 1020 × 1320 мм   двуизмерно парче, от руло 140 см

⚠️ Формулата е ПОТРЕБИТЕЛСКИ код. Затова нормализаторът изхвърля негодното
мълчаливо, вместо да хвърля: криво `pieces` е козметичен дефект, а изключение
по средата на реда изяжда цялата цена на позицията.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDesignPieces(TransactionCase):

    def _norm(self, raw):
        return self.env['mrp.bom']._design_normalize_pieces(raw)

    # ── каквото ТРЯБВА да мине ────────────────────────────────────────────
    def test_mixed_lengths(self):
        """🔑 Профилът на комарник: 2 × 1150 + 2 × 850."""
        self.assertEqual(
            self._norm([{"n": 2, "length_mm": 1150}, {"n": 2, "length_mm": 850}]),
            [{"n": 2, "length_mm": 1150}, {"n": 2, "length_mm": 850}])

    def test_width_is_ignored(self):
        """⛔ Двуизмерното парче е ОТКАЗАНО решение (Влади, 28.08): „искам да
        изписва само дължина от дадена ролка, не искам 2D оптимизация."

        Ключът не гърми — просто не влиза в изхода. Формулите на комарника го
        подаваха, докато искането още стоеше, тъй че мълчаливото пропускане е
        по-добро от изключение върху вече написана формула.
        """
        self.assertEqual(
            self._norm([{"n": 1, "length_mm": 1320, "width_mm": 1020,
                         "note": "от руло 140 см"}]),
            [{"n": 1, "length_mm": 1320, "note": "от руло 140 см"}])


    def test_floats_are_rounded(self):
        """Формулите смятат в плаваща точка; милиметърът е цяло число."""
        self.assertEqual(self._norm([{"n": 2, "length_mm": 1149.6}]),
                         [{"n": 2, "length_mm": 1150}])

    def test_qty_is_accepted_as_alias(self):
        """`qty` върши работа колкото `n` — формулите пишат ту едното, ту другото."""
        self.assertEqual(self._norm([{"qty": 3, "length_mm": 500}]),
                         [{"n": 3, "length_mm": 500}])

    # ── каквото трябва да се ИЗХВЪРЛИ, без да гърми ───────────────────────
    def test_garbage_is_dropped_not_raised(self):
        """⚠️ Същината: крив вход не бива да събаря калкулацията.

        Ако това падне с изключение вместо с None, един сгрешен ред ще изяде
        цената на цялата позиция — точно каквото се случи при T2 inputs.
        """
        for bad in (None, "низ", 42, [], [None], ["низ"], [{}],
                    [{"n": 0, "length_mm": 100}], [{"n": 2, "length_mm": 0}],
                    [{"n": "две", "length_mm": "дълго"}], [{"length_mm": 100}]):
            self.assertIsNone(self._norm(bad), "не изхвърли: %r" % (bad,))

    def test_partial_garbage_keeps_the_good(self):
        """Един негоден запис не бива да отнася годните със себе си."""
        self.assertEqual(
            self._norm([{"n": 2, "length_mm": 1150}, {"боклук": 1},
                        {"n": 0, "length_mm": 900}]),
            [{"n": 2, "length_mm": 1150}])


    def test_note_is_capped(self):
        """Бележката е за екрана, не за роман — реже се, не троши подредбата."""
        out = self._norm([{"n": 1, "length_mm": 500, "note": "х" * 200}])
        self.assertEqual(len(out[0]["note"]), 64)
