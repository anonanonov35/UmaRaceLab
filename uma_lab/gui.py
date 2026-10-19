from __future__ import annotations
import bisect
import gc
from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from . import __version__
from .data import DEFAULT_INSTALL, GameData
from .engine import LIMITATIONS, RaceResult, simulate, audit_catalog
from .models import APTITUDE_KEYS, GRADES, STATS, STRATEGIES, RaceConfig, Runner, load_builds, save_builds
from .build_catalog import bind_variant, find_variant, owned_unique, legacy_aptitudes, add_build_skill, UNIQUE_RARITIES
from .skill_codec import fidelity_issues
from .track_views import TrackViews
from .race_margins import format_board_time
from .i18n import Translator
from .theme import get_palette, apply_theme
from .skill_cards import SkillGrid, SkillDetailCard
from .paths import user_data_dir

STAT_LABELS = {"speed": "Скорость", "stamina": "Выносливость", "power": "Сила", "guts": "Характер", "wisdom": "Мудрость"}
GROUND = ["Хорошее / Firm", "Влажное / Good", "Мягкое / Soft", "Тяжёлое / Heavy"]
WEATHER = ["Ясно", "Облачно", "Дождь", "Снег"]
SEASONS = ["Весна", "Лето", "Осень", "Зима"]
MOODS = ["Ужасное", "Плохое", "Обычное", "Хорошее", "Отличное"]


class RaceLab:
    def __init__(self, root: tk.Tk, local_dir: Path | None = None):
        self.root = root
        self.local = local_dir if local_dir is not None else user_data_dir()
        self.local.mkdir(parents=True, exist_ok=True)
        self.settings = {}
        try:
            self.settings=json.loads((self.local/'settings.json').read_text(encoding='utf-8'))
            if not isinstance(self.settings,dict):self.settings={}
        except (ValueError,OSError):
            pass
        self.theme_name=self.settings.get('theme','light')
        if self.theme_name not in ('light','dark'):self.theme_name='light'
        self.palette=get_palette(self.theme_name)
        self.tr=Translator(self.settings.get('language','ru'))
        self._choice_labels()
        self.data = None
        self.result: RaceResult | None = None
        self.playing = False
        self.playhead = 0.
        self.last_clock = time.perf_counter()
        self.active_runner = 0
        self.busy = False
        self.results_queue = queue.Queue()
        self.worker = None
        self.frame_times = []
        self.last_event_count = -1
        self.skill_audit = {}
        self.audit_ready = False
        self.time_of_day, self.race_grade = 2, 100
        self.root.title(f"Uma Race Lab / {__version__}")
        width = min(1320, root.winfo_screenwidth() - 80)
        height = min(960, root.winfo_screenheight() - 100)
        self.root.geometry(f"{width}x{height}+{max(0, (root.winfo_screenwidth() - width) // 2)}+30")
        self.root.minsize(min(1100, width), min(780, height))
        self.root.configure(bg=self.palette['background'])
        self._style()
        self._connect_initial()
        self.runners = self._default_runners()
        saved = self.local / "autosave-builds.json"
        if saved.exists():
            try:
                self.runners = load_builds(saved)
            except (ValueError, OSError, TypeError) as e:
                messagebox.showwarning(self.tr('Не удалось загрузить билды'), self.tr.dynamic(str(e)), parent=root)
        self._bind_loaded_runners()
        self._layout()
        self._refresh_data()
        self._refresh_roster()
        self._load_runner()
        root.protocol("WM_DELETE_WINDOW", self._close)
        root.after(30, self._animate)
        root.after(100, self._poll_result)

    def _style(self):
        apply_theme(self.root,self.theme_name)

    def _choice_labels(self):
        for key,values in [('ground',GROUND),('weather',WEATHER),('seasons',SEASONS),('moods',MOODS)]:
            setattr(self,key,[self.tr(v) for v in values])
        self.stat_labels={key:self.tr(value) for key,value in STAT_LABELS.items()}
        self.strategies={key:self.tr(value) for key,value in STRATEGIES.items()}

    def _save_settings(self):
        pending=self.local/'settings.json.tmp'
        pending.write_text(json.dumps(self.settings,ensure_ascii=False,indent=2),encoding='utf-8')
        pending.replace(self.local/'settings.json')

    def _course_label(self,course):
        surface=self.tr({1:'трава',2:'грунт'}.get(course['ground'],str(course['ground'])))
        turn=self.tr({1:'правый',2:'левый',4:'прямой'}.get(course['turn'],str(course['turn'])))
        return f"{course['name']} / {course['distance']} {self.tr('м')} / {surface} / {turn} / #{course['id']}"

    def _navigate(self,index):
        self.notebook.select(index)

    def _queue_layout(self,event):
        if event.widget!=self.root:return
        pending=getattr(self,'layout_pending',None)
        if pending:self.root.after_cancel(pending)
        self.layout_pending=self.root.after(60,self._adapt_layout)

    def _adapt_layout(self):
        self.layout_pending=None
        self._size_build_form()
        compact=self.root.winfo_height()<850
        if getattr(self,'compact',None)==compact and getattr(self,'compact_owner',None)==self.notebook:return
        self.compact,self.compact_owner=compact,self.notebook
        self.brand_label.configure(font=('Segoe UI',22 if compact else 28,'bold'))
        self.header.configure(pady=8 if compact else 14)
        self.database_bar.configure(padding=(24,6 if compact else 10,24,6))
        for button in self.nav_buttons:button.configure(pady=6 if compact else 10)
        self.results_tree.configure(height=2 if compact else 5)
        self.results_table.configure(height=(2 if compact else 5)*30+49)
        self.event_list.configure(height=2 if compact else 5)
        for widget in (self.race_description,self.result_caption,self.stat_hint,self.example_hint):
            widget.pack_forget()
        if not compact:
            self.race_description.pack(anchor='w',pady=(2,8),before=self.track_views)
            self.result_caption.pack(anchor='w',pady=(0,5),before=self.results_table)
            self.stat_hint.pack(anchor='w',before=self.build_choices)
            self.example_hint.pack(anchor='w',pady=(5,0),before=self.build_choices)
        self.root.after_idle(self._size_build_form)

    def _sync_navigation(self,_=None):
        index=self.notebook.index(self.notebook.select())
        for i,button in enumerate(self.nav_buttons):
            button.configure(fg=self.palette['accent'] if i==index else self.palette['masthead_text'],
                             bg=self.palette['nav_selected'] if i==index else self.palette['masthead'])

    def _change_language(self,language):
        self._change_preferences(language=language)

    def _toggle_theme(self):
        self._change_preferences(theme='light' if self.theme_name=='dark' else 'dark')

    def _change_preferences(self,language=None,theme=None):
        language=language or self.tr.language
        theme=theme or self.theme_name
        if language==self.tr.language and theme==self.theme_name:return
        # Preserve raw form edits, including temporarily invalid numbers.
        # Preference switches never validate or write the user's builds.
        if any(isinstance(w,tk.Toplevel) for w in self.root.winfo_children()):
            self.root.bell()
            return
        course_id=getattr(self,'course_labels',{}).get(self.course_var.get())
        conditions=[labels.index(var.get()) for labels,var in [(self.ground,self.ground_var),(self.weather,self.weather_var),(self.seasons,self.season_var)]]
        form={key:var.get() for key,var in self.form_vars.items()}
        strategy=next(k for k,v in self.strategies.items() if v==form['strategy'])
        mood=self.moods.index(form['mood'])
        character=self.character_var.get()
        seed,speed=self.seed_var.get(),self.play_speed.get()
        tab=self.notebook.index(self.notebook.select())
        diagnostic=self.result_diagnostics.get()
        result,playhead,playing=self.result,self.playhead,self.playing
        pane_fraction=max(.4,min(.75,self.result_panes.sashpos(0)/max(1,self.result_panes.winfo_width())))
        scrolls=[(name,getattr(self,name).yview()[0]) for name in ('roster','runner_skills','build_form_canvas','results_tree','event_list','model_text')]
        selected_skills=self.runner_skills.curselection()
        self.settings['language']=language
        self.settings['theme']=theme
        self.theme_name=theme
        self.palette=get_palette(theme)
        self.tr=Translator(language)
        self._choice_labels()
        try:self._save_settings()
        except OSError as error:self._error(error)
        for child in list(self.root.winfo_children()):child.destroy()
        self._style()
        self._layout()
        self._refresh_data(reuse_audit=True)
        if course_id is not None:
            self.course_var.set(next(k for k,v in self.course_labels.items() if v==course_id))
        for labels,var,index in zip((self.ground,self.weather,self.seasons),(self.ground_var,self.weather_var,self.season_var),conditions):var.set(labels[index])
        self.seed_var.set(seed);self.play_speed.set(speed)
        self._refresh_roster();self._load_runner()
        for key,value in form.items():self.form_vars[key].set(value)
        self.form_vars['strategy'].set(self.strategies[strategy]);self.form_vars['mood'].set(self.moods[mood])
        self.character_var.set(character)
        self._refresh_skills()
        self.result_diagnostics.set(diagnostic);self._result_columns()
        if result:
            self._set_result(result)
            self.playhead=playhead;self.playing=playing
            self.seek.set(playhead);self.play_button.configure(text=self.tr('Пауза' if playing else 'Воспроизвести'))
            self._draw()
        else:self._preview_course()
        if self.busy:
            self.play_button.configure(state='disabled')
            self.run_button.configure(state='disabled',text=self.tr('Расчёт…'))
            self.notice.set(self.tr('Рассчитываю совместное поле, рельеф и навыки…'))
        self._navigate(tab)
        self.root.update_idletasks()
        self.result_panes.sashpos(0,int(pane_fraction*self.result_panes.winfo_width()))
        for name,fraction in scrolls:getattr(self,name).yview_moveto(fraction)
        for index in selected_skills:self.runner_skills.selection_set(index)
        # Rebuilt Tk widgets contain Python cycles. Finalize them on the UI thread.
        gc.collect()

    def _connect_initial(self):
        path = DEFAULT_INSTALL
        config = self.local / "settings.json"
        if config.exists():
            try:
                path = Path(json.loads(config.read_text(encoding="utf-8"))["database_path"])
            except (ValueError, KeyError, TypeError, OSError):
                pass
        try:
            self.data = GameData(path)
        except Exception as e:
            self.initial_error = str(e)

    def _default_runners(self):
        names = {c["id"]: c["name"] for c in self.data.characters} if self.data else {}
        ids = [1002, 1003, 1007, 1001, 1008, 1013]
        return [Runner(name=names.get(cid, self.tr('Билд {p0}', p0=i + 1)), chara_id=cid,
                       speed=1050 - i * 15, stamina=800 + i * 25,
                       power=900 + i * 10, guts=450 + i * 15, wisdom=600 + i * 10,
                       strategy=[1, 2, 4, 3, 3, 2][i],popularity=i+1) for i, cid in enumerate(ids)]

    def _bind_loaded_runners(self):
        if not self.data:
            return
        for index, runner in enumerate(self.runners):
            try:
                self.runners[index] = bind_variant(runner, self.data)
            except ValueError:
                # Keep an unavailable explicit ID visible; applying requires a valid selection.
                pass

    def _layout(self):
        mast=tk.Frame(self.root,bg=self.palette['masthead'])
        mast.pack(fill='x')
        self.header=tk.Frame(mast,bg=self.palette['masthead'],padx=24,pady=14)
        self.header.pack(fill='x')
        header=self.header
        self.brand_label=tk.Label(header,text='UMA / RACE LAB',font=('Segoe UI',28,'bold'),bg=self.palette['masthead'],fg=self.palette['masthead_text'])
        self.brand_label.pack(side='left')
        tk.Label(header,text=self.tr('Локальная лаборатория гонок'),font=('Segoe UI',10),bg=self.palette['masthead'],fg=self.palette['masthead_muted']).pack(side='left',padx=24)
        language=tk.Frame(header,bg=self.palette['masthead'])
        language.pack(side='right')
        self.theme_button=tk.Button(language,text=self.tr('Светлая тема' if self.theme_name=='dark' else 'Тёмная тема'),command=self._toggle_theme,
            font=('Segoe UI Semibold',10),bg=self.palette['nav_selected'],fg=self.palette['masthead_text'],
            activebackground=self.palette['accent'],activeforeground=self.palette['on_accent'],relief='flat',bd=0,padx=12,pady=6,
            highlightthickness=1,highlightbackground=self.palette['nav_border'],highlightcolor=self.palette['accent'],takefocus=True,cursor='hand2')
        self.theme_button.pack(side='left',padx=(0,12))
        for code in ('ru','en'):
            selected=code==self.tr.language
            tk.Button(language,text=code.upper(),command=lambda c=code:self._change_language(c),font=('Segoe UI Semibold',10),bg=self.palette['accent'] if selected else self.palette['nav_selected'],fg=self.palette['on_accent'] if selected else self.palette['masthead_text'],activebackground=self.palette['accent'],activeforeground=self.palette['on_accent'],relief='flat',bd=0,padx=12,pady=6,highlightthickness=1,highlightbackground=self.palette['nav_border'],highlightcolor=self.palette['accent'],takefocus=True,cursor='hand2').pack(side='left',padx=(4,0))
        nav=tk.Frame(mast,bg=self.palette['masthead'],padx=24)
        nav.pack(fill='x')
        self.nav_buttons=[]
        for i,label in enumerate(('Гонка и воспроизведение','Билды и навыки','Точность и источники')):
            button=tk.Button(nav,text=self.tr(label),command=lambda n=i:self._navigate(n),font=('Segoe UI Semibold',10),bg=self.palette['masthead'],fg=self.palette['masthead_text'],activebackground=self.palette['nav_selected'],activeforeground=self.palette['accent'],relief='flat',bd=0,padx=16,pady=10,highlightthickness=1,highlightbackground=self.palette['masthead'],highlightcolor=self.palette['accent'],takefocus=True,cursor='hand2')
            button.pack(side='left',padx=(0,6));self.nav_buttons.append(button)
        tk.Label(nav,text=self.tr('Исследовательская модель'),font=('Segoe UI',9),bg=self.palette['masthead'],fg=self.palette['masthead_muted']).pack(side='right',padx=4)
        self.database_bar=ttk.Frame(self.root,padding=(24,10,24,6))
        database=self.database_bar;database.pack(fill='x')
        self.db_status=tk.StringVar()
        ttk.Label(database,textvariable=self.db_status,style='Muted.TLabel').pack(side='left')
        ttk.Button(database,text=self.tr('Выбрать базу…'),command=self._choose_data).pack(side='right')
        self.refresh_button=ttk.Button(database,text=self.tr('Обновить справочник'),command=self._reload_data)
        self.refresh_button.pack(side='right',padx=8)
        self.notice=tk.StringVar(value=self.tr('Готово. Настройте билды, выберите трассу и запустите прогон.'))
        ttk.Label(self.root,textvariable=self.notice,padding=(24,8,24,10),style='Muted.TLabel',wraplength=1200).pack(side='bottom',fill='x')
        self.notebook=ttk.Notebook(self.root)
        self.notebook.pack(fill='both',expand=True,padx=24,pady=(0,8))
        self.race_tab,self.build_tab,self.model_tab=(ttk.Frame(self.notebook,padding=(0,10,0,0)) for _ in range(3))
        for panel,label in zip((self.race_tab,self.build_tab,self.model_tab),('Гонка и воспроизведение','Билды и навыки','Точность и источники')):
            self.notebook.add(panel,text=self.tr(label))
        self.notebook.bind('<<NotebookTabChanged>>',self._sync_navigation)
        self.notebook.enable_traversal()
        self._race_layout();self._builder_layout();self._model_layout()
        self._sync_navigation()
        self.root.bind('<Configure>',self._queue_layout)
        self.root.after_idle(self._adapt_layout)

    def _race_layout(self):
        top = ttk.Frame(self.race_tab)
        top.pack(fill="x")
        ttk.Label(top, text=self.tr('Трасса')).grid(row=0, column=0, sticky="w")
        self.course_var = tk.StringVar()
        self.course_combo = ttk.Combobox(top, textvariable=self.course_var, state="readonly", width=67)
        self.course_combo.grid(row=1, column=0, sticky="ew", padx=(0, 12), pady=(4, 0))
        ttk.Label(top, text="Seed").grid(row=0, column=1, sticky="w")
        self.seed_var = tk.StringVar(value="42")
        ttk.Entry(top, textvariable=self.seed_var, width=12).grid(row=1, column=1, sticky="w")
        self.run_button = ttk.Button(top, text=self.tr('Рассчитать гонку'), style="Primary.TButton", command=self._run)
        self.run_button.grid(row=1, column=2, padx=(16, 0))
        top.columnconfigure(0, weight=1)
        conditions = ttk.Frame(self.race_tab)
        conditions.pack(fill="x", pady=(12, 8))
        self.ground_var, self.weather_var, self.season_var = tk.StringVar(value=self.ground[0]), tk.StringVar(value=self.weather[0]), tk.StringVar(value=self.seasons[2])
        for col, (label, var, values, width) in enumerate([
            (self.tr('Покрытие'), self.ground_var, self.ground, 24), (self.tr('Погода'), self.weather_var, self.weather, 14), (self.tr('Сезон'), self.season_var, self.seasons, 14)]):
            ttk.Label(conditions, text=label).grid(row=0, column=2 * col, padx=(0, 8))
            ttk.Combobox(conditions, textvariable=var, values=values, state="readonly", width=width).grid(row=0, column=2 * col + 1, padx=(0, 20))
        ttk.Button(conditions,text=self.tr('Ещё условия…'),command=self._race_options).grid(row=0,column=6)
        self.race_description=ttk.Label(self.race_tab, text=self.tr('Повороты и уклоны участвуют в расчёте. Метки — участки дистанции; фактический рывок зависит от HP.'), style="Muted.TLabel")
        self.race_description.pack(anchor="w", pady=(2, 8))
        self.track_views = TrackViews(self.race_tab, translator=self.tr,palette=self.palette)
        self.track_views.pack(fill="both", expand=True)
        self.canvas = self.track_views.top
        self.course_combo.bind('<<ComboboxSelected>>',self._preview_course)
        controls = ttk.Frame(self.race_tab)
        controls.pack(fill="x", pady=8)
        self.play_button = ttk.Button(controls, text=self.tr('Воспроизвести'), command=self._toggle_play, state="disabled")
        self.play_button.pack(side="left")
        ttk.Button(controls, text=self.tr('В начало'), command=self._rewind).pack(side="left", padx=8)
        self.play_speed = tk.StringVar(value="4×")
        ttk.Combobox(controls, textvariable=self.play_speed, values=["1×", "4×", "16×"], state="readonly", width=5).pack(side="left")
        self.seek = ttk.Scale(controls, from_=0, to=1, command=self._seek_to)
        self.seek.pack(side="left", fill="x", expand=True, padx=16)
        self.clock = tk.StringVar(value=self.tr('0.0 с'))
        ttk.Label(controls, textvariable=self.clock, width=23).pack(side="left")
        self.export_button = ttk.Button(controls, text=self.tr('Экспорт прогона…'), command=self._export, state="disabled")
        self.export_button.pack(side="right")
        lower = self.result_panes = ttk.Panedwindow(self.race_tab, orient="horizontal")
        lower.pack(fill="both", expand=True)
        results_frame = ttk.Labelframe(lower, text=self.tr('Результаты гонки'), padding=8)
        event_frame = ttk.Labelframe(lower, text=self.tr('События воспроизведения'), padding=8)
        lower.add(results_frame, weight=3)
        lower.add(event_frame, weight=2)
        result_controls = ttk.Frame(results_frame)
        result_controls.pack(fill='x', pady=(0, 6))
        self.result_diagnostics = tk.BooleanVar(value=False)
        ttk.Checkbutton(result_controls, text=self.tr('Расчётные времена'), variable=self.result_diagnostics, command=self._result_columns).pack(side='left')
        ttk.Button(result_controls, text=self.tr('Как читать результаты'), command=self._explain_results).pack(side='right')
        self.result_caption=ttk.Label(results_frame, text=self.tr('Время* — модель табло. L — корпус. Отставание — к строке выше.'), style='Muted.TLabel', wraplength=590)
        self.result_caption.pack(anchor='w', pady=(0, 5))
        self.results_table=ttk.Frame(results_frame)
        self.results_table.configure(width=580,height=199)
        self.results_table.grid_propagate(False)
        self.results_table.pack(fill="both",expand=True)
        self.results_table.columnconfigure(0,weight=1);self.results_table.rowconfigure(0,weight=1)
        self.results_tree = ttk.Treeview(self.results_table, columns=("place", "gate", "name", "time", "margin", "hp", "scaled", "prev", "gap"), show="headings", height=5)
        for key, label, width in [("place", self.tr('Место'), 52), ("gate", "№", 30), ("name", self.tr('Билд'), 155), ("time", self.tr('Время победителя*'), 142), ("margin", self.tr('От предыдущей ≈'), 140), ("hp", "HP, %", 60), ("scaled", self.tr('Расчёт ×1,18, с'), 125), ("prev", self.tr('К предыдущей, с'), 130), ("gap", self.tr('К победителю, с'), 125)]:
            self.results_tree.heading(key, text=label)
            self.results_tree.column(key, width=width, minwidth=35, stretch=key == "name",anchor="w" if key=="name" else "center")
        self.results_tree.tag_configure('winner',background=self.palette['accent_tint'],font=('Segoe UI Semibold',10))
        self.results_tree.tag_configure('even',background=self.palette['row_alt'])
        self.results_tree.tag_configure('odd',background=self.palette['surface'])
        self._result_columns()
        results_scroll = ttk.Scrollbar(self.results_table, orient="vertical", command=self.results_tree.yview)
        results_xscroll = ttk.Scrollbar(self.results_table, orient='horizontal', command=self.results_tree.xview)
        self.results_tree.configure(yscrollcommand=results_scroll.set, xscrollcommand=results_xscroll.set)
        results_scroll.grid(row=0,column=1,sticky="ns")
        results_xscroll.grid(row=1,column=0,sticky="ew")
        self.results_tree.grid(row=0,column=0,sticky="nsew")
        self.results_table.bind('<Configure>',lambda _:self.root.after_idle(self._fit_result_columns))
        self._empty_results()
        self.event_list = tk.Listbox(event_frame,selectbackground=self.palette['selected'],selectforeground=self.palette['ink'], bg=self.palette['surface'], fg=self.palette['ink'], bd=0, highlightthickness=0, font=("Segoe UI", 10), height=5)
        event_scroll = ttk.Scrollbar(event_frame, orient="vertical", command=self.event_list.yview)
        self.event_list.configure(yscrollcommand=event_scroll.set)
        event_scroll.pack(side="right", fill="y")
        self.event_list.pack(fill="both", expand=True)
        # Reserve readable results and controls before giving the remaining
        # space to the diagrams on smaller displays.
        lower.pack_forget();controls.pack_forget();self.track_views.pack_forget()
        lower.pack(side='bottom',fill='x')
        controls.pack(side='bottom',fill='x',pady=8)
        self.track_views.pack(fill='both',expand=True)

    def _builder_layout(self):
        toolbar = ttk.Frame(self.build_tab)
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Label(toolbar, text=self.tr('Состав забега'), style="Section.TLabel").pack(side="left")
        ttk.Button(toolbar, text=self.tr('Загрузить билды…'), command=self._import_builds).pack(side="right")
        ttk.Button(toolbar, text=self.tr('Сохранить билды…'), command=self._save_builds).pack(side="right", padx=8)
        content = ttk.Frame(self.build_tab)
        content.pack(fill="both", expand=True)
        left = ttk.Frame(content)
        left.pack(side="left", fill="y", padx=(0, 16))
        self.roster = tk.Listbox(left, bg=self.palette['surface'], fg=self.palette['ink'], selectbackground=self.palette["selected"], selectforeground=self.palette['ink'],
                                 font=("Segoe UI", 11), width=21, height=14, bd=0, highlightthickness=1,
                                 highlightbackground=self.palette["border"], highlightcolor=self.palette["accent"], exportselection=False)
        self.roster.pack(fill="both", expand=True)
        self.roster.bind("<<ListboxSelect>>", self._select_runner)
        ttk.Button(left, text=self.tr('Добавить билд'), command=self._add_runner).pack(fill="x", pady=(12, 6))
        ttk.Button(left, text=self.tr('Дублировать'), command=self._duplicate_runner).pack(fill="x", pady=6)
        ttk.Button(left, text=self.tr('Удалить из состава'), command=self._remove_runner).pack(fill="x", pady=6)
        right = self.build_editor = ttk.Frame(content)
        right.pack(side="left", fill="both", expand=True)
        right.bind('<Configure>',lambda _:self._size_build_form())
        top_shell=ttk.Frame(right)
        top_shell.pack(fill='x')
        self.build_form_canvas=tk.Canvas(top_shell,height=360,bg=self.palette['background'],bd=0,highlightthickness=0,yscrollincrement=24)
        form_scroll=ttk.Scrollbar(top_shell,command=self.build_form_canvas.yview)
        self.build_form_canvas.configure(yscrollcommand=form_scroll.set)
        form_scroll.pack(side='right',fill='y')
        self.build_form_canvas.pack(side='left',fill='both',expand=True)
        self.build_form=ttk.Frame(self.build_form_canvas)
        form_window=self.build_form_canvas.create_window(0,0,window=self.build_form,anchor='nw')
        self.build_form.bind('<Configure>',lambda _:self._size_build_form())
        self.build_form_canvas.bind('<Configure>',lambda e:self.build_form_canvas.itemconfigure(form_window,width=e.width))
        form = ttk.Frame(self.build_form)
        form.pack(fill="x")
        self.form_vars = {key: tk.StringVar() for key in ("name", *STATS, "strategy", "mood", "unique_level", "card_rarity", *APTITUDE_KEYS)}
        ttk.Label(form, text=self.tr('Имя билда')).grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.form_vars["name"], width=22).grid(row=1, column=0, sticky="ew", padx=(0, 16), pady=4)
        ttk.Label(form, text=self.tr('Ума и версия костюма')).grid(row=0, column=1, sticky="w")
        self.character_var = tk.StringVar()
        self.character_combo = ttk.Combobox(form, textvariable=self.character_var, state="readonly", width=32)
        self.character_combo.grid(row=1, column=1, sticky="ew", pady=4)
        self.character_combo.bind('<<ComboboxSelected>>', self._variant_changed)
        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=2)
        stats = ttk.Frame(self.build_form)
        stats.pack(fill="x", pady=(12, 8))
        for col, key in enumerate(STATS):
            tk.Label(stats, text=self.stat_labels[key], bg=self.palette['stat_header'], fg=self.palette['stat_header_ink'],
                     font=('Segoe UI Semibold', 10), pady=5).grid(row=0, column=col, sticky='ew', padx=1)
            ttk.Spinbox(stats, from_=1, to=5000, textvariable=self.form_vars[key], width=6, font=('Segoe UI Semibold', 16),
                        justify='center').grid(row=1, column=col, sticky='ew', padx=1, pady=(1,0))
            stats.columnconfigure(col, weight=1)
        self.stat_hint=ttk.Label(self.build_form, text=self.tr('Статы выше 1200 участвуют в расчёте: избыток учитывается с коэффициентом ½.'), style="Muted.TLabel")
        self.stat_hint.pack(anchor="w")
        self.example_hint=ttk.Label(self.build_form, text=self.tr('Смена версии обновляет уникальный навык и базовые пригодности. Статы вводятся вручную.'), style="Muted.TLabel", wraplength=840)
        self.example_hint.pack(anchor="w", pady=(5,0))
        choices = self.build_choices = ttk.Frame(self.build_form)
        choices.pack(fill="x", pady=(8, 4))
        aptitude_table = ttk.Frame(choices)
        aptitude_table.pack(fill='x')
        aptitude_rows = [('Поверхность', [('Трава','turf'),('Грунт','dirt')]),
                         ('Дистанция', [('Спринт','sprint'),('Миля','mile'),('Средняя','medium'),('Длинная','long')]),
                         ('Стиль', [('Front','front'),('Pace','pace'),('Late','late'),('End','end')])]
        for row, (label, entries) in enumerate(aptitude_rows):
            ttk.Label(aptitude_table, text=self.tr(label), font=('Segoe UI Semibold',10)).grid(row=row, column=0, sticky='w', padx=(0,8), pady=3)
            for column, (caption, key) in enumerate(entries, 1):
                cell=ttk.Frame(aptitude_table,style='Card.TFrame')
                cell.grid(row=row,column=column,sticky='ew',padx=3,pady=3)
                tk.Label(cell,text=self.tr(caption),bg=self.palette['surface'],fg=self.palette['ink'],font=('Segoe UI',10)).pack(side='left',padx=(7,3))
                ttk.Combobox(cell,textvariable=self.form_vars[key],values=list(reversed(GRADES)),state='readonly',width=2,
                             font=('Segoe UI Semibold',11),justify='center').pack(side='right',padx=(0,2))
        for column in range(1,5):aptitude_table.columnconfigure(column,weight=1,uniform='aptitude')
        race_choices=ttk.Frame(choices)
        race_choices.pack(fill='x',pady=(6,0))
        specs = [(self.tr('Стратегия'), 'strategy', list(self.strategies.values()), 23),
                 (self.tr('Настроение'), 'mood', self.moods, 11),
                 (self.tr('Звёзды умы'), 'card_rarity', [], 4)]
        for col, (label, key, values, width) in enumerate(specs):
            ttk.Label(race_choices, text=label).grid(row=0, column=col, sticky='w',padx=(0,10))
            combo=ttk.Combobox(race_choices, textvariable=self.form_vars[key], values=values, state='readonly', width=width)
            combo.grid(row=1,column=col,sticky='ew',padx=(0,10),pady=4)
            if key=='card_rarity':
                self.rarity_combo=combo
                combo.bind('<<ComboboxSelected>>',self._rarity_changed)
        ttk.Label(race_choices,text=self.tr('Уровень уникального')).grid(row=0,column=3,sticky='w')
        ttk.Spinbox(race_choices,from_=1,to=6,textvariable=self.form_vars['unique_level'],width=4).grid(row=1,column=3,sticky='ew',pady=4)
        self.form_vars['unique_level'].trace_add('write',lambda *_: self._refresh_skills())
        race_choices.columnconfigure(0,weight=1)
        skill_header=self.build_skill_header=ttk.Frame(right)
        skill_header.pack(fill='x',pady=(8,6))
        self.skills_heading=tk.StringVar(value=self.tr('Навыки билда'))
        ttk.Label(skill_header,textvariable=self.skills_heading,font=('Segoe UI Semibold',12)).pack(side='left')
        ttk.Button(skill_header,text=self.tr('Параметры навыков…'),command=self._advanced_runner).pack(side='right')
        skillframe = ttk.Frame(right)
        skillframe.pack(fill='both',expand=True)
        self.runner_skills = SkillGrid(skillframe,self.palette,self._show_skill_details)
        self.runner_skills.pack(fill="both", expand=True)
        skill_buttons = self.build_skill_buttons = ttk.Frame(right)
        skill_buttons.pack(fill="x")
        ttk.Button(skill_buttons, text=self.tr('Выбрать навык из игры…'), command=self._open_skills).pack(side="left")
        ttk.Button(skill_buttons, text=self.tr('Убрать выбранный'), command=self._remove_skill).pack(side="left", padx=8)
        ttk.Button(skill_buttons, text=self.tr('Подробнее'), command=self._selected_skill_details).pack(side='left')
        ttk.Button(skill_buttons, text=self.tr('Применить билд'), style="Primary.TButton", command=self._apply_runner).pack(side="right")
        self.catalog_hint=ttk.Label(right, text=self.tr('Все записи master.mdb доступны в справочнике. Эффекты вне модели явно блокируют расчёт.'), style="Muted.TLabel",wraplength=740)
        # Give actions and at least one row of cards room; only the form scrolls when short.
        for widget in (top_shell,skill_header,skillframe,skill_buttons):widget.pack_forget()
        skill_buttons.pack(side="bottom",fill="x",pady=(8,0))
        top_shell.pack(fill='x')
        skill_header.pack(fill='x',pady=(8,6))
        skillframe.pack(fill='both',expand=True,pady=(0,4))
        def form_events(widget):
            widget.bind('<MouseWheel>',lambda e:self._scroll_build_form(e))
            widget.bind('<FocusIn>',lambda _,w=widget:self._see_build_field(w),add='+')
            for child in widget.winfo_children():form_events(child)
        form_events(self.build_form)
        self.build_form_canvas.bind('<MouseWheel>',self._scroll_build_form)

    def _size_build_form(self):
        if not hasattr(self,'build_form_canvas') or not self.build_form_canvas.winfo_exists():return
        canvas=self.build_form_canvas
        wanted=self.build_form.winfo_reqheight()
        reserved=self.build_skill_header.winfo_reqheight()+self.build_skill_buttons.winfo_reqheight()+self.runner_skills.card_height+40
        height=min(wanted,max(190,self.build_editor.winfo_height()-reserved))
        if int(canvas.cget('height'))!=height:canvas.configure(height=height)
        canvas.configure(scrollregion=canvas.bbox('all'))

    def _scroll_build_form(self,event):
        self.build_form_canvas.yview_scroll(-int(event.delta/120),'units')
        return 'break'

    def _see_build_field(self,widget):
        canvas=self.build_form_canvas
        widget_top=widget.winfo_rooty()-self.build_form.winfo_rooty()
        top=max(0,widget_top-28)  # Keep the field's label in view with keyboard focus.
        bottom=widget_top+widget.winfo_height()+8
        current=canvas.canvasy(0)
        total=max(1,self.build_form.winfo_reqheight())
        if top<current:canvas.yview_moveto(top/total)
        elif bottom>current+canvas.winfo_height():
            canvas.yview_moveto((bottom-canvas.winfo_height())/total)

    def _model_layout(self):
        self.model_text = text = tk.Text(self.model_tab,insertbackground=self.palette['ink'],selectbackground=self.palette['selected'],selectforeground=self.palette['ink'], bg=self.palette['surface'], fg=self.palette['ink'], font=("Segoe UI", 12), wrap="word", relief="flat", padx=24, pady=20)
        scroll = ttk.Scrollbar(self.model_tab, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        text.tag_configure("title", font=("Segoe UI Semibold", 18), spacing3=14)
        text.tag_configure("head", font=("Segoe UI Semibold", 12), spacing1=18, spacing3=8)
        text.insert("end", self.tr('Точность должна быть измерена\n'), "title")
        text.insert("end", self.tr('Процент совпадения с игрой пока неизвестен: нужны эталонные кадры с известными билдами. Поддержка условия или эффекта означает участие в модели; она ещё не доказывает совпадение с нативным расчётом.\n'))
        text.insert('end',self.tr('Время гонки и время табло\n'),'head')
        text.insert('end',self.tr('Время победителя* — модель игрового табло в формате минуты:секунды.десятые. У остальных показано отставание от предыдущей строки: Nose, Head, Neck, доли корпуса (L). Локально прочитаны enum HorseLength и DIFFTIME_TO_LENGTH=15. Пороги категорий, округление и использование scaled-разницы — пока интерпретация, поэтому стоят знаки ≈. Отставания не вычисляются из скорректированного времени победителя.\n'))
        text.insert('end',self.tr('Флажок «Расчётные времена» показывает шкалу raw × FinishTimeCoef (×1,18), разницу с предыдущей и с победителем в секундах. Например, 88,333 с до коррекции может стать 1:31.0 на табло Kyoto. Счётчик воспроизведения остаётся во внутренних секундах. Поправка табло не меняет движения, навыков и ранга; нативный RNG табло не воспроизведён. Момент финиша интерполируется внутри шага движения, чтобы не терять близкие разрывы.\n'))
        text.insert("end", self.tr('Подтверждено вашей установкой\n'), "head")
        text.insert("end", self.tr('Unity 2022.3.62f2, IL2CPP v31.1. Из master.mdb читаются 734 навыка, все ветки, уровни и коэффициенты. Из локальных Unity-ресурсов извлечены игровые повороты, уклоны и 1001 точка реального пути для 119/121 трасс. Две записи без ресурсов не заменяются вымышленными трассами. Шаг 0,0666000023 с подтверждён метаданными.\n'))
        text.insert("end", self.tr('Что считает текущая модель\n'), "head")
        text.insert("end", self.tr('Совместное поле 1–18 участниц: полосы, блокировки, удержание позиции, обгоны, HP, kakari, спуски, рывок, борьба и сохранение силы. Учитываются статы выше 1200, пассивы, уникальные и унаследованные навыки, обе ветки, уровни, динамическая длительность и дополнительные эффекты. Неизвестные эффекты не пропускаются молча. Сценарные Carnival Bonus (501–503) требуют отдельной модели сценария и не участвуют в обычном забеге.\n'))
        text.insert("end", self.tr('Ограничения\n'), "head")
        for limitation in LIMITATIONS:
            text.insert("end", "• " + self.tr.dynamic(limitation) + "\n")
        text.insert("end", self.tr('Источники и следующий этап\n'), "head")
        text.insert("end", self.tr('Основа — открытый honse-sim 0.13.0 (GPL-3.0), с локальными исправлениями времени, обзора, обгонов, веток и длительностей. Часть динамических условий и повторных активаций требует дальнейшей сверки. Подробности и границы достоверности: docs/ACCURACY.md.\n\n'))
        url = "https://github.com/jalbarrang/torena-sim"
        text.tag_configure("source", foreground=self.palette['ink'], underline=True)
        text.insert("end", url, "source")
        text.tag_bind("source", "<Button-1>", lambda _: webbrowser.open(url))
        text.tag_bind("source", "<Enter>", lambda _: text.configure(cursor="hand2"))
        text.tag_bind("source", "<Leave>", lambda _: text.configure(cursor="xterm"))
        text.configure(state="disabled")

    def _refresh_data(self, reuse_audit=False):
        if not self.data:
            self.db_status.set(self.tr('База не подключена. Выберите master.mdb из установки игры.'))
            return
        d = self.data
        self.db_status.set(self.tr('База подключена · {p0} трасс · {p1} навыков · SHA256 {p2}', p0=len(d.courses), p1=len(d.skills), p2=d.fingerprint[:10]))
        old = self.course_var.get()
        self.course_labels = {self._course_label(c): c["id"] for c in d.courses}
        self.course_combo.configure(values=list(self.course_labels))
        if old in self.course_labels:
            self.course_var.set(old)
        else:
            default = next((self._course_label(c) for c in d.courses if c["name"] == "Tokyo" and c["distance"] == 2400 and c["ground"] == 1), next(iter(self.course_labels), ""))
            self.course_var.set(default)
        self.character_labels = {f"{v['display_name']} · #{v['id']}": v['id'] for v in sorted(d.variants,key=lambda v:(v['display_name'].casefold(),v['id'])) if v['profiles']}
        self.character_combo.configure(values=list(self.character_labels))
        try:
            audit=None if reuse_audit else audit_catalog(d)
            if audit is not None:
                self.skill_audit={int(s['skillId']):s for s in audit['effects']}
                self.audit_ready=True
        except Exception as e:
            self.skill_audit={}
            self.audit_ready=False
            self.notice.set(self.tr('Аудит навыков недоступен: ')+str(e))
        self._preview_course()

    def _choose_data(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(title=self.tr('Выберите master.mdb'), initialdir=str(DEFAULT_INSTALL / "UmamusumePrettyDerby_Data/Persistent/master"), filetypes=[(self.tr('База игры'), "*.mdb"), (self.tr('Все файлы'), "*")], parent=self.root)
        if path:
            try:
                data = GameData(Path(path))
                self.data = data
                self._bind_loaded_runners()
                self.settings["database_path"]=str(data.path)
                self._save_settings()
                self._refresh_data()
                self._load_runner()
                self.notice.set(self.tr('Подключена база ') + str(data.path))
            except Exception as e:
                self._error(e)

    def _reload_data(self):
        if self.busy or not self.data:
            return
        try:
            self.data.reload()
            self._bind_loaded_runners()
            self._refresh_data()
            self._load_runner()
            self.notice.set(self.tr('Справочник обновлён из установленной игры. Следующий запуск использует эту версию базы.'))
        except Exception as e:
            self._error(e)

    def _refresh_roster(self):
        self.roster.delete(0, "end")
        for i, runner in enumerate(self.runners):
            self.roster.insert("end", f"{i + 1:02d}  {runner.name}")
        self.roster.selection_set(self.active_runner)

    def _load_runner(self):
        r = self.runners[self.active_runner]
        for key in ("name", *STATS, "unique_level", "card_rarity"):
            self.form_vars[key].set(str(getattr(r, key)))
        for key,value in (r.aptitudes or legacy_aptitudes(r)).items():self.form_vars[key].set(value)
        self.form_vars["strategy"].set(self.strategies[r.strategy])
        self.form_vars["mood"].set(self.moods[r.mood - 1])
        variant=find_variant(r,self.data) if self.data else None
        variant_id=variant['id'] if variant else r.outfit_id
        self.character_var.set(next((label for label, cid in getattr(self, 'character_labels', {}).items() if cid == variant_id),
                                    self.tr('Неизвестная версия #{p0}',p0=variant_id) if variant_id else ''))
        self._rarity_choices(variant)
        self._refresh_skills()
        self.build_form_canvas.yview_moveto(0)

    def _rarity_choices(self,variant):
        self.rarity_combo.configure(values=sorted(variant['profiles']) if variant else [])

    def _variant_changed(self,_=None):
        if not self.data:return
        variant_id=self.character_labels.get(self.character_var.get())
        if variant_id is None:return
        try:
            original=self.runners[self.active_runner]
            variant=next(v for v in self.data.variants if v['id']==variant_id)
            # Keep stars where valid; a three-star costume cannot use a one-star profile.
            stars=int(self.form_vars['card_rarity'].get() or 3)
            if stars not in variant['profiles']:stars=max(3,variant['default_rarity'])
            runner=bind_variant(original,self.data,variant_id,stars,reset_aptitudes=variant_id!=original.outfit_id)
            self.runners[self.active_runner]=runner
            self.form_vars['card_rarity'].set(str(runner.card_rarity))
            self._rarity_choices(variant)
            if variant_id!=original.outfit_id:
                for key,value in runner.aptitudes.items():self.form_vars[key].set(value)
            self._refresh_skills()
        except ValueError as error:self._error(error)

    def _rarity_changed(self,_=None):
        self._variant_changed()

    def _commit_runner(self):
        values = {"name": self.form_vars["name"].get().strip()}
        try:
            values.update({key: int(self.form_vars[key].get()) for key in (*STATS, "unique_level", "card_rarity")})
            values["strategy"] = next(k for k, v in self.strategies.items() if v == self.form_vars["strategy"].get())
            values["mood"] = self.moods.index(self.form_vars["mood"].get()) + 1
            values['aptitudes']={key:self.form_vars[key].get() for key in APTITUDE_KEYS}
        except (ValueError, StopIteration) as e:
            raise ValueError(self.tr('Проверьте числовые характеристики, стратегию и настроение билда')) from e
        r = replace(self.runners[self.active_runner], **values)
        variant_id=getattr(self,'character_labels',{}).get(self.character_var.get())
        if self.data:
            if variant_id is None:
                raise ValueError(self.tr('Выберите конкретную версию умы'))
            r=bind_variant(r,self.data,variant_id,r.card_rarity)
        r.validate()
        self.runners[self.active_runner] = r

    def _select_runner(self, _=None):
        selected = self.roster.curselection()
        if not selected or selected[0] == self.active_runner:
            return
        try:
            self._commit_runner()
            self.active_runner = selected[0]
            self._refresh_roster()
            self._load_runner()
        except ValueError as e:
            self._refresh_roster()
            self._error(e)

    def _apply_runner(self):
        try:
            self._commit_runner()
            self._refresh_roster()
            self._autosave()
            self.notice.set(self.tr('Билд сохранён локально. Ранее рассчитанная гонка сохраняет свой исходный состав.'))
        except (ValueError, OSError) as e:
            self._error(e)

    def _add_runner(self):
        try:
            self._commit_runner()
            if len(self.runners) >= 18:
                raise ValueError(self.tr('В забеге не более 18 участников'))
            runner=Runner(name=self.tr('Билд {p0}', p0=len(self.runners) + 1),popularity=len(self.runners)+1)
            if self.data and self.data.variants:
                previous=self.runners[self.active_runner]
                variant=find_variant(previous,self.data) or self.data.variants[0]
                runner=bind_variant(runner,self.data,variant['id'],max(3,variant['default_rarity']),reset_aptitudes=True)
            self.runners.append(runner)
            self.active_runner = len(self.runners) - 1
            self._refresh_roster()
            self._load_runner()
            self._autosave()
        except (ValueError, OSError) as e:
            self._error(e)

    def _duplicate_runner(self):
        try:
            self._commit_runner()
            if len(self.runners) >= 18:
                raise ValueError(self.tr('В забеге не более 18 участников'))
            r = self.runners[self.active_runner]
            self.runners.append(replace(r, name=(r.name[:90] + self.tr(' · копия')), skills=r.skills.copy(),aptitudes=r.aptitudes.copy()))
            self.active_runner = len(self.runners) - 1
            self._refresh_roster()
            self._load_runner()
            self._autosave()
        except (ValueError, OSError) as e:
            self._error(e)

    def _remove_runner(self):
        if len(self.runners) <= 1:
            return self._error(ValueError(self.tr('Оставьте хотя бы один билд')))
        self.runners.pop(self.active_runner)
        self.active_runner = min(self.active_runner, len(self.runners) - 1)
        self._refresh_roster()
        self._load_runner()
        self._autosave()

    def _refresh_skills(self):
        if not hasattr(self,'runner_skills'):return
        runner=self.runners[self.active_runner]
        own=owned_unique(runner,self.data) if self.data else None
        ids=sorted(runner.skills,key=lambda sid:0 if sid==own else 1)
        self.runner_skills.set_items([self._skill_item(sid) for sid in ids])
        self.skills_heading.set(self.tr('Навыки билда · {p0}',p0=len(ids)))

    def _skill_item(self,sid):
        skill=self.data.skills.get(sid,{}) if self.data else {}
        rarity=skill.get('rarity',1)
        kind='unique' if rarity in UNIQUE_RARITIES else 'gold' if rarity==2 else 'normal'
        label=self.tr('Уникальный') if kind=='unique' else self.tr('Золотой') if kind=='gold' else self.tr('Эволюция') if rarity==6 else self.tr('Обычный')
        own=owned_unique(self.runners[self.active_runner],self.data) if self.data else None
        if sid==own:
            label+=' · '+self.tr('Закреплён')+' · Lv '+self.form_vars['unique_level'].get()
        elif rarity==1 and self.data and self.data.skills.get(sid-800000,{}).get('rarity') in UNIQUE_RARITIES:
            label=self.tr('Унаследованный')
        return {'id':sid,'name':skill.get('name',self.tr('Неизвестный')),'description':skill.get('description',''),
                'kind':kind,'label':label}

    def _selected_skill_details(self):
        selected=self.runner_skills.curselection()
        if selected:self._show_skill_details(self.runner_skills.items[selected[0]]['id'])

    def _show_skill_details(self,sid):
        window=tk.Toplevel(self.root)
        window.title(self.tr('Подробности навыка'))
        window.geometry('760x410');window.minsize(620,360)
        window.transient(self.root);window.grab_set()
        panel=ttk.Frame(window,padding=24);panel.pack(fill='both',expand=True)
        ttk.Label(panel,text=self.tr('Подробности навыка'),font=('Segoe UI Semibold',18)).pack(anchor='w',pady=(0,20))
        card=SkillDetailCard(panel,self.palette);card.pack(fill='x')
        card.set_item(self._skill_item(sid))
        skill=self.data.skills.get(sid) if self.data else None
        status=self._skill_status(skill)[1] if skill else self.tr('неизвестный ID')
        ttk.Label(panel,text=f'#{sid} · {status}',style='Muted.TLabel',wraplength=680).pack(anchor='w',pady=14)
        ttk.Button(panel,text=self.tr('Закрыть'),command=window.destroy).pack(side='bottom',anchor='e')
        window.bind('<Escape>',lambda _:window.destroy())

    def _remove_skill(self):
        selected = self.runner_skills.curselection()
        if selected:
            sid=self.runner_skills.items[selected[0]]['id']
            if self.data and sid==owned_unique(self.runners[self.active_runner],self.data):
                self.notice.set(self.tr('Уникальный навык закреплён за версией умы. Для замены выберите другую версию или редкость.'))
                return
            try:self._commit_runner()
            except ValueError as error:return self._error(error)
            self.runners[self.active_runner].skills.remove(sid)
            self._refresh_skills()
            self._autosave()

    def _open_skills(self):
        if not self.data:
            return self._error(ValueError(self.tr('Сначала подключите базу игры')))
        try:
            self._commit_runner()
        except ValueError as e:
            return self._error(e)
        window = tk.Toplevel(self.root)
        window.title(self.tr('Навыки установленной игры'))
        window.geometry("940x680")
        window.minsize(820, 560)
        window.transient(self.root)
        window.grab_set()
        panel = ttk.Frame(window, padding=18)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text=self.tr('Справочник навыков'), font=("Segoe UI Semibold", 18)).pack(anchor="w")
        controls = ttk.Frame(panel)
        controls.pack(fill="x", pady=12)
        query = tk.StringVar()
        ttk.Label(controls, text=self.tr('Имя или ID')).pack(side="left", padx=(0, 8))
        entry = ttk.Entry(controls, textvariable=query, width=35)
        entry.pack(side="left")
        only_supported = tk.BooleanVar(value=False)
        ttk.Checkbutton(controls, text=self.tr('Только участвующие в расчёте'), variable=only_supported).pack(side="left", padx=16)
        treeframe = ttk.Frame(panel)
        tree = ttk.Treeview(treeframe, columns=("id", "name", "rarity", "support"), show="headings", height=12, selectmode="browse")
        self.skill_picker_tree=tree
        for kind in ('unique','gold','normal'):
            tree.tag_configure(kind,background=self.palette['skill_'+kind][0],foreground=self.palette['skill_ink'])
        for key, label, width in [("id", "ID", 80), ("name", self.tr('Название'), 300), ("rarity", self.tr('Тип'), 100), ("support", self.tr('Статус расчёта'), 200)]:
            tree.heading(key, text=label)
            tree.column(key, width=width, stretch=key == "name")
        scroll = ttk.Scrollbar(treeframe, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)
        detail = tk.Text(panel,insertbackground=self.palette['ink'],selectbackground=self.palette['selected'],selectforeground=self.palette['ink'], height=3, wrap="word", bg=self.palette['surface'], fg=self.palette['ink'], font=("Segoe UI", 10), relief="flat", padx=10, pady=8)
        card=SkillDetailCard(panel,self.palette)
        self.skill_picker_card=card
        count = tk.StringVar()
        footer = ttk.Frame(panel)
        footer.pack(side="bottom", fill="x")
        detail.pack(side="bottom", fill="x", pady=(4,10))
        card.pack(side='bottom',fill='x',pady=(10,0))
        treeframe.pack(fill="both", expand=True)
        ttk.Label(footer, textvariable=count, style="Muted.TLabel").pack(side="left")

        def refresh(*_):
            tree.delete(*tree.get_children())
            search = query.get().strip().casefold()
            total = 0
            for sid, skill in sorted(self.data.skills.items()):
                ok, why = self._skill_status(skill)
                if only_supported.get() and not ok:
                    continue
                if search and search not in skill["name"].casefold() and search not in str(sid):
                    continue
                inherited=self.data.skills.get(sid-800000,{})
                kind=self.tr('Унаследованный') if skill['rarity']==1 and inherited.get('rarity') in (3,4,5) else {1:self.tr('Обычный'),2:self.tr('Золотой'),3:self.tr('Уникальный'),4:self.tr('Уникальный'),5:self.tr('Уникальный'),6:self.tr('Эволюция')}.get(skill['rarity'],self.tr('Особый'))
                background='unique' if skill['rarity'] in UNIQUE_RARITIES else 'gold' if skill['rarity']==2 else 'normal'
                tree.insert("", "end", iid=str(sid), values=(sid, skill["name"],kind,why),tags=(background,))
                total += 1
            count.set(self.tr('Найдено: {p0} / {p1}', p0=total, p1=len(self.data.skills)))

        def show(*_):
            if not tree.selection():
                return
            skill = self.data.skills[int(tree.selection()[0])]
            card.set_item(self._skill_item(skill['id']))
            runner=self.runners[self.active_runner]
            foreign=skill['rarity'] in UNIQUE_RARITIES and skill['id']!=owned_unique(runner,self.data)
            add_button.configure(state='disabled' if foreign or skill['id'] in runner.skills else 'normal')
            ok, why = self._skill_status(skill)
            effects = [self.tr('тип {p0}: {p1} / 10000', p0=skill[f'ability_type_1_{i}'], p1=skill[f'float_ability_value_1_{i}']) for i in range(1, 4) if skill[f"ability_type_1_{i}"]]
            detail.configure(state="normal")
            detail.delete("1.0", "end")
            branches='\n'.join(self.tr('Ветка {p0}: {p1}\nПредусловие: {p2}', p0=b, p1=skill.get('condition_' + str(b), ''), p2=skill.get('precondition_' + str(b), '') or self.tr('нет')) for b in (1,2) if skill.get('condition_'+str(b)))
            detail.insert("end", self.tr('{p0} · #{p1}\n{p2}\n{p3}\nЭффекты ветки 1: {p4}\n{p5}. Совпадение с игрой ещё не измерено.\n', p0=skill['name'], p1=skill['id'], p2=skill['description'].replace(chr(92) + 'n', ' '), p3=branches, p4=', '.join(effects), p5=why)+'; '.join(self.tr.dynamic(s) for s in fidelity_issues(skill)))
            if skill['rarity'] in (3,4,5) and skill['id']+800000 in self.data.skills:
                detail.insert('end',self.tr('\nПолная уникальная версия. Для наследования есть отдельный навык #{p0}; у него другая сила и длительность.', p0=skill['id'] + 800000))
            if foreign:detail.insert('end','\n'+self.tr('Этот уникальный навык принадлежит другой версии умы. Выберите унаследованный навык.'))
            detail.configure(state="disabled")

        def add():
            if not tree.selection():
                return
            sid = int(tree.selection()[0])
            runner = self.runners[self.active_runner]
            if sid not in runner.skills:
                try:
                    self.runners[self.active_runner]=add_build_skill(runner,sid,self.data)
                    self._refresh_skills()
                    self._autosave()
                    count.set(self.tr('Добавлен навык #{p0}', p0=sid))
                    show()
                except (ValueError,OSError) as error:self._error(error)

        ttk.Button(footer, text=self.tr('Закрыть'), command=window.destroy).pack(side="right")
        add_button=ttk.Button(footer, text=self.tr('Добавить в билд'), style="Primary.TButton", command=add,state='disabled')
        self.skill_picker_add=add_button
        add_button.pack(side="right", padx=8)
        query.trace_add("write", refresh)
        only_supported.trace_add("write", refresh)
        tree.bind("<<TreeviewSelect>>", show)
        tree.bind("<Double-1>", lambda _: add())
        tree.bind('<Return>',lambda _:add())
        window.bind("<Escape>", lambda _: window.destroy())
        refresh()
        entry.focus_set()

    def _autosave(self):
        save_builds(self.local / "autosave-builds.json", self.runners)

    def _save_builds(self):
        try:
            self._commit_runner()
            path = filedialog.asksaveasfilename(title=self.tr('Сохранить билды'), initialdir=str(self.local), initialfile="builds.json", defaultextension=".json", filetypes=[("JSON", "*.json")], parent=self.root)
            if path:
                save_builds(Path(path), self.runners)
                self.notice.set(self.tr('Билды сохранены: ') + path)
        except (ValueError, OSError) as e:
            self._error(e)

    def _import_builds(self):
        path = filedialog.askopenfilename(title=self.tr('Загрузить билды'), initialdir=str(self.local), filetypes=[("JSON", "*.json")], parent=self.root)
        if path:
            try:
                runners = load_builds(Path(path))
                self.runners = runners
                self._bind_loaded_runners()
                self.active_runner = 0
                self._refresh_roster()
                self._load_runner()
                self._autosave()
            except (ValueError, OSError) as e:
                self._error(e)

    def _run(self):
        if self.busy:
            return
        try:
            if not self.data:
                raise ValueError(self.tr('Сначала подключите базу игры'))
            self._commit_runner()
            if self.data.changed():
                self.data.reload()
                self._bind_loaded_runners()
                self._refresh_data()
            config = RaceConfig(self.course_labels[self.course_var.get()], int(self.seed_var.get()),
                                self.ground.index(self.ground_var.get()) + 1, self.weather.index(self.weather_var.get()) + 1, self.seasons.index(self.season_var.get()) + 1,self.time_of_day,self.race_grade)
            config.validate()
            for index,runner in enumerate(self.runners):
                if find_variant(runner,self.data) is None:
                    raise ValueError(self.tr('Для билда «{p0}» выберите конкретную версию умы',p0=runner.name))
                self.runners[index]=bind_variant(runner,self.data)
            self._autosave()
            runners = [replace(r, skills=r.skills.copy(),aptitudes=r.aptitudes.copy()) for r in self.runners]
            self.busy = True
            self.playing = False
            self.run_button.configure(state="disabled", text=self.tr("Расчёт…"))
            self.play_button.configure(state="disabled", text=self.tr('Воспроизвести'))
            self.notice.set(self.tr('Рассчитываю совместное поле, рельеф и навыки…'))
            data = self.data

            def work():
                try:
                    data.ensure_course_catalog()
                    self.results_queue.put(simulate(runners, config, data))
                except Exception as e:
                    self.results_queue.put(e)

            gc.collect()
            self.worker = threading.Thread(target=work, daemon=True)
            self.worker.start()
        except (ValueError, KeyError, OSError) as e:
            self._error(e)

    def _poll_result(self):
        try:
            result = self.results_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.run_button.configure(state="normal", text=self.tr("Рассчитать гонку"))
            if isinstance(result, Exception):
                self.play_button.configure(state="normal" if self.result else "disabled")
                self.notice.set(self.tr('Расчёт остановлен: проверьте состав и поддержку навыков.'))
                self._error(result)
            else:
                self._set_result(result)
        self.root.after(100, self._poll_result)

    def _set_result(self, result: RaceResult):
        self.result = result
        self.frame_times = [f["time"] for f in result.frames]
        self.seek.configure(to=self.frame_times[-1])
        self.playhead = 0.
        self.seek.set(0)
        self.last_event_count = -1
        self.play_button.configure(state="normal", text=self.tr('Воспроизвести'))
        self.export_button.configure(state="normal")
        self.results_tree.delete(*self.results_tree.get_children())
        times=result.scaled_finish_times or result.finish_times
        best = min(times)
        order=sorted(range(len(result.runners)), key=lambda i: (result.finish_times[i], i))
        for rank, idx in enumerate(order):
            board=result.display_finish_times[idx] if result.display_finish_times else None
            margin=result.finish_margins[idx] if result.finish_margins else None
            previous=f'+{times[idx]-times[order[rank-1]]:.4f}' if rank else '-'
            label=('≈ '+margin['label']) if margin else ('-' if rank==0 else self.tr('нет данных'))
            self.results_tree.insert("", "end", tags=("winner" if rank==0 else "even" if rank%2==0 else "odd",), values=(rank + 1, idx + 1, result.runners[idx]["name"], format_board_time(board) if board is not None else '-', label, f"{100 * result.frames[-1]['runners'][idx]['hp_ratio']:.1f}", f"{times[idx]:.4f}", previous, f"+{times[idx] - best:.4f}"))
        self.notice.set(self.tr('Готово · seed {p0} · {p1} кадров · модель {p2} · точность относительно игры не измерена', p0=result.seed, p1=len(result.frames), p2=result.model)+ (self.tr(' · оговорки по {p0} навыкам в экспорте', p0=len(result.support_report)) if result.support_report else ''))
        self._draw()

    def _result_columns(self):
        columns=('place','gate','name','time','margin','hp')
        if self.result_diagnostics.get():
            columns+=('scaled','prev','gap')
        self.results_tree.configure(displaycolumns=columns)
        self.root.after_idle(self._fit_result_columns)

    def _fit_result_columns(self):
        # The table frame owns its request size, so fitting a name column
        # cannot grow the results pane and squeeze the event log away.
        if not self.results_tree.winfo_exists():return
        columns=self.results_tree['displaycolumns']
        fixed=sum(self.results_tree.column(key,'width') for key in columns if key!='name')
        width=max(155,self.results_tree.winfo_width()-fixed-2)
        if self.results_tree.column('name','width')!=width:
            self.results_tree.column('name',width=width)

    def _empty_results(self):
        self.results_tree.tag_configure('hint',foreground=self.palette['muted'])
        self.results_tree.insert('','end',tags=('hint',),values=('','',self.tr('Рассчитайте гонку')))

    def _explain_results(self):
        example=self.tr('Например: 1:29.9 означает 1 минуту 29,9 секунды.')
        correction=self.tr('Внутреннее время умножается на 1,18. Если результат выходит за пороги трассы, для табло выбирается время около соответствующего порога. При одинаковом seed выбор повторяется. Эта поправка не меняет расстановку мест.')
        if self.result:
            winner=min(range(len(self.result.runners)),key=lambda i:(self.result.finish_times[i],i))
            board=self.result.display_finish_times[winner] if self.result.display_finish_times else None
            if board is not None:
                example=self.tr('Этот прогон: {p0} — {p1} ({p2:.3f} с). До поправки табло: {p3:.4f} с.', p0=self.result.runners[winner]['name'], p1=format_board_time(board), p2=board, p3=self.result.scaled_finish_times[winner])
                clock=self.result.display_clock
                if clock.get('correction') in ('lower','upper'):
                    bound=clock['bounds']['min' if clock['correction']=='lower' else 'max']
                    low=bound['seconds']-bound['random_range_seconds']
                    high=bound['seconds']+bound['random_range_seconds']
                    correction+=self.tr('\nВ этом прогоне использован диапазон {p0:.3f}–{p1:.3f} с из параметров трассы.', p0=low, p1=high)
        messagebox.showinfo(self.tr('Как читать результаты'),
            self.tr('Время победителя*\n')+example+'\n'+correction+self.tr('\nОстальным абсолютное время табло пока не назначается.\n\nОт предыдущей\nКаждая строка сравнивается со строкой выше. Если у 3-го места Nose, оно отстало от 2-го на нос. L — корпус; 1 1/2 L — полтора корпуса. Distance — больше 10 корпусов.\n\nТочность\nНазвания и коэффициент 15 прочитаны из файлов игры. Пороги категорий и округление ещё требуют проверки, поэтому подписи отмечены ≈. Разрывы считаются до случайной поправки табло.\n\nРасчётные времена\nФлажок открывает время ×1,18 и два разрыва в секундах: к предыдущей и к победителю. Счётчик повтора показывает внутреннее время симуляции.'), parent=self.root)

    def _toggle_play(self):
        if self.result and not self.busy:
            if self.playhead >= self.frame_times[-1]:
                self._rewind()
            self.playing = not self.playing
            self.last_clock = time.perf_counter()
            self.play_button.configure(text=self.tr('Пауза') if self.playing else self.tr('Воспроизвести'))

    def _rewind(self):
        self.playing = False
        self.playhead = 0.
        self.seek.set(0)
        self.play_button.configure(text=self.tr('Воспроизвести'))
        self._draw()

    def _seek_to(self, value):
        if not getattr(self, "updating_seek", False):
            self.playhead = float(value)
            self._draw()

    def _animate(self):
        now = time.perf_counter()
        elapsed = min(.1, now - self.last_clock)
        self.last_clock = now
        if self.playing and self.result:
            self.playhead = min(self.frame_times[-1], self.playhead + elapsed * int(self.play_speed.get().rstrip("×")))
            if self.playhead >= self.frame_times[-1]:
                self.playing = False
                self.play_button.configure(text=self.tr('Воспроизвести'))
            self.updating_seek = True
            self.seek.set(self.playhead)
            self.updating_seek = False
            self._draw()
        self.root.after(30, self._animate)

    def _skill_status(self,skill):
        if not skill:return False,self.tr('Нет записи')
        report=self.skill_audit.get(skill['id'])
        if not self.audit_ready:return False,self.tr('Аудит недоступен')
        if report and (report.get('droppedEffects') or report.get('fullyUnmodeled')):
            return False,self.tr('Сценарный эффект / вне модели') if skill['id'] in (1000011,1000012) else self.tr('Есть эффекты вне модели')
        if any('семантика приближена' in s for s in fidelity_issues(skill)):
            return True,self.tr('Условие приближено')
        return True,self.tr('В расчёте · нужна сверка')

    def _preview_course(self,_=None):
        if _ is not None and self.result and self.course_labels.get(self.course_var.get())!=self.result.course['id']:
            self.playing=False;self.result=None;self.frame_times=[]
            self.play_button.configure(state='disabled',text=self.tr('Воспроизвести'));self.export_button.configure(state='disabled')
            self.results_tree.delete(*self.results_tree.get_children());self._empty_results();self.event_list.delete(0,'end')
        if self.result:return
        if self.data and hasattr(self,'course_labels'):
            try:
                course=self.data.course(self.course_labels[self.course_var.get()])
                self.track_views.update_race(course)
            except (ValueError,KeyError) as e:
                self.track_views.update_race(None)
                self.notice.set(self.tr.dynamic(str(e)))

    def _race_options(self):
        window=tk.Toplevel(self.root);window.title(self.tr('Дополнительные условия гонки'))
        window.transient(self.root)
        window.grab_set();window.bind('<Escape>',lambda _:window.destroy())
        panel=ttk.Frame(window,padding=20);panel.pack(fill='both',expand=True)
        time_var=tk.StringVar(value=str(self.time_of_day));grade_var=tk.StringVar(value=str(self.race_grade))
        ttk.Label(panel,text=self.tr('Код времени суток (0–5 из master)')).grid(row=0,column=0,sticky='w',pady=8)
        ttk.Combobox(panel,textvariable=time_var,values=list(range(6)),state='readonly',width=10).grid(row=0,column=1)
        ttk.Label(panel,text=self.tr('Класс гонки (100 = G1; 200 = G2; 300 = G3)')).grid(row=1,column=0,sticky='w',pady=8)
        ttk.Combobox(panel,textvariable=grade_var,values=[100,200,300,400,500,600,700,800],state='readonly',width=10).grid(row=1,column=1)
        def apply():
            self.time_of_day=int(time_var.get());self.race_grade=int(grade_var.get());window.destroy()
        ttk.Button(panel,text=self.tr('Отмена'),command=window.destroy).grid(row=2,column=0,pady=12,sticky='e')
        ttk.Button(panel,text=self.tr('Применить'),command=apply).grid(row=2,column=1,pady=12)

    def _advanced_runner(self):
        try:self._commit_runner()
        except ValueError as e:return self._error(e)
        runner=self.runners[self.active_runner]
        window=tk.Toplevel(self.root);window.title(self.tr('Параметры навыков'));window.transient(self.root)
        window.grab_set();window.bind('<Escape>',lambda _:window.destroy())
        panel=ttk.Frame(window,padding=20);panel.pack(fill='both',expand=True)
        labels={'popularity':self.tr('Популярность (1–18)'),'team':self.tr('Команда (0 = нет команды)'),'career_wins':self.tr('Победы в карьере'),'fan_count':self.tr('Поклонники'),**{'aoharu_'+k:self.tr('Aoharu: сумма ')+self.stat_labels[k] for k in STATS}}
        variables={k:tk.StringVar(value=str(getattr(runner,k))) for k in labels}
        for row,(key,label) in enumerate(labels.items()):
            ttk.Label(panel,text=label).grid(row=row,column=0,sticky='w',pady=4)
            ttk.Entry(panel,textvariable=variables[key],width=16).grid(row=row,column=1,pady=4)
        def apply():
            try:
                values={k:int(v.get()) for k,v in variables.items()}
                updated=replace(runner,**values);updated.validate()
                self.runners[self.active_runner]=updated;self._autosave();window.destroy()
            except (ValueError,OSError) as e:self._error(e)
        ttk.Button(panel,text=self.tr('Отмена'),command=window.destroy).grid(row=len(labels),column=0,pady=15,sticky='e')
        ttk.Button(panel,text=self.tr('Применить'),style='Primary.TButton',command=apply).grid(row=len(labels),column=1,pady=15)

    def _draw(self):
        if not hasattr(self,'track_views'):return
        if not self.result:
            self._preview_course()
            return
        i=max(0,bisect.bisect_right(self.frame_times,self.playhead)-1)
        frame=self.result.frames[i]
        nextframe=self.result.frames[min(i+1,len(self.frame_times)-1)]
        span=nextframe['time']-frame['time']
        alpha=max(0,min(1,(self.playhead-frame['time'])/span)) if span else 0
        states=[{**state,'distance':state['distance']+alpha*(nextframe['runners'][j]['distance']-state['distance'])} for j,state in enumerate(frame['runners'])]
        spurts=[(e['runner'],e['distance']) for e in self.result.events if e['kind']=='last-spurt' and e['runner']==0 and e['time']<=self.playhead]
        self.track_views.update_race(self.result.course,states,spurts)
        self.clock.set(self.tr('{p0:.1f} / {p1:.1f} с · расчёт', p0=self.playhead, p1=self.frame_times[-1]))
        visible=[e for e in self.result.events if e['time']<=self.playhead]
        if len(visible)!=self.last_event_count:
            self.event_list.delete(0,'end')
            for event in visible:
                name=self.result.runners[event['runner']]['name']
                self.event_list.insert('end',self.tr('{p0:6.1f} с · {p1} · {p2}', p0=event['time'], p1=name, p2=self.tr.dynamic(self.tr({'overtake-start':'Обгон начат','overtake-end':'Обгон завершён','debuff-applied':'Дебафф применён'}.get(event['kind'],event['text'])))))
            self.event_list.see('end');self.last_event_count=len(visible)

    def _export(self):
        if not self.result:
            return
        path = filedialog.asksaveasfilename(title=self.tr('Экспорт прогона'), initialdir=str(self.local), initialfile=f"race-{datetime.now():%Y%m%d-%H%M%S}.json", defaultextension=".json", filetypes=[("JSON", "*.json")], parent=self.root)
        if path:
            try:
                Path(path).write_text(json.dumps(self.result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
                self.notice.set(self.tr('Экспортирован воспроизводимый прогон: ') + path)
            except OSError as e:
                self._error(e)

    def _error(self, e):
        messagebox.showerror("Uma Race Lab", self.tr.dynamic(str(e)), parent=self.root)

    def _close(self):
        try:
            self._commit_runner()
            self._autosave()
        except (ValueError, OSError) as e:
            if not messagebox.askyesno(self.tr('Закрыть без сохранения?'), self.tr.dynamic(str(e)) + self.tr('\n\nЗакрыть приложение без сохранения этих изменений?'), parent=self.root):
                return
        self.root.destroy()


def main():
    root = tk.Tk()
    RaceLab(root)
    root.mainloop()
