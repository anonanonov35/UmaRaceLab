import ast
import json
from pathlib import Path
import re
from string import Formatter
import unittest

from uma_lab.i18n import Translator
from uma_lab.theme import PALETTES, get_palette

ROOT=Path(__file__).resolve().parents[1]


class LocalizationTests(unittest.TestCase):
    def test_catalog_preserves_all_format_arguments(self):
        catalog=Translator('en').catalog
        fields=lambda text:sorted((field,spec,conversion) for _,field,spec,conversion in Formatter().parse(text) if field)
        for source,target in catalog.items():
            with self.subTest(source=source):
                self.assertEqual(fields(source),fields(target))
                self.assertFalse(re.search('[А-Яа-яЁё]',target))

    def test_every_explicit_ui_string_has_an_english_entry(self):
        catalog=Translator('en').catalog
        for path in (ROOT/'uma_lab/gui.py',ROOT/'uma_lab/track_views.py'):
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='tr' and node.args and isinstance(node.args[0],ast.Constant):
                    self.assertIn(node.args[0].value,catalog,f'{path.name}:{node.lineno}')

    def test_languages_are_isolated_and_preserve_names(self):
        ru,en=Translator('ru'),Translator('en')
        self.assertEqual(ru('Характеристики'),'Характеристики')
        self.assertEqual(en('Характеристики'),'Stats')
        self.assertEqual(ru.language,'ru')
        self.assertEqual(Translator('invalid').language,'ru')
        self.assertEqual(en.dynamic('Seiun Sky / 100201'),'Seiun Sky / 100201')

    def test_dynamic_validation_and_skill_messages(self):
        en=Translator('en')
        self.assertEqual(en.dynamic('speed: нужно целое число от 1 до 5000'),'speed: enter an integer from 1 to 5000')
        self.assertEqual(en.dynamic('Seiun Sky: в базе нет навыка 123'),'Seiun Sky: skill 123 is missing from the database')
        self.assertIn('visiblehorse',en.dynamic('Условие visiblehorse: текущая семантика приближена, нативная версия не восстановлена'))
        self.assertEqual(en('Этот прогон: {p0} — {p1} ({p2:.3f} с). До поправки табло: {p3:.4f} с.',p0='Oguri',p1='1:29.9',p2=89.9123,p3=88.12345),
                         'This run: Oguri, 1:29.9 (89.912 s). Before the board correction: 88.1235 s.')

    def test_core_text_and_button_contrast(self):
        def luminance(color):
            rgb=[int(color[i:i+2],16)/255 for i in (1,3,5)]
            linear=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in rgb]
            return sum(a*b for a,b in zip(linear,(.2126,.7152,.0722)))
        for theme,palette in PALETTES.items():
            pairs=[('ink','surface'),('muted','background'),('on_accent','accent'),('on_accent','accent_hover'),
                   ('masthead_text','masthead'),('masthead_muted','masthead'),('accent','nav_selected'),
                   ('ink','selected'),('ink','accent_tint'),('ink','row_alt'),('ink','hover'),('stat_header_ink','stat_header')]
            for foreground,background in pairs:
                with self.subTest(theme=theme,pair=(foreground,background)):
                    a,b=sorted((luminance(palette[foreground]),luminance(palette[background])))
                    self.assertGreaterEqual((b+.05)/(a+.05),4.5)
            for kind in ('unique','gold','normal'):
                for foreground in ('skill_ink','skill_muted'):
                    for color in palette['skill_'+kind]:
                        with self.subTest(theme=theme,kind=kind,foreground=foreground,color=color):
                            a,b=sorted((luminance(palette[foreground]),luminance(color)))
                            self.assertGreaterEqual((b+.05)/(a+.05),4.5)

    def test_theme_palettes_are_isolated_and_have_identical_roles(self):
        self.assertEqual(set(PALETTES['light']),set(PALETTES['dark']))
        selected=get_palette('dark')
        selected['ink']='#abcdef'
        self.assertNotEqual(selected['ink'],get_palette('dark')['ink'])
        self.assertEqual(get_palette('unknown'),get_palette('light'))


if __name__=='__main__':unittest.main()
