"""Semantic colors and control states. Rationale: docs/gui-control-decisions.md."""
from __future__ import annotations
from dataclasses import dataclass
import tkinter as tk
from tkinter import font as tkfont, ttk
from .typography import configure_fonts, font_tuple
from .interaction import install_wheel_policy


@dataclass(frozen=True)
class Palette:
    background: str
    surface: str
    text: str
    muted: str
    border: str
    control_border: str
    accent: str
    accent_hover: str
    accent_pressed: str
    on_accent: str
    selection: str
    selected_text: str
    error: str
    success: str
    hover: str
    pressed: str
    disabled_background: str
    disabled_text: str
    rail: str
    rail_text: str
    rail_muted: str
    rail_hover: str
    header: str
    header_text: str
    row_alt: str
    stage: str
    on_stage: str
    ink: str
    paper: str
    roster_alt: str


# Red is the compositional stage, distinct from form and reading surfaces.
# Borders which identify inputs use control_border; structural dividers use border.
PALETTES = {
    "rebel": Palette(
        background="#f2efe8", surface="#fffdf8", text="#242127", muted="#655e65",
        border="#c6bdb8", control_border="#8b7e81", accent="#b51f36",
        accent_hover="#95182c", accent_pressed="#751124", on_accent="#fffdf8",
        selection="#26232b", selected_text="#fffdf8", error="#a31c32", success="#246346",
        hover="#e8e2da", pressed="#d9d1c9", disabled_background="#e4ded8", disabled_text="#685e65",
        rail="#cd1233", rail_text="#fffdf6", rail_muted="#fffdf6", rail_hover="#312d37",
        header="#111014", header_text="#fffdf6", row_alt="#f4f0e9",
        stage="#cd1233", on_stage="#fffdf6", ink="#111014", paper="#fffdf6", roster_alt="#211e25"),
    "afterhours": Palette(
        background="#201e24", surface="#29262e", text="#f4efe7", muted="#c0b6c0",
        border="#5e5663", control_border="#8d8191", accent="#ed8797",
        accent_hover="#f7a1af", accent_pressed="#ffc0cb", on_accent="#28131a",
        selection="#eadfe6", selected_text="#231d27", error="#ff9bac", success="#9ed7b5",
        hover="#3a3540", pressed="#49414e", disabled_background="#36313a", disabled_text="#a89aa8",
        rail="#99112b", rail_text="#fffdf6", rail_muted="#fffdf6", rail_hover="#302936",
        header="#17151b", header_text="#f4efe7", row_alt="#302c35",
        stage="#99112b", on_stage="#fffdf6", ink="#111014", paper="#fffdf6", roster_alt="#211e25"),
}


def app_root(widget):
    while widget.master is not None:
        widget = widget.master
    return widget


def palette(root: tk.Misc) -> Palette:
    return PALETTES[getattr(app_root(root), "campus_theme", "rebel")]


def _flat_surfaces(root, style, size):
    """Solid ttk elements without Clam's hard-coded one-pixel edge strokes.

    Tiny solid tiles stretch inside the native element layout. Widgets retain
    their built-in input, selection, accessibility and keyboard behaviour.
    Keep image objects alive and recolour them when the theme changes.
    """
    images = getattr(root, "campus_flat_images", {})
    root.campus_flat_images = images
    def element(name, states, *, width=2, height=2, arrow=False):
        names = []
        for index, (state, color) in enumerate(states):
            key = (name, index)
            if key not in images:
                images[key] = tk.PhotoImage(master=root, width=width, height=height)
            image = images[key]
            image.configure(width=width, height=height)
            image.blank()
            if arrow:
                for y in range(4):
                    left = (width-7)//2+y
                    image.put(color, to=(left, (height-4)//2+y, left+7-2*y, (height-4)//2+y+1))
            else:
                image.put(color, to=(0, 0, width, height))
            names.append((state, image))
        if name not in style.element_names():
            style.element_create(name, "image", names[-1][1],
                *((state, image) for state, image in names[:-1]), border=0, sticky="" if arrow else "nswe")
        return name

    states = ("disabled", "pressed", "active", "focus", "selected", "")
    for name in ("TButton", "Accent.TButton", "Danger.TButton", "Nav.TButton", "TabSelected.TButton",
                 "CutNav.TButton", "CutSelected.TButton", "StageNav.TButton", "TEntry", "Read.TEntry", "TCombobox", "TNotebook.Tab"):
        colors = [(state, style.lookup(name, "background", (state,) if state else ())) for state in states]
        fill = element("Campus."+name+".fill", colors)
        if name.endswith("TButton"):
            children = [("Button.padding", {"sticky":"nswe", "children":[("Button.label", {"sticky":"nswe"})]})]
        elif name == "TNotebook.Tab":
            children = [("Notebook.padding", {"sticky":"nswe", "children":[("Notebook.label", {"sticky":"nswe"})]})]
        else:
            prefix = "Combobox" if name == "TCombobox" else "Entry"
            children = [(prefix+".padding", {"sticky":"nswe", "children":[(prefix+".textarea", {"sticky":"nswe"})]})]
            if name == "TCombobox":
                arrow = element("Campus.Combobox.downarrow", [(state, style.lookup(name,"foreground",(state,) if state else ())) for state in states],
                                width=size(20), height=size(14), arrow=True)
                children.insert(0, (arrow, {"side":"right", "sticky":""}))
        style.layout(name, [(fill, {"sticky":"nswe", "children":children})])
    for prefix, orientations in (("", ("Vertical", "Horizontal")), ("Ink.", ("Vertical", "Horizontal")), ("Rail.", ("Vertical",))):
        for orient in orientations:
            name = f"{prefix}{orient}.TScrollbar"
            track = element("Campus."+name+".trough", [("", style.lookup(name,"troughcolor"))])
            thumb = element("Campus."+name+".thumb", [(state, style.lookup(name,"background",(state,) if state else ())) for state in ("pressed","active","")],
                            width=size(8 if orient == "Vertical" else 24), height=size(24 if orient == "Vertical" else 8))
            style.layout(name, [(track, {"sticky":"nswe", "children":[(thumb,{"sticky":"nswe"})]})])


def configure_styles(root: tk.Misc, mode="rebel", zoom=1.0) -> ttk.Style:
    if mode not in PALETTES or zoom not in (1.0, 1.25, 1.5):
        raise ValueError("不支持的主题或字号")
    root.campus_theme, root.campus_zoom = mode, zoom
    p = PALETTES[mode]
    families = configure_fonts(root)
    family, display = families["body"], families["display"]
    size = lambda n: round(n * zoom)
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(name, root=root).configure(family=family, size=size(11))
    for option, value in {"background": p.surface, "foreground": p.text,
            "selectBackground": p.selection, "selectForeground": p.selected_text, "font": "TkDefaultFont"}.items():
        root.option_add(f"*TCombobox*Listbox.{option}", value)
    style = ttk.Style(root)
    style.theme_use("clam")
    install_wheel_policy(root)
    # Native interaction, flat paint: state is communicated by a filled surface,
    # not Clam's hairline borders or dotted focus rectangles.
    def without_focus(layout):
        result = []
        for element, options in layout:
            options = dict(options)
            children = without_focus(options.pop("children", []))
            if element.endswith((".focus", ".border", ".field", ".tab", ".client", ".cell")):
                result.extend(children)
            else:
                if children:
                    options["children"] = children
                result.append((element, options))
        return result
    for name in ("TButton", "TEntry", "TCombobox", "TNotebook", "TNotebook.Tab", "Treeview", "Treeview.Heading"):
        style.layout(name, without_focus(style.layout(name)))
    root.configure(background=p.background)
    style.configure(".", background=p.background, foreground=p.text, font="TkDefaultFont",
        bordercolor=p.border, lightcolor=p.border, darkcolor=p.border, focuscolor=p.accent,
        troughcolor=p.background)
    for name, color in (("App", p.background), ("Surface", p.surface), ("Rail", p.rail), ("Stage", p.stage), ("Ink", p.ink)):
        style.configure(f"{name}.TFrame", background=color)
    roles = {
        "Title": (p.ink, p.paper, display, 35, "normal"),
        "StageMeta": (p.stage, p.on_stage, family, 10, "normal"),
        "CourseName": (p.surface, p.text, display, 25, "normal"),
        "NoticeTitle": (p.surface, p.text, display, 32, "normal"),
        "Score": (p.surface, p.text, families["latin"], 62, "normal"),
        "SectionTitle": (p.background, p.text, family, 14, "bold"),
        "Body": (p.background, p.text, family, 11, "normal"),
        "Muted": (p.background, p.muted, family, 10, "normal"),
        "Surface": (p.surface, p.text, family, 11, "normal"),
        "SurfaceMuted": (p.surface, p.muted, family, 10, "normal"),
        "InspectorTitle": (p.surface, p.text, family, 14, "bold"),
        "LoginTitle": (p.surface, p.text, display, 23, "normal"),
        "Status": (p.surface, p.success, family, 10, "normal"),
        "Error": (p.surface, p.error, family, 10, "normal"),
        "RailTitle": (p.paper, p.ink, display, 43, "normal"),
        "RailMuted": (p.rail, p.rail_muted, family, 10, "normal"),
    }
    for name, (bg, fg, face, pt, weight) in roles.items():
        style.configure(f"{name}.TLabel", background=bg, foreground=fg, font=(face, size(pt), weight))

    # Every state sets a readable foreground/background pair, including hover.
    style.configure("TButton", padding=(size(12), size(7)), background=p.surface, foreground=p.text,
        borderwidth=0, relief="flat", bordercolor=p.control_border, lightcolor=p.control_border,
        darkcolor=p.control_border, focusthickness=0, focuscolor=p.accent)
    style.map("TButton", background=[("disabled", p.disabled_background), ("pressed", p.pressed), ("active", p.hover), ("focus", p.hover)],
        foreground=[("disabled", p.disabled_text), ("!disabled", p.text)],
        bordercolor=[("focus", p.accent), ("!focus", p.control_border)])
    style.configure("Accent.TButton", background=p.accent, foreground=p.on_accent,
        bordercolor=p.accent, focuscolor=p.on_accent, font=(family, size(11), "bold"))
    style.map("Accent.TButton", background=[("disabled", p.disabled_background), ("pressed", p.accent_pressed), ("active", p.accent_hover), ("focus", p.accent_hover)],
        foreground=[("disabled", p.disabled_text), ("!disabled", p.on_accent)],
        bordercolor=[("disabled", p.border), ("!disabled", p.accent)])
    style.configure("Nav.TButton", borderwidth=0, padding=(size(12), size(8)), background=p.background)
    style.map("Nav.TButton", background=[("active", p.hover), ("!active", p.background)])
    style.configure("TabSelected.TButton", background=p.selection, foreground=p.selected_text,
        font=(family, size(11), "bold"), borderwidth=0)
    style.map("TabSelected.TButton", background=[("active", p.selection), ("!active", p.selection)],
        foreground=[("active", p.selected_text), ("!active", p.selected_text)])
    style.configure("Danger.TButton", foreground=p.error)
    style.map("Danger.TButton", foreground=[("disabled", p.disabled_text), ("!disabled", p.error)])

    # Readonly still permits selecting/copying text. Disabled fields are visibly distinct.
    for name in ("TEntry", "TCombobox"):
        style.configure(name, fieldbackground=p.surface, background=p.surface, foreground=p.text,
            padding=size(7), insertcolor=p.text, borderwidth=0, relief="flat", bordercolor=p.background,
            lightcolor=p.background, darkcolor=p.background, arrowcolor=p.text, arrowsize=size(14))
        style.map(name, bordercolor=[("invalid", p.error), ("focus", p.accent), ("!focus", p.control_border)],
            background=[("disabled", p.disabled_background), ("focus", p.selection), ("!focus", p.surface)],
            fieldbackground=[("disabled", p.disabled_background), ("focus", p.selection), ("!focus", p.surface)],
            foreground=[("disabled", p.disabled_text), ("focus", p.selected_text), ("!focus", p.text)],
            insertcolor=[("focus", p.selected_text)], arrowcolor=[("focus", p.selected_text), ("!focus", p.text)],
            lightcolor=[("focus", p.selection), ("!focus", p.background)],
            darkcolor=[("focus", p.selection), ("!focus", p.background)],
            selectbackground=[("readonly", p.selection)], selectforeground=[("readonly", p.selected_text)])
    style.configure("Read.TEntry", padding=(4, 4), borderwidth=0, relief="flat",
        bordercolor=p.surface, lightcolor=p.surface, darkcolor=p.surface)
    # Clam's Entry.field still leaves corner pixels at borderwidth=0. Read-only
    # copyable values need text/selection, not an input-field border element.
    style.layout("Read.TEntry", [("Entry.padding", {"sticky":"nswe", "children":[
        ("Entry.textarea", {"sticky":"nswe"})]})])
    style.map("Read.TEntry", background=[("readonly",p.surface), ("!readonly",p.surface)],
        fieldbackground=[("readonly", p.surface)], foreground=[("readonly", p.text)],
        bordercolor=[("focus", p.accent), ("!focus", p.surface)])

    style.configure("Treeview", background=p.surface, fieldbackground=p.surface, foreground=p.text,
        rowheight=size(36), borderwidth=0, bordercolor=p.surface)
    style.configure("Treeview.Heading", background=p.header, foreground=p.header_text,
        font=(family, size(10), "bold"), padding=(size(8), size(9)), relief="flat")
    style.map("Treeview.Heading", background=[("active", p.rail_hover)], foreground=[("active", p.header_text)])
    style.map("Treeview", background=[("selected", p.selection)], foreground=[("selected", p.selected_text)],
        bordercolor=[("focus", p.accent), ("!focus", p.control_border)])
    style.configure("TNotebook", background=p.surface, borderwidth=0)
    style.configure("TNotebook.Tab", background=p.background, foreground=p.muted, borderwidth=0,
        shiftrelief=0, expand=(0, 0, 0, 0),
        padding=(size(12), size(8)), font=(family, size(10), "bold"))
    style.map("TNotebook.Tab", background=[("focus", p.hover), ("selected", p.surface), ("active", p.hover)],
        foreground=[("selected", p.text), ("active", p.text)],
        padding=[("selected", (size(12), size(8))), ("!selected", (size(12), size(8)))],
        expand=[("selected", (0, 0, 0, 0))],
        bordercolor=[("focus",p.accent), ("!focus",p.border)])
    style.configure("TSeparator", background=p.border)
    style.configure("TPanedwindow", background=p.border, sashwidth=size(8))
    for orient, sticky in (("Vertical","ns"),("Horizontal","we")):
        style.layout(f"{orient}.TScrollbar", [(f"{orient}.Scrollbar.trough", {"sticky":sticky,
            "children":[(f"{orient}.Scrollbar.thumb", {"sticky":"nswe"})]})])
    style.configure("TScrollbar", background=p.control_border, troughcolor=p.surface,
        bordercolor=p.surface, lightcolor=p.control_border, darkcolor=p.control_border,
        borderwidth=0, relief="flat", gripcount=0, width=size(8), arrowsize=size(8))
    style.map("TScrollbar", background=[("pressed", p.accent), ("active", p.muted)])
    for orient in ("Vertical", "Horizontal"):
        style.configure(f"Ink.{orient}.TScrollbar", troughcolor=p.ink, bordercolor=p.ink)
    style.configure("Rail.Vertical.TScrollbar", troughcolor=p.rail, background=p.ink,
        bordercolor=p.rail, lightcolor=p.ink, darkcolor=p.ink)
    style.map("Rail.Vertical.TScrollbar", background=[("active", p.rail_text), ("pressed", p.rail_text)])

    # Black chapter tickets reverse to paper when selected; red connects the whole stage.
    for name, bg, fg in (("CutNav", p.ink, p.paper), ("CutSelected", p.paper, p.ink)):
        style.configure(f"{name}.TButton", background=bg, foreground=fg, borderwidth=0,
            font=font_tuple(root, "display", 16), anchor="w", padding=(4, 2), focusthickness=0, focuscolor=fg)
        state_bg = p.paper if name == "CutSelected" else p.rail_hover
        style.map(f"{name}.TButton", background=[("active",state_bg), ("focus",state_bg), ("!focus",bg)],
            foreground=[("active", fg), ("!active", fg)])
    style.configure("Banner.TFrame", background=p.surface)
    style.configure("BannerName.TLabel", background=p.paper, foreground=p.ink,
        font=font_tuple(root, "display", 24))
    style.configure("BannerMeta.TLabel", background=p.stage, foreground=p.on_stage, font=(family, size(10)))
    style.configure("BannerNumber.TLabel", background=p.stage, foreground=p.on_stage,
        font=font_tuple(root, "latin", 24))
    style.configure("FormError.TLabel", background=p.background, foreground=p.error, font=(family, size(10), "bold"))
    style.configure("ElementBadge.TLabel", background=p.stage, foreground=p.on_stage, font=(family, size(18), "bold"))
    style.configure("Roster.Treeview", background=p.ink, fieldbackground=p.ink, foreground=p.paper,
        borderwidth=0, bordercolor=p.ink, rowheight=size(40))
    style.configure("Roster.Treeview.Heading", background=p.ink, foreground=p.paper,
        font=(family,size(10),"bold"), padding=(8,12))
    style.map("Roster.Treeview", background=[("selected",p.paper)],foreground=[("selected",p.ink)])
    style.configure("Stage.TPanedwindow", background=p.stage, sashwidth=size(14))
    style.configure("StageNav.TButton", background=p.ink, foreground=p.paper, borderwidth=0)
    style.map("StageNav.TButton",background=[("active",p.rail_hover)],foreground=[("!disabled",p.paper)])
    _flat_surfaces(root, style, size)
    return style


def text_options(root: tk.Misc) -> dict:
    p = palette(root)
    return dict(background=p.surface, foreground=p.text, insertbackground=p.text,
        selectbackground=p.selection, selectforeground=p.selected_text, relief="flat", borderwidth=0,
        highlightthickness=0, font="TkTextFont", padx=16, pady=12)


def install_icon(root: tk.Tk) -> None:
    image = tk.PhotoImage(master=root, width=32, height=32)
    image.put("#101014", to=(0, 0, 32, 32))
    for y in range(7, 25):
        x = 7 + abs(15-y)//2
        image.put("#fffcf4", to=(x, y, x+2, y+1))
        image.put("#fffcf4", to=(30-x, y, 32-x, y+1))
    image.put("#fffcf4", to=(15, 14, 17, 26))
    image.put("#dd2437", to=(0, 27, 32, 32))
    root.iconphoto(True, image)
    root.campus_icon = image
