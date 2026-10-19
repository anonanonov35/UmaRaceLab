"""Per-window UI translation. Stored builds and simulation exports stay language-neutral."""
from __future__ import annotations
import json
from pathlib import Path
import re
from string import Formatter


class Translator:
    def __init__(self, language='ru'):
        self.language=language if language in ('ru','en') else 'ru'
        self.catalog=json.loads((Path(__file__).parent/'locales/en.json').read_text(encoding='utf-8'))
        self._patterns=[]

    def __call__(self, source, **values):
        template=self.catalog.get(source,source) if self.language=='en' else source
        return template.format(**values).replace('—','-').replace('–','-')

    def dynamic(self, text):
        """Translate messages emitted by the unchanged model and data adapters."""
        if self.language=='ru':
            return text.replace('—','-').replace('–','-')
        if text in self.catalog:
            return self.catalog[text]
        if not self._patterns:
            for source,target in self.catalog.items():
                if '{' not in source:
                    continue
                try:
                    parts=list(Formatter().parse(source))
                    pattern=''.join(re.escape(literal)+(f'(?P<{field}>.+?)' if field else '') for literal,field,_,_ in parts)
                    if any(field for _,field,_,_ in parts):
                        self._patterns.append((re.compile('^'+pattern+'$',re.S),target))
                except (ValueError,re.error):
                    continue
        for pattern,target in self._patterns:
            match=pattern.fullmatch(text)
            if match:
                plain=''.join(literal+(match.group(field) if field else '') for literal,field,_,_ in Formatter().parse(target))
                return plain.replace('—','-').replace('–','-')
        return text.replace('—','-').replace('–','-')
