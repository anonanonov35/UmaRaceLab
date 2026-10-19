"""Two synchronized views of the actual, distance-sampled local course path."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from .courses import phase_marks,position_at,segment_at,world_position_at
from .i18n import Translator
from .theme import get_palette

class TrackViews(ttk.Frame):
    def __init__(self,parent,translator=None,palette=None):
        super().__init__(parent)
        self.tr=translator or Translator()
        self.palette=(palette or get_palette()).copy()
        self.course=None
        self.states=[]
        self.spurts=[]
        self.top=tk.Canvas(self,bg=self.palette['surface'],height=280,highlightthickness=1,highlightbackground=self.palette['border'])
        self.profile=tk.Canvas(self,bg=self.palette['surface'],height=280,highlightthickness=1,highlightbackground=self.palette['border'])
        self.top.grid(row=0,column=0,sticky='nsew',padx=(0,10))
        self.profile.grid(row=0,column=1,sticky='nsew')
        self.columnconfigure(0,weight=1,uniform='views')
        self.columnconfigure(1,weight=1,uniform='views')
        self.rowconfigure(0,weight=1)
        self.detail=tk.StringVar(value=self.tr('Наведите указатель на схему: дистанция, поворот, высота и уклон.'))
        ttk.Label(self,textvariable=self.detail,font=('Segoe UI',9)).grid(row=1,column=0,columnspan=2,sticky='w',pady=(5,0))
        for canvas in (self.top,self.profile):
            canvas.bind('<Configure>',lambda _:self.draw())
        self.top.bind('<Motion>',self._hover_top)
        self.profile.bind('<Motion>',self._hover_profile)

    def update_race(self,course,states=(),spurts=()):
        self.course=course
        self.states=states
        self.spurts=spurts
        self.draw()

    def _text(self,c,x,y,text,**kwargs):
        return c.create_text(x,y,text=text,fill=self.palette['ink'],font=('Segoe UI',8),**kwargs)

    def _top_transform(self):
        points=self.course['geometry']['points']
        xs,zs=[p[0] for p in points],[p[1] for p in points]
        lo,hi,bottom,top=min(xs),max(xs),min(zs),max(zs)
        w,h=self.top.winfo_width(),self.top.winfo_height()
        scale=min((w-110)/max(1,hi-lo),(h-105)/max(1,top-bottom))
        return lambda x,z:(w/2+(x-(hi+lo)/2)*scale,h/2+23-(z-(top+bottom)/2)*scale),scale

    def _profile_transform(self):
        w,h=self.profile.winfo_width(),self.profile.winfo_height()
        elevations=[p[2] for p in self.course['geometry']['points']]
        lo,hi=min(elevations),max(elevations)
        span=max(1.,hi-lo)
        return lambda d,e:(42+(w-66)*d/self.course['distance'],h-55-(h-140)*(e-lo)/span),lo,hi

    def draw(self):
        for c,title in [(self.top,self.tr('ТРАССА СВЕРХУ')),(self.profile,self.tr('ПРОФИЛЬ ВЫСОТ'))]:
            c.delete('all')
            self._text(c,14,14,title,anchor='nw')
        if not self.course or not self.course.get('geometry'):
            for c in (self.top,self.profile):
                self._text(c,20,90,self.tr('Нет проверенной геометрии этой трассы'),anchor='w')
            return
        if min(self.top.winfo_width(),self.profile.winfo_width())<100:return
        course=self.course;g=course['geometry'];D=course['distance']
        t,scale=self._top_transform()
        p,lo,hi=self._profile_transform()
        phases=phase_marks(D)
        # Each legend also gives the exact boundaries, including tracks with
        # repeated laps whose segments overlap in the top projection.
        for c in (self.top,self.profile):
            width=c.winfo_width()
            for i,(name,start,end) in enumerate(phases):
                x=12+i*(width-24)/4
                c.create_line(x,40,x+12,40,fill=self.palette['phase_colors'][i],width=4)
                phase={'early race':'Начало','mid race':'Середина','late race':'Конец','last spurt':'Финишная фаза'}[name]
                self._text(c,x+17,35,self.tr(phase),anchor='nw')
                self._text(c,x+17,50,self.tr('{p0:.0f}–{p1:.0f} м', p0=start, p1=end),anchor='nw')
        allcoords=[a for x,z,_ in g['points'] for a in t(x,z)]
        self.top.create_line(*allcoords,fill=self.palette['road'],width=24,capstyle='round',joinstyle='round')
        for i,(name,start,end) in enumerate(phases):
            ds=[start]+[j*D/(len(g['points'])-1) for j in range(len(g['points'])) if start<j*D/(len(g['points'])-1)<end]+[end]
            coords=[a for d in ds for a in t(*position_at(g,d)[:2])]
            self.top.create_line(*coords,fill=self.palette['phase_colors'][i],width=9,capstyle='round',joinstyle='round')
            x,y=t(*position_at(g,start)[:2])
            self.top.create_oval(x-4,y-4,x+4,y+4,fill=self.palette['surface'],outline=self.palette['phase_colors'][i],width=2)
        for n,corner in enumerate(g['corners']):
            middle=corner['start']+corner['length']/2
            x,y=t(*position_at(g,middle)[:2])
            center_x,center_y=t(sum(q[0] for q in g['points'])/len(g['points']),sum(q[1] for q in g['points'])/len(g['points']))
            shift=-20 if x<center_x else 20
            self._text(self.top,x+shift,y+(16 if y>center_y else -13),self.tr('C{p0} · {p1:.0f} м', p0=corner.get('number', n + 1), p1=corner['length']),anchor='e' if shift<0 else 'w')
        for d,label,offset in [(0.,self.tr('СТАРТ'),11),(D,self.tr('ФИНИШ'),-11)]:
            x,y=t(*position_at(g,d)[:2]);self.top.create_line(x-8,y-8,x+8,y+8,fill=self.palette['ink'],width=2)
            self._text(self.top,x+offset,y+24,label,anchor='e' if offset<0 else 'w')
        self._text(self.top,12,self.top.winfo_height()-10,self.tr('Контур из CourseLaneAnim · длины поворотов из courseParams'),anchor='sw')
        # Distance is linear; elevation is true metres with an explicit vertical
        # exaggeration. Slope intervals use gameplay events rather than a noisy
        # derivative of the visual lane animation.
        for i,(_,start,end) in enumerate(phases):
            x1,_=p(start,lo);x2,_=p(end,lo)
            self.profile.create_rectangle(x1,73,x2,82,fill=self.palette['phase_colors'][i],outline='')
            self.profile.create_line(x1,82,x1,self.profile.winfo_height()-50,fill=self.palette['grid'],dash=(2,4))
        for slope in g['slopes']:
            start,end=slope['start'],min(D,slope['start']+slope['length'])
            x1,_=p(start,lo);x2,_=p(end,lo)
            color=self.palette['uphill'] if slope['slope']>0 else self.palette['downhill']
            self.profile.create_rectangle(x1,85,x2,self.profile.winfo_height()-55,fill=color,outline='')
            if x2-x1>18:
                self._text(self.profile,(x1+x2)/2,90,f"{slope['slope']/10000:+g}%",anchor='n')
        profile=[a for j,point in enumerate(g['points']) for a in p(D*j/(len(g['points'])-1),point[2])]
        self.profile.create_line(*profile,fill=self.palette['ink'],width=3,joinstyle='round')
        for corner in g['corners']:
            x1,_=p(corner['start'],lo);x2,_=p(corner['start']+corner['length'],lo)
            y=self.profile.winfo_height()-39
            self.profile.create_line(x1,y,x2,y,fill=self.palette['corner'],width=5)
            if x2-x1>18:self._text(self.profile,(x1+x2)/2,y+3,f"C{corner.get('number','')}",anchor='n')
        for j in range(5):
            d=j*D/4;x,_=p(d,lo)
            self._text(self.profile,x,self.profile.winfo_height()-8,f'{d:.0f}',anchor='s')
        self._text(self.profile,8,105,self.tr('{p0:.1f} м', p0=hi),anchor='nw')
        self._text(self.profile,8,self.profile.winfo_height()-58,self.tr('{p0:.1f} м', p0=lo),anchor='sw')
        self._text(self.profile,self.profile.winfo_width()-12,14,self.tr('Высота: масштаб увеличен'),anchor='ne')
        for i,state in enumerate(self.states):
            d=min(D,max(0,state['distance']))
            x,z,e=world_position_at(g,d,state.get('lane',0),course['turn'])
            sx,sy=t(x,z)
            px,py=p(d,e)
            color=self.palette['runner_colors'][i%len(self.palette['runner_colors'])]
            for c,cx,cy in [(self.top,sx,sy),(self.profile,px,py-10-(i%3)*9)]:
                c.create_oval(cx-7,cy-7,cx+7,cy+7,fill=color,outline=self.palette['runner_ink'],width=1)
                c.create_text(cx,cy,text=str(i+1),fill=self.palette['runner_ink'],font=('Segoe UI Semibold',7))
        if self.spurts:
            # First build is the reference; every runner's actual transition is
            # also exported and recorded in the event list.
            d=self.spurts[0][1];x,_=p(d,lo)
            self.profile.create_line(x,80,x,self.profile.winfo_height()-48,fill=self.palette['spurt'],dash=(5,3),width=2)
            tx,ty=t(*position_at(g,d)[:2]);self.top.create_oval(tx-11,ty-11,tx+11,ty+11,outline=self.palette['spurt'],width=2)

    def _describe(self,d):
        if not self.course:return
        g=self.course['geometry'];d=max(0,min(self.course['distance'],d))
        corner=segment_at(g['corners'],d);slope=segment_at(g['slopes'],d)
        parts=[self.tr('{p0:.1f} м', p0=d),self.tr('высота {p0:.2f} м', p0=position_at(g, d)[2])]
        parts.append(self.tr('поворот C{p0} ({p1:g}–{p2:g} м; длина {p3:g} м)', p0=corner.get('number', ''), p1=corner['start'], p2=corner['start'] + corner['length'], p3=corner['length']) if corner else self.tr('прямая'))
        parts.append(self.tr('уклон {p0:+g}%', p0=slope['slope'] / 10000) if slope else self.tr('без игрового уклона'))
        self.detail.set(' · '.join(parts))

    def _hover_profile(self,event):
        if self.course and self.course.get('geometry'):
            self._describe((event.x-42)/max(1,self.profile.winfo_width()-66)*self.course['distance'])

    def _hover_top(self,event):
        if not self.course or not self.course.get('geometry'):return
        t,_=self._top_transform();points=self.course['geometry']['points']
        index=min(range(len(points)),key=lambda i:(t(*points[i][:2])[0]-event.x)**2+(t(*points[i][:2])[1]-event.y)**2)
        self._describe(index/(len(points)-1)*self.course['distance'])
