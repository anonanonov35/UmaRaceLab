"""Keyboard-operable skill cards; gradients are native Canvas drawing, not assets."""
import tkinter as tk
from tkinter import font as tkfont, ttk


def wrapped(text, font, width):
    lines, line = [], ''
    for word in text.replace('\\n', ' ').split():
        candidate = (line + ' ' + word).strip()
        if line and font.measure(candidate) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines or ['']


def gradient(canvas, box, colors):
    x, y, width, height = box
    for offset in range(0, int(width), 4):
        point = offset / max(1, width - 1) * (len(colors) - 1)
        index = min(int(point), len(colors) - 2)
        fraction = point - index
        a, b = colors[index], colors[index + 1]
        rgb = [round(int(a[k:k+2], 16) * (1-fraction) + int(b[k:k+2], 16) * fraction) for k in (1, 3, 5)]
        color = '#' + ''.join(f'{value:02x}' for value in rgb)
        canvas.create_rectangle(x+offset, y, min(x+width, x+offset+4), y+height, fill=color, outline='')


def draw_card(canvas, box, item, palette, title_font, meta_font, selected=False, description=False):
    x, y, width, height = box
    colors = palette['skill_' + item.get('kind', 'normal')]
    gradient(canvas, box, colors)
    canvas.create_rectangle(x, y, x+width, y+height, outline=palette['skill_focus'] if selected else palette['skill_border'], width=3 if selected else 1)
    label = item.get('label', '')
    canvas.create_text(x+14, y+12, text=label, anchor='nw', fill=palette['skill_muted'], font=meta_font)
    lines = wrapped(item['name'], title_font, width-28)
    if not description and len(lines) > 2:
        lines = lines[:2]
        while title_font.measure(lines[-1] + '…') > width-28:
            lines[-1] = lines[-1][:-1]
        lines[-1] += '…'
    top = y + 33
    canvas.create_text(x+14, top, text='\n'.join(lines), anchor='nw', fill=palette['skill_ink'], font=title_font)
    if description:
        top += len(lines) * title_font.metrics('linespace') + 12
        canvas.create_line(x+14, top-5, x+width-14, top-5, fill=palette['skill_border'])
        body = wrapped(item.get('description', ''), meta_font, width-28)
        canvas.create_text(x+14, top+5, text='\n'.join(body), anchor='nw', fill=palette['skill_ink'], font=meta_font)


class SkillGrid(tk.Frame):
    """Single selection, two columns, visible focus; Listbox-like selection/scroll API."""
    def __init__(self, master, palette, on_open):
        super().__init__(master, bg=palette['surface'])
        self.palette, self.on_open = palette, on_open
        self.items, self.selected, self.columns = [], None, 2
        self.title_font = tkfont.Font(self, family='Segoe UI', size=11, weight='bold')
        self.meta_font = tkfont.Font(self, family='Segoe UI', size=9)
        self.card_height = max(88, 39 + 2*self.title_font.metrics('linespace'))
        self.canvas = tk.Canvas(self, bg=palette['surface'], bd=0, highlightthickness=1,
                                highlightbackground=palette['border'], highlightcolor=palette['accent'], takefocus=True)
        scrollbar = ttk.Scrollbar(self, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda _: self._draw())
        self.canvas.bind('<Button-1>', self._click)
        self.canvas.bind('<Double-1>', self._open)
        self.canvas.bind('<Return>', self._open)
        self.canvas.bind('<space>', self._open)
        self.canvas.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(-int(e.delta/120), 'units'))
        for key, step in [('Left', -1), ('Right', 1), ('Up', -2), ('Down', 2)]:
            self.canvas.bind('<'+key+'>', lambda e, s=step: self._move(s))
        self.canvas.bind('<Home>', lambda _: self._select(0))
        self.canvas.bind('<End>', lambda _: self._select(len(self.items)-1))

    def set_items(self, items):
        selected_id = self.items[self.selected]['id'] if self.selected is not None and self.selected < len(self.items) else None
        self.items = items
        self.selected = next((i for i, item in enumerate(items) if item['id'] == selected_id), None)
        self._draw()

    def _draw(self):
        c = self.canvas
        c.delete('all')
        width = max(100, c.winfo_width()-12)
        self.columns = 2 if width >= 600 else 1
        card_width = (width - 12*(self.columns-1)) / self.columns
        for index, item in enumerate(self.items):
            x = 6 + (index % self.columns)*(card_width+12)
            y = 6 + (index // self.columns)*(self.card_height+10)
            draw_card(c, (x, y, card_width, self.card_height), item, self.palette,
                      self.title_font, self.meta_font, index == self.selected)
        rows = (len(self.items)+self.columns-1)//self.columns
        c.configure(scrollregion=(0, 0, width, max(1, rows*(self.card_height+10)+6)), yscrollincrement=30)

    def _click(self, event):
        self.canvas.focus_set()
        width = max(100, self.canvas.winfo_width()-12)
        column = min(self.columns-1, max(0, int((event.x-6) / ((width+12)/self.columns))))
        row = int(max(0, self.canvas.canvasy(event.y)-6) / (self.card_height+10))
        self._select(row*self.columns+column, see=False)

    def _select(self, index, see=True):
        if not self.items:
            return 'break'
        self.selected = max(0, min(len(self.items)-1, index))
        self._draw()
        if see:
            top = (self.selected//self.columns)*(self.card_height+10)
            current = self.canvas.canvasy(0)
            height = self.canvas.winfo_height()
            total = max(1, ((len(self.items)+self.columns-1)//self.columns)*(self.card_height+10)+6)
            if top < current:
                self.canvas.yview_moveto(top/total)
            elif top+self.card_height+12 > current+height:
                self.canvas.yview_moveto((top+self.card_height+12-height)/total)
        return 'break'

    def _move(self, step):
        if self.selected is None:
            return self._select(0)
        if abs(step) == 2:
            step = self.columns if step > 0 else -self.columns
        return self._select(self.selected+step)

    def _open(self, _=None):
        if self.selected is not None:
            self.on_open(self.items[self.selected]['id'])
        return 'break'

    def curselection(self):
        return (self.selected,) if self.selected is not None else ()

    def selection_set(self, index):
        self._select(index, see=False)

    def yview(self):
        return self.canvas.yview()

    def yview_moveto(self, fraction):
        self.canvas.yview_moveto(fraction)


class SkillDetailCard(tk.Canvas):
    def __init__(self, master, palette):
        super().__init__(master, height=155, bg=palette['background'], highlightthickness=0)
        self.palette, self.item = palette, None
        self.title_font = tkfont.Font(self, family='Segoe UI', size=14, weight='bold')
        self.meta_font = tkfont.Font(self, family='Segoe UI', size=11)
        self.bind('<Configure>', lambda _: self._draw())

    def set_item(self, item):
        self.item = item
        self._draw()

    def _draw(self):
        self.delete('all')
        if self.item is None:
            return
        width = max(150, self.winfo_width()-4)
        title = wrapped(self.item['name'], self.title_font, width-28)
        body = wrapped(self.item.get('description', ''), self.meta_font, width-28)
        height = 65 + len(title)*self.title_font.metrics('linespace') + len(body)*self.meta_font.metrics('linespace')
        self.configure(height=height+4)
        draw_card(self, (2, 2, width, height), self.item, self.palette, self.title_font, self.meta_font, description=True)
