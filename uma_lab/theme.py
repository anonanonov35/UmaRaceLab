"""Native Tk tokens inspired by the user's monochrome/orange reference."""
from tkinter import ttk

LIGHT_PALETTE={
    'background':'#f3f3f1','surface':'#fdfdfc','ink':'#202020',
    'muted':'#626262','border':'#8a8a85','subtle':'#e8e8e4',
    'accent':'#ff663d','accent_hover':'#f1542a','accent_tint':'#fff0e9',
    'masthead':'#1d1d1e','masthead_text':'#f4f4f1','masthead_muted':'#bdbdb9',
    'selected':'#fbd8c9','disabled':'#d9d9d4',
    'on_accent':'#202020','hover':'#deded9','pressed':'#c2c2bc',
    'nav_selected':'#303031','nav_border':'#555555','row_alt':'#f5f5f2',
    'road':'#deded8','grid':'#deded8','uphill':'#ffe1d3','downhill':'#e4e4df',
    'corner':'#8e8e87','spurt':'#bd542e','runner_ink':'#fdfdfc',
    'phase_colors':('#9a9a94','#656561','#ba4b2c','#ff663d'),
    'runner_colors':('#236b59','#366caa','#ae5730','#855aa3','#b23f63','#78632b','#437f8c','#634d91','#914e4e'),
    'skill_ink':'#352a26','skill_muted':'#5c514b','skill_border':'#96908b',
    'skill_unique':('#dbffd8','#bceeff','#d2c8ff','#ffc4ef'),
    'skill_gold':('#fff7ce','#ffe391','#ffc64f'),'skill_normal':('#ffffff','#f3f3f7'),
    'skill_focus':'#78472d',
    'stat_header':'#416d29','stat_header_ink':'#ffffff',
}

DARK_PALETTE={
    'background':'#18191a','surface':'#222426','ink':'#f1f1ec',
    'muted':'#b3b3ad','border':'#777972','subtle':'#303235',
    'accent':'#ff663d','accent_hover':'#ff805e','accent_tint':'#3a2922',
    'masthead':'#151617','masthead_text':'#f4f4f1','masthead_muted':'#bdbdb9',
    'selected':'#5a3527','disabled':'#2a2c2f',
    'on_accent':'#202020','hover':'#3b3d41','pressed':'#494c50',
    'nav_selected':'#303031','nav_border':'#696b68','row_alt':'#282a2c',
    'road':'#4a4b48','grid':'#3d3f3b','uphill':'#50342a','downhill':'#303a41',
    'corner':'#8f938c','spurt':'#ff835b','runner_ink':'#151617',
    'phase_colors':('#c1c1b9','#92958f','#db8064','#ff663d'),
    'runner_colors':('#69bfa0','#85b4e9','#e5aa7a','#b09ada','#ea94b0','#cbbe71','#7cc2ce','#a5a8dc','#d89898'),
    'skill_ink':'#352a26','skill_muted':'#5c514b','skill_border':'#96908b',
    'skill_unique':('#dbffd8','#bceeff','#d2c8ff','#ffc4ef'),
    'skill_gold':('#fff7ce','#ffe391','#ffc64f'),'skill_normal':('#ffffff','#f3f3f7'),
    'skill_focus':'#78472d',
    'stat_header':'#2e4d25','stat_header_ink':'#f1f1ec',
}

PALETTES={'light':LIGHT_PALETTE,'dark':DARK_PALETTE}
PALETTE=LIGHT_PALETTE  # Backward-compatible default for tools and independent views.


def get_palette(name='light'):
    return PALETTES.get(name,LIGHT_PALETTE).copy()


def apply_theme(root,name='light'):
    p=get_palette(name)
    root.configure(bg=p['background'])
    root.option_add('*TCombobox*Listbox.background',p['surface'])
    root.option_add('*TCombobox*Listbox.foreground',p['ink'])
    root.option_add('*TCombobox*Listbox.selectBackground',p['selected'])
    root.option_add('*TCombobox*Listbox.selectForeground',p['ink'])
    root.option_add('*TButton.cursor','hand2')
    s=ttk.Style(root)
    s.theme_use('clam')
    s.configure('.',font=('Segoe UI',10),background=p['background'],foreground=p['ink'])
    s.configure('TFrame',background=p['background'])
    s.configure('Card.TFrame',background=p['surface'])
    s.configure('TLabel',background=p['background'])
    s.configure('Muted.TLabel',foreground=p['muted'])
    s.configure('Section.TLabel',font=('Segoe UI Semibold',20))
    s.configure('TButton',padding=(12,7),background=p['subtle'],foreground=p['ink'],borderwidth=0,focusthickness=2,focuscolor=p['ink'])
    s.map('TButton',background=[('disabled',p['disabled']),('pressed',p['pressed']),('active',p['hover'])],foreground=[('disabled',p['muted']),('!disabled',p['ink'])])
    s.configure('Primary.TButton',background=p['accent'],foreground=p['on_accent'],font=('Segoe UI Semibold',10),padding=(18,8))
    s.map('Primary.TButton',background=[('disabled',p['disabled']),('pressed','#e94d24'),('active',p['accent_hover'])],foreground=[('disabled',p['muted']),('!disabled',p['on_accent'])])
    s.configure('TNotebook',borderwidth=0,tabmargins=0,background=p['background'],bordercolor=p['background'],lightcolor=p['background'],darkcolor=p['background'])
    s.layout('TNotebook.Tab',[])
    s.configure('Treeview',background=p['surface'],fieldbackground=p['surface'],foreground=p['ink'],rowheight=30,borderwidth=0,font=('Segoe UI',10))
    s.configure('Treeview.Heading',background=p['subtle'],foreground=p['ink'],padding=(8,8),font=('Segoe UI Semibold',10),borderwidth=0)
    s.map('Treeview.Heading',background=[('active',p['hover'])],foreground=[('!disabled',p['ink'])])
    s.map('Treeview',background=[('selected',p['selected'])],foreground=[('selected',p['ink'])])
    for control in ('TCombobox','TEntry','TSpinbox'):
        s.configure(control,padding=6,background=p['subtle'],fieldbackground=p['surface'],foreground=p['ink'],arrowcolor=p['ink'],bordercolor=p['border'],lightcolor=p['surface'],darkcolor=p['surface'],insertcolor=p['ink'],selectbackground=p['selected'],selectforeground=p['ink'])
        s.map(control,bordercolor=[('focus',p['ink'])],fieldbackground=[('disabled',p['subtle']),('readonly',p['surface'])],foreground=[('disabled',p['muted']),('readonly',p['ink'])],background=[('active',p['hover'])])
    s.configure('TCheckbutton',background=p['background'],foreground=p['ink'],indicatorbackground=p['surface'],indicatorforeground=p['on_accent'],focuscolor=p['ink'])
    s.map('TCheckbutton',background=[('active',p['background'])],indicatorbackground=[('selected',p['accent'])])
    s.configure('TLabelframe',borderwidth=0,relief='flat',bordercolor=p['background'],lightcolor=p['background'],darkcolor=p['background'])
    s.configure('TLabelframe.Label',foreground=p['ink'],font=('Segoe UI Semibold',11))
    s.configure('TScale',background=p['border'],troughcolor=p['subtle'],bordercolor=p['border'],lightcolor=p['border'],darkcolor=p['border'],sliderlength=22)
    s.configure('Horizontal.TProgressbar',background=p['accent'],troughcolor=p['subtle'],borderwidth=0)
    s.configure('TScrollbar',background=p['subtle'],troughcolor=p['background'],arrowcolor=p['ink'],bordercolor=p['background'],lightcolor=p['subtle'],darkcolor=p['subtle'],borderwidth=0,arrowsize=12)
    s.map('TScrollbar',background=[('active',p['hover']),('pressed',p['pressed'])],arrowcolor=[('active',p['ink'])])
    s.configure('TPanedwindow',background=p['background'])
