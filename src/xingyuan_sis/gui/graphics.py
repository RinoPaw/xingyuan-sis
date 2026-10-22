"""Static cut-paper composition; native controls retain interaction and keyboard semantics."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, font as tkfont
from .theme import app_root, palette
from .typography import font_tuple, fitted_font
from .vector import VectorCanvas


def px(root, value):
    scale = float(root.tk.call('tk', 'scaling')) / (96/72)
    return round(value * scale * getattr(app_root(root), 'campus_zoom', 1.0))


def beast_emblem(canvas, x, y, size, *, ink, paper, cut):
    """Campus mark: angular ears, cheek ruff, split muzzle; not a student portrait."""
    def polygon(points, fill):
        coords = [v for a, b in points for v in (x+a*size/100, y+b*size/100)]
        canvas.create_polygon(*coords, fill=fill, outline='', tags='emblem')
    polygon([(4,0),(31,18),(50,12),(69,18),(96,0),(87,40),(99,58),
             (79,65),(85,76),(64,82),(50,100),(36,82),(15,76),(21,65),(1,58),(13,40)], paper)
    polygon([(9,5),(35,27),(50,19),(65,27),(91,5),(80,43),(91,56),
             (69,61),(76,72),(58,77),(50,92),(42,77),(24,72),(31,61),(9,56),(20,43)], ink)
    polygon([(15,15),(29,31),(20,35)], cut)
    polygon([(85,15),(71,31),(80,35)], cut)
    polygon([(20,44),(43,49),(37,56),(24,52)], paper)
    polygon([(80,44),(57,49),(63,56),(76,52)], paper)
    polygon([(50,45),(39,67),(50,82),(61,67)], paper)
    polygon([(42,65),(58,65),(50,72)], ink)
    polygon([(49,74),(51,74),(51,85),(49,85)], ink)


class CutNavigation(ttk.Frame):
    def __init__(self, parent, number, label, command):
        super().__init__(parent, style='Rail.TFrame', height=px(parent,58), width=px(parent,206))
        self.pack_propagate(False)
        self.selected, self.index = False, number
        self.canvas = VectorCanvas(self, highlightthickness=0, background=palette(self).rail)
        self.canvas.place(relwidth=1, relheight=1)
        self.button = ttk.Button(self,text=label,command=command,style='CutNav.TButton',takefocus=True)
        self.button.place(x=px(self,45),y=px(self,12),width=px(self,148),height=px(self,35))
        self.canvas.bind('<Button-1>',lambda e:self.button.invoke())
        self.canvas.bind('<Configure>',self.draw)
        self.button.bind('<FocusIn>',self.draw,add='+')
        self.button.bind('<FocusOut>',self.draw,add='+')
        self.button.bind('<Configure>',self.draw,add='+')
        def hover(active):
            self.button.state(['active' if active else '!active'])
            self.draw()
        for target in (self.canvas,self.button):
            target.bind('<Enter>',lambda e:hover(True),add='+')
            target.bind('<Leave>',lambda e:hover(False),add='+')

    def set_selected(self,selected):
        if self.selected == selected:
            return
        self.selected=selected
        self.button.configure(style='CutSelected.TButton' if selected else 'CutNav.TButton')
        self.draw()

    def draw(self,event=None):
        c,p=self.canvas,palette(self)
        w,h=c.winfo_width(),c.winfo_height()
        c.delete('all')
        bg,fg=(p.paper,p.ink) if self.selected else (p.ink,p.paper)
        if not self.selected and (self.button.instate(['active']) or self.button.instate(['focus'])):
            bg=p.rail_hover
        offset=px(self,7 if self.index%2 else 2)
        if self.selected:
            c.create_polygon(0,h*.25,w-9,0,w,h*.80,7,h,fill=p.ink,outline='')
        c.create_polygon(offset,h*.14,w-10,h*.05,w-3,h*.88,offset+3,h*.96,fill=bg,outline='')
        # Different faces have different ascenders/descenders. Align their
        # baselines, not their top-left font boxes, at every DPI and zoom.
        label_face = tkfont.Font(root=self, font=ttk.Style(self).lookup(self.button.cget('style'), 'font'))
        number_font = font_tuple(self, 'latin', 26)
        number_face = tkfont.Font(root=self, font=number_font)
        baseline = self.button.winfo_y() + (self.button.winfo_height()-label_face.metrics('linespace'))//2 + label_face.metrics('ascent')
        c.create_text(px(self,10),baseline-number_face.metrics('ascent'),text=f'{self.index:02}',font=number_font,
            fill=fg,anchor='nw',tags='nav-number')
        c.render()


class Brandmark(ttk.Frame):
    def __init__(self,parent):
        super().__init__(parent,style='Rail.TFrame',height=px(parent,116),width=px(parent,216))
        self.pack_propagate(False)
        art=VectorCanvas(self,background=palette(self).rail,highlightthickness=0)
        art.place(relwidth=1,relheight=1)
        def draw(event):
            art.delete('all')
            art.create_polygon(4,px(self,18),event.width-16,0,event.width,px(self,108),13,px(self,116),
                fill=palette(self).paper,outline='')
            art.create_text(px(self,22),px(self,24),text='星原',font=font_tuple(self,'display',43),
                fill=palette(self).ink,anchor='nw',tags='brand-name')
            art.render()
        art.bind('<Configure>',draw)


class ChapterHeading(ttk.Frame):
    """One functional title on an oblique sheet, alongside native action buttons."""
    def __init__(self,parent,title):
        super().__init__(parent,style='Stage.TFrame',height=px(parent,102))
        self.grid_propagate(False)
        self.columnconfigure(0,weight=1)
        self.rowconfigure(0,weight=1)
        art=VectorCanvas(self,background=palette(self).stage,highlightthickness=0)
        art.place(relwidth=1,relheight=1)
        self.title=title
        def draw(event):
            p=palette(self);art.delete('all')
            w,h=event.width,event.height
            art.create_polygon(0,h*.13,w*.69,0,w*.66,h*.90,12,h,fill=p.ink,outline='')
            art.create_polygon(w*.68,0,w*.69,0,w*.66,h*.90,w*.65,h*.90,fill=p.paper,outline='')
            actions=[c for c in self.winfo_children() if isinstance(c,ttk.Button)]
            action_width=sum(c.winfo_reqwidth()+px(self,8) for c in actions)
            compact=w < px(self,640)
            stacked=bool(actions) and w-action_width < px(self,180)
            height = px(self, 102 if stacked or not compact else 64)
            # Configure callbacks fire while Tk settles geometry. Reassigning
            # unchanged frame dimensions and grid options can provoke additional
            # geometry passes even when nothing on screen needs to move.
            if int(self.cget('height')) != height:
                self.configure(height=height)
            target_row = 1 if stacked else 0
            for control in actions:
                if int(control.grid_info()['row']) != target_row:
                    control.grid_configure(row=target_row)
            width=w-px(self,52) if stacked else w-action_width-px(self,52)
            width=min(width,w*.65-px(self,36))
            art.create_text(px(self,18),h*.49,text=title,anchor='w',fill=p.paper,
                font=fitted_font(self,'display',24 if compact else 35,title,max(1,width)),tags='page-title')
            art.render()
        art.bind('<Configure>',draw)


class CampusSeal(VectorCanvas):
    def __init__(self,parent):
        super().__init__(parent,background=palette(parent).stage,highlightthickness=0,width=1,height=1)
        self.bind('<Configure>',self.draw)

    def draw(self,event=None):
        p=palette(self);w,h=self.winfo_width(),self.winfo_height();self.delete('all')
        self.create_polygon(0,h*.08,w*.93,0,w,h*.86,w*.13,h,fill=p.ink,outline='')
        size=min(w*.86,h*.86)
        beast_emblem(self,(w-size)/2,(h-size)/2,size,ink=p.ink,paper=p.paper,cut=p.stage)
        self.render()


class RecordBanner(ttk.Frame):
    def __init__(self,parent,name,number,kin,element=None,affinity=None):
        super().__init__(parent,style='Stage.TFrame',height=px(parent,204))
        self.grid_propagate(False)
        self.art=VectorCanvas(self,background=palette(self).stage,highlightthickness=0)
        self.art.place(relwidth=1,relheight=1)
        self.name_text=str(name)
        self.number_text, self.kin_text = number, kin
        self.element_text = f'{element} / {affinity or "—"}' if element else ''
        self.art.bind('<Configure>',self._draw)

    def _draw(self,event=None):
        c,p=self.art,palette(self);w,h=c.winfo_width(),c.winfo_height();c.delete('all')
        size=min(px(self,148),w*.46)
        beast_emblem(c,w-size-px(self,6),-px(self,10),size,ink=p.ink,paper=p.paper,cut=p.stage)
        c.create_polygon(0,h*.54,w-8,h*.49,w,h*.81,8,h*.86,fill=p.paper,outline='')
        c.create_text(px(self,18),px(self,16),text=self.number_text,fill=p.on_stage,
            font=font_tuple(self,'latin',24),anchor='nw',tags='banner-number')
        c.create_text(px(self,18),px(self,134),text=self.name_text,fill=p.ink,
            font=fitted_font(self,'display',32,self.name_text,w-px(self,36)),anchor='w',tags='banner-name')
        c.create_text(px(self,18),px(self,174),text=self.kin_text,fill=p.on_stage,
            font=font_tuple(self,'body',10),anchor='nw',width=max(1,w-px(self,36)),tags='banner-kin')
        if self.element_text:
            c.create_text(px(self,18),px(self,60),text=self.element_text,fill=p.on_stage,
                font=font_tuple(self,'body',18,bold=True),anchor='nw',tags='badge')
        c.render()


class ScoreSlip(ttk.Frame):
    def __init__(self,parent,row):
        super().__init__(parent,style='Surface.TFrame')
        self.columnconfigure(0,weight=1)
        name=row.get('student_name') or row.get('student_no') or ''
        course=row.get('course_name') or row.get('course_code') or ''
        ttk.Label(self,text=name,style='InspectorTitle.TLabel').grid(row=0,column=0,sticky='w')
        label=ttk.Label(self,text=course,style='CourseName.TLabel')
        label.grid(row=1,column=0,sticky='w',pady=(3,8))
        ttk.Label(self,text=f"{row.get('student_no','')}  /  {row.get('semester','')}",style='SurfaceMuted.TLabel').grid(row=2,column=0,sticky='w')
        value=row.get('score')
        score='待录入' if value is None else f'{value:g}' if isinstance(value,(int,float)) else str(value)
        ttk.Label(self,text=score,style='Score.TLabel' if value is not None else 'CourseName.TLabel').grid(row=0,column=1,rowspan=3,sticky='e',padx=(px(self,24),0))
        self.bind('<Configure>',lambda e:label.configure(wraplength=max(px(self,120),e.width-px(self,170))))


class NoticeHeading(ttk.Frame):
    def __init__(self,parent,row):
        super().__init__(parent,style='Surface.TFrame')
        self.columnconfigure(0,weight=1)
        ttk.Label(self,text=f"{row.get('class_name') or '班级公告'}  /  {str(row.get('created_at',''))[:10]}",style='SurfaceMuted.TLabel').grid(row=0,column=0,sticky='w')
        title=ttk.Label(self,text=row.get('title',''),style='NoticeTitle.TLabel')
        title.grid(row=1,column=0,sticky='ew',pady=(px(self,12),px(self,16)))
        self.bind('<Configure>',lambda e:title.configure(wraplength=max(1,e.width)))
