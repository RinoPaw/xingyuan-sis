"""Export every Tk control's layout, state colors and design rationale using demo data.

Run with uv run python tools/gui_design_audit.py --output <outside-project-folder>
     --inventory docs/gui-control-inventory.md
No user database or account files are read or changed. No additional dependencies.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import inspect
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import tkinter as tk
from tkinter import ttk

from xingyuan_sis.auth import Identity
from xingyuan_sis.database import initialize_database
from xingyuan_sis.service import XingyuanService
from xingyuan_sis.gui.app import _enable_windows_dpi_awareness
from xingyuan_sis.gui.controller import COLLECTIONS, fields
from xingyuan_sis.gui.graphics import Brandmark, CutNavigation, RecordBanner, ChapterHeading, CampusSeal, ScoreSlip, NoticeHeading
from xingyuan_sis.gui.vector import VectorCanvas
from xingyuan_sis.gui.login import LoginView
from xingyuan_sis.gui.main_window import MainWindow
from xingyuan_sis.gui.theme import PALETTES, configure_styles, install_icon
from xingyuan_sis.gui.widgets import PasswordDialog, RecordDialog, ResultDialog


# Each rule contains two distinct decisions, not merely the implementation value.
# The human-readable design specification explains the tradeoffs in more detail.
RULES = {
    'score': ('选课身份和课程左对齐，实际分数在右以62pt窄体突出；未录入用文字，绝不显示0。下方通栏列表支持逐条核对。', 'text/surface保持成绩凭条清晰，分数大小承担主次，不用红绿颜色给学生价值判断。'),
    'notice': ('阅读页先列班级与日期，再给32pt公告标题，正文独占下方；目录只显示标题，扩大正文空间。', 'text/surface承担长文，标题力黑与普通正文分层；不加入兽形校徽干扰公告。'),
    'emblem': ('几何校徽按容器短边适配：尖耳在上、颊毛向外、分裂口鼻沿中轴；首页和登录用大轮廓，档案用右上角印记。', 'paper轮廓、ink内部和stage耳内负形构成三色校徽。无独立物种状态含义，不冒充人物肖像。'),
    'profile': ('本人档案在宽窗左身份右分类字段；窄窗收为顶部姓名与成绩入口、下方完整字段，防止身份画面挤掉资料。', '与名册共用身份区配色，字段维持surface/text，说明置于on_stage/stage底栏。'),
    'shell': ('主工作区按当前任务分配剩余空间，背景与导航连通；表单仍使用单独阅读面。', 'stage红底构成整页气氛，surface承载需要持续阅读的资料，避免把饱和色直接置于密集正文下。'),
    'rail': ('章节签固定左侧，品牌在上、账号在下；中部可滚动，Tab焦点会自动露出。', '导航外壳与stage同红，不再形成封闭的黑色侧栏；内部黑白票签承载可读文字。'),
    'brand': ('星原只出现一次，43pt力黑和斜纸片构成左上识别锚点；登录版沿用同一形。', 'paper底与ink字最大反差，红底露出的边角表达拼贴而不依赖额外英文标语。'),
    'identity': ('账号置于章节之后，固定左下，避免与可点击章节混淆。', 'on_stage浅字与红底配对，保留足够对比而不再使用发灰的小字。'),
    'status': ('底部仅显示当前计数、权限说明或操作结果；切页清除上页状态。', 'on_stage浅字与贯穿窗体的stage红底配对，长信息换行。'),
    'nav': ('58单位高票签内，编号x10、标签x45；编号顶部由两种字体的ascent/linespace与按钮位置推算，使文字基线一致。奇偶票签形状错位，文字保持固定列。', '未选中ink底paper字，选中整块反转为paper底ink字；悬停/焦点改变整张票签明度；不画下划线或虚线焦点框。'),
    'heading': ('唯一页标题位于102单位高斜切横幅左侧，35pt力黑；窄窗压至64高、24pt起适配。只有动作剩余空间不足180时才换行，保留数据高度。', 'ink黑斜面与paper浅字形成横向重心，右侧白色切缝引导视线；周边stage红保持连续。'),
    'summary': ('实际人数置于校园页底栏，正文优先用于公告，不占用大号标题位置。', 'on_stage/stage提供可读事实，没有口号式重复。'),
    'page-action': ('本页动作贴近唯一标题右侧；窄窗换至下一行。浏览中性、新增为主操作。', '强调按钮仍使用accent/on_accent，与stage主背景分工：按钮有独立边界，状态变化成对更新文字和底色。'),
    'search': ('搜索紧贴标题下方，固定标签与伸展输入；窄窗筛选另起一行。滚轮只滚动名册，不修改筛选值。', '标签on_stage/stage，输入text/surface，保证红底上仍有清晰可输入区域。'),
    'filter': ('学院、班级、学籍按逻辑顺序紧随查询；窄窗候选宽度由13字单位减到10，字段名称仍完整。', '候选使用text/surface实色区域；焦点以selection/selected_text整块反转，禁用用独立灰底灰字，不画细边框。'),
    'table': ('名册/课程为左表右档案；公告左侧只列标题目录；成绩为下方通栏列表。初始列宽随分隔区适配，保留拖动和水平滚动。', '常态paper/ink，交替行roster_alt，选中ink/paper整行反转；黑名录与白档案形成两个强阅读层。'),
    'column': ('列标题紧贴对应数据；初始按Schema列比例适配可用宽度，每列至少70。数值右对齐、其他左对齐。公告班级与日期转入阅读页头。', 'Roster表头使用paper/ink，hover继续保持高对比；排序方向以箭头表达。'),
    'inspector': ('名册右侧先读身份再读字段；公告阅读区更宽，成绩凭条居上。窄窗改为列表/资料页签，资料页暂收查询栏，姓名与编号代替大图，编辑等沿用记录菜单，给字段留出空间；Ctrl+F回到列表搜索。', 'surface连续阅读面与黑列表对照，身份处的stage红和paper姓名签负责图形表达。'),
    "empty": ("未选中时只在详情起点提示选择记录，不占据名册，也不制造伪造的空档案。", "单行提示使用次级文字色与纸面配对，不再重复主标题与辅助说明。"),
    "record-action": ("编辑和重置在当前档案下方；删除靠右分开，减少惯性连点；成绩入口另起一行。", "编辑与重置保持中性；删除使用错误色文字并仍有明确确认，颜色不单独决定危险含义。"),
    'banner': ('204单位高身份区：编号左上、校徽右上、姓名横切中下部、族系落在下缘；元素与亲和在编号下。', 'stage底保持红色张力，姓名paper/ink反转；校徽是学校标记，不是学生肖像。'),
    'banner-name': ('姓名置于y109的白纸片，32pt起按真实长度适配；与编号分离并成为当前档案主角。', 'ink字/paper底；大字与轮廓共同产生层级，不使用不清楚的暗红字。'),
    'banner-number': ('学号或编号左上x18/y16，24pt窄体，先于姓名提供校验标识。', 'on_stage浅字置于stage红底，与右侧黑白校徽保持区分。'),
    'badge': ('元素和亲和成对放在编号下x18/y60，用同一行明确两者关系。', 'on_stage/stage，不另外引入元素彩虹色；实际元素由文字表达。'),
    "tabs": ("学籍、族系与元素、生活资料按主题分组；窄窗外层列表/资料页签在同一窗口切换区域，内层仍切换字段。Tab聚焦后左右方向键可切换；滚轮只滚动当前内容，不切页签。", "选中页签与纸面相连，未选中用次级字和工作区底；两种状态内边距相同且不扩张，无外框，切换不改变几何尺寸。"),
    'academic-tabs': ('学院、专业、班级、族系、支系位于标题后、搜索前；切换复用标题、查询、表格及分隔布局，只更新列与数据，避免整页拆建造成空白闪帧。', '未选中ink/paper，选中使用selection/selected_text；结构属于本页，不增加第二条红色导航带。'),
    "detail-label": ("三个资料页均用标签左、值右的网格；按全部标签实际请求宽度确定共用列起点，顶部对齐便于扫描长值。", "标签为次级色、实际值为正文色；两者对纸面均可读，通过层级而非低对比区分。"),
    "detail-value": ("只读字段位于共用右列并可聚焦复制；生活资料值用原生Text换行并按显示行数增高，整页只有外层ScrollArea滚动，不截断备注。", "移除Entry.field边框元素，避免零边宽仍残留角点；正文与选区保持可读，保留聚焦复制。"),
    "reading": ("多行公告、资料或结果占据剩余阅读空间，正文自动换行，滚动条位于右侧。", "连续纸面与正文色适合长文；选区独立反转，四周用留白，无细边框。"),
    "scroll": ("8单位细滚动条靠右/下，去掉箭头；仅溢出且正在悬停/滚动/键盘操作时显示，闲置1.1秒隐藏，拖动时保留。固定细留槽避免页面抖动。", "轨道随surface/ink/stage底色；滑块control_border，导航用ink；悬停/按下提高明度，不保留立体边框。"),
    "form": ("任务窗口居于父窗口附近并受屏幕边界约束；正文上方不重复原生窗口任务标题。", "任务区保持中性底，输入用纸面实色块；任务强调交给保存按钮，区域不画细边框。"),
    "field-label": ("标签与右侧输入行对应，必填项加星号；学生字段按身份、学籍、族系、生活的邻近关系分组。", "标签使用正文色保证小字号识别；必填含义由星号表达，不只依赖颜色。"),
    "field-input": ("输入位于对应标签右侧并占据可用宽度；生日紧邻年龄，关联项以候选列表减少录入错误。", "可编辑和只读候选使用纸面实色块；聚焦用selection/selected_text整块反转，禁用用独立灰底灰字；错误通过邻近文字说明，不画细边框。"),
    "error": ("错误位于表单之后、按钮之前，紧邻保存动作且不遮盖输入；保留草稿供修正。", "错误色文字与所在底面保持对比，同时保留完整错误说明，不能只画红框。"),
    "save": ("保存位于表单底部操作区，与取消成对；登录提交占据表单宽度，形成明确的流程终点。", "强调底及专用反色表明主操作；悬停、按下、禁用均提供成对文字/底色。"),
    "cancel": ("取消在表单底部靠右，与保存相邻，Esc 同样可用；有修改时仍进行放弃确认。", "中性按钮降低与保存的竞争；焦点和悬停仍清晰可辨。"),
    "hint": ("格式说明或快捷键紧邻所解释的字段/底部动作，不在每页重复堆叠。", "次级色保持辅助地位，但不通过模糊浅灰牺牲可读性。"),
    "close": ("关闭位于只读窗口底部右侧，与正文分离，Esc 可关闭。", "中性按钮代表退出阅读，无需将关闭标为危险或主操作。"),
    'login': ('左侧红色身份区域最多360宽、窄窗约三分之一；校名在上、兽形徽记占剩余高度；右侧表单最多440宽。', '红、黑、白承担学校识别，表单保持surface/text，身份区与输入区不争夺文字对比。'),
    "login-label": ("标签在输入框正上方，固定单列顺序；账号在前，密码和确认紧随。", "正文色落在纸面上，稳定清晰；不通过占位文字代替持久标签。"),
    "login-input": ("输入框与标签同宽对齐；默认管理员账号只读禁用，密码使用掩码；首个可输入字段获得焦点。", "输入与禁用状态使用不同底色；焦点描边清楚，账号值在灰底上仍保持可读。"),
    "menu": ("文件、记录、前往、查看、账户、帮助按桌面习惯从左到右；项次序按同类动作分组。", "弹出菜单请求纸面/正文与选中反色；原生顶层菜单与标题栏由操作系统绘制，不能伪称 RGB 完全受控。"),
}

FIELD_REASONS = {
    "student_no": "主标识最先出现，便于核对账号与后续资料的归属。",
    "name": "名称紧随主编号，先建立人的或资料对象的可读身份。",
    "gender": "与姓名、生日和年龄邻近，保持身份资料为一组。",
    "birth_date": "在年龄之前，先提供可推算年龄的原始日期。",
    "age": "紧跟生日，方便理解完整生日推算年龄、日期不完整时保留年龄资料的关系。",
    "enrollment_year": "学生表单在此开始学籍组；班级表单则作为专业归属后的年级信息。",
    "class_code": "在入学年份之后核对班级；公告中在正文之前确认接收范围。",
    "status": "学籍状态紧随班级归属，先确认在校状态再填写族系信息。",
    "family": "学生在此开始族系组，并放在支系之前以提供关联候选。",
    "branch": "紧跟族系，只从该族系的支系中选择，降低错误关联。",
    "primary_element": "紧邻族系资料，且在亲和等级之前给出等级所指对象。",
    "primary_affinity": "紧跟主元素，把对象与等级作为一对阅读。",
    "contact": "在结构化身份/学籍/族系之后开始生活组，避免联系方式打断主流程。",
    "dormitory": "紧邻联系方式，同属生活资料。",
    "notes": "放在最后承接无法结构化的补充，使用多行输入。",
    "code": "学院、专业、班级的主编号先于名称，保持跨入口的标识核对顺序。",
    "department_code": "在专业或课程的自身标识和基本属性之后确认所属学院。",
    "major_code": "在班级自身标识之后明确专业归属，再录入年级。",
    "course_code": "课程表单先确认主编号；选课表单紧随学生标识来确认关联课程。",
    "credits": "在课程编号和名称之后，与课时相邻便于检查教学规模。",
    "hours": "紧跟学分，让相关数值在相邻行核对。",
    "semester": "在学生和课程之后，先确认选课主键中的学期，再填写成绩。",
    "score": "成绩在学生、课程和学期之后填写；留空表示待录入。",
    "title": "公告先写可识别的标题，再确认接收班级和正文。",
    "body": "公告最后使用较高的多行输入区，容纳完整内容而不拉长单行。",
}


def field_context(widget):
    owner = widget.master
    while owner is not None and not isinstance(owner, RecordDialog): owner = owner.master
    if owner is None: return None
    key = next((key for key, control in owner.controls.items() if control is widget), None)
    if key is None and widget.winfo_class() == "TLabel":
        text = str(option(widget, "text")).removesuffix(" *")
        key = next((field.key for field in fields(owner.key) if field.label == text), None)
    if key is None: return None
    reason = FIELD_REASONS[key]
    if owner.key == "families": reason = "族系名称是本记录唯一字段，直接进入输入，不增加多余分组。"
    elif owner.key == "branches" and key == "family": reason = "支系名称之后确认所属族系，核对同名支系的归属。"
    return key, reason


@contextmanager
def trace_origins():
    original = tk.BaseWidget.__init__
    def construct(widget, *args, **kwargs):
        original(widget, *args, **kwargs)
        frame = inspect.currentframe().f_back
        try:
            while frame:
                path = Path(frame.f_code.co_filename)
                if path.parent.name == "gui" and path.parent.parent.name == "xingyuan_sis":
                    widget.design_origin = f"{path.name}:{frame.f_lineno} {frame.f_code.co_qualname}"
                    break
                frame = frame.f_back
        finally:
            del frame
    tk.BaseWidget.__init__ = construct
    try:
        yield
    finally:
        tk.BaseWidget.__init__ = original


def rule_for(widget):
    origin = getattr(widget, "design_origin", "")
    cls = widget.winfo_class()
    text = str(option(widget, "text"))
    style = str(option(widget, "style"))
    if isinstance(widget, VectorCanvas) and not isinstance(widget, CampusSeal): return rule_for(widget.master)
    if isinstance(widget, CampusSeal) or "CampusSeal." in origin: return "emblem"
    if isinstance(widget, ChapterHeading) or "ChapterHeading." in origin: return "heading"
    if isinstance(widget, ScoreSlip) or "ScoreSlip." in origin: return "score"
    if isinstance(widget, NoticeHeading) or "NoticeHeading." in origin: return "notice"
    if "_show_profile" in origin: return "profile"
    if isinstance(widget, tk.Menu): return "menu"
    if isinstance(widget, tk.Toplevel): return "form"
    if isinstance(widget, Brandmark) or "Brandmark." in origin: return "brand"
    if isinstance(widget, CutNavigation) or "CutNavigation." in origin: return "nav"
    if "RailMuted" in style: return "identity"
    if "_show_collection" in origin and style in {"Nav.TButton", "StageNav.TButton", "TabSelected.TButton"}: return "academic-tabs"
    if cls == "Canvas" and "Rail" in str(option(widget.master, "style")): return "rail"
    if isinstance(widget, RecordBanner) or "RecordBanner." in origin:
        if "BannerName" in style: return "banner-name"
        if "BannerNumber" in style: return "banner-number"
        if "ElementBadge" in style: return "badge"
        return "banner"
    if "Scrollbar" in cls: return "scroll"
    if cls in {"TNotebook", "TNotebook.Tab"}: return "tabs"
    if cls == "Treeview": return "table"
    if "ReadonlyParagraph." in origin: return "detail-value"
    if cls == "Text": return "field-input" if "RecordDialog." in origin else "reading"
    if "Title.TLabel" in style and "InspectorTitle" not in style: return "heading"
    if "FormError" in style or style == "Error.TLabel": return "error"
    if "Read.TEntry" in style: return "detail-value"
    if "_student_details" in origin: return "detail-label"
    if "RecordDialog." in origin:
        if text == "保存": return "save"
        if text == "取消": return "cancel"
        if text.startswith("生日：") or text.startswith("Ctrl+"): return "hint"
        if cls == "TLabel": return "field-label"
        if cls in {"TEntry", "TCombobox"}: return "field-input"
        return "form"
    if "PasswordDialog." in origin:
        if cls == "TButton": return "save"
        return "field-label" if cls == "TLabel" else "field-input" if cls == "TEntry" else "form"
    if "LoginView." in origin:
        if cls == "TButton": return "save"
        if cls == "TEntry": return "login-input"
        if "Muted" in style: return "hint"
        return "login-label" if cls == "TLabel" else "login"
    if text == "关闭": return "close"
    if "inspect" in origin:
        return "record-action" if cls == "TButton" else "empty" if text == "选择记录以查看详情" else "inspector"
    if "_heading" in origin: return "summary" if cls == "TLabel" else "heading"
    if "_show_collection" in origin:
        if cls == "TEntry" or text == "搜索": return "search"
        if cls == "TCombobox": return "filter"
        if cls == "TButton": return "page-action"
        return "table" if cls == "TPanedwindow" else "inspector" if "Surface" in style else "shell"
    if "_build_header" in origin or "Rail" in style: return "rail"
    if "MainWindow.__init__" in origin and cls == "TLabel": return "status"
    if cls == "TButton": return "page-action"
    if "_show_overview" in origin: return "reading"
    return "shell"


def option(widget, name):
    try:
        # Tk accepts abbreviations: Entry.cget('text') would return textvariable's name.
        return widget.cget(name) if name in widget.keys() else ""
    except tk.TclError: return ""


def style_name(widget):
    name = str(option(widget, "style") or widget.winfo_class())
    if widget.winfo_class() == "TScrollbar" and not option(widget, "style"):
        name = str(option(widget, "orient")).title()+".TScrollbar"
    return name


def colors(widget, states=(), style=None):
    if isinstance(widget, ttk.Widget):
        style = style or style_name(widget)
        return {name: str(ttk.Style(widget).lookup(style, name, state=states)) for name in (
            "foreground", "background", "fieldbackground", "bordercolor")}
    if isinstance(widget, tk.Menu):
        prefix = "disabled" if "disabled" in states else "active" if "active" in states else ""
        return {"foreground": str(option(widget, prefix+"foreground")),
            "background": str(option(widget, "activebackground" if "active" in states else "background")),
            "selectcolor": str(option(widget, "selectcolor"))}
    return {name: str(option(widget, name)) for name in (
        "foreground", "background", "highlightbackground", "highlightcolor")}


def label_for(widget):
    text = str(option(widget, "text")).replace("\n", " / ")
    if not text and widget.winfo_class() in {"TLabel", "Label"} and option(widget, "textvariable"):
        text = str(widget.tk.globalgetvar(str(option(widget, "textvariable"))))
    if text: return text
    if widget.winfo_class() == "TCombobox" and "_show_collection" in getattr(widget, "design_origin", ""):
        return widget.get()+"（筛选）"
    # Link an input to its persistent label instead of exporting sample input values.
    grid = widget.grid_info() if widget.winfo_manager() == "grid" else {}
    if grid:
        for sibling in widget.master.winfo_children():
            if sibling.winfo_class() == "TLabel" and sibling.winfo_manager() == "grid":
                other = sibling.grid_info()
                same_row = grid["column"] > 0 and other["row"] == grid["row"] and other["column"] == 0
                above = grid["column"] == 0 and other["row"] == grid["row"]-1 and other["column"] == 0
                if same_row or above:
                    return str(option(sibling, "text"))+"（输入/值）"
    return widget.winfo_class()


def snapshot(root, scene, rows, seen):
    def add(widget, suffix="", *, label=None, rule=None, layout=None, style=None):
        identity = str(widget)+suffix
        visibility = identity+(":visible" if widget.winfo_ismapped() else ":hidden")
        if visibility in seen: return None
        seen.add(visibility)
        rule = rule or rule_for(widget)
        manager = widget.winfo_manager()
        getter = getattr(widget, manager+"_info", None) if manager in {"grid", "pack", "place"} else None
        info = getter() if getter is not None else {}
        info = {key: str(value) for key, value in info.items() if key != "in"}
        row = {"id": f"C{len(rows)+1:04}", "scene": scene, "path": identity,
            "class": widget.winfo_class(), "label": label or label_for(widget), "origin": getattr(widget, "design_origin", "Tk/OS"),
            "mapped": bool(widget.winfo_ismapped()), "layout": layout or {"manager": manager, **info},
            "bounds": [widget.winfo_x(), widget.winfo_y(), widget.winfo_width(), widget.winfo_height()],
            "rule": rule, "position_reason": RULES[rule][0], "color_reason": RULES[rule][1],
            "colors": {"normal": colors(widget, style=style)}}
        context = field_context(widget)
        if context is not None:
            key, reason = context
            row["label"] += " / "+key
            row["position_reason"] = reason+" "+row["position_reason"]
            if str(option(widget, "state")) == "disabled":
                row["color_reason"] += " 此字段在编辑时不可修改，灰底灰字传达该限制。"
        if isinstance(widget, ttk.Widget):
            for state in ("active", "pressed", "focus", "disabled", "readonly", "selected", "invalid"):
                row["colors"][state] = colors(widget, (state,), style)
        elif isinstance(widget, tk.Menu):
            for state in ("active", "disabled"): row["colors"][state] = colors(widget, (state,))
        rows.append(row)
        return row
    def walk(widget):
        add(widget)
        if isinstance(widget, ttk.Treeview):
            for column in widget["columns"]:
                add(widget, ":heading:"+column, label="表头 / "+widget.heading(column, "text"), rule="column",
                    layout=widget.column(column), style=style_name(widget)+".Heading")
        if isinstance(widget, ttk.Notebook):
            for index, tab in enumerate(widget.tabs()):
                add(widget, ":tab:"+str(index), label="页签 / "+widget.tab(tab, "text"), rule="tabs",
                    layout={"index": index}, style="TNotebook.Tab")
        if isinstance(widget, tk.Menu):
            end = widget.index("end")
            for i in range(end+1 if end is not None else 0):
                kind = widget.type(i)
                if kind == "separator": continue
                text = widget.entrycget(i, "label")
                add(widget, ":menu:"+str(i), label="菜单项 / "+text, rule="menu", layout={"index": i, "type": kind,
                    "state": widget.entrycget(i, "state")})
        if isinstance(widget, tk.Canvas):
            for item in widget.find_all():
                if widget.type(item) not in {"polygon", "line", "text"}: continue
                tags = widget.gettags(item)
                rule = next((tag for tag in tags if tag in {"emblem", "banner-name", "banner-number", "badge"}),rule_for(widget))
                row = add(widget, ":item:"+str(item), label=("透明文字 / "+widget.itemcget(item,"text")) if widget.type(item)=="text" else "矢量路径 / "+widget.type(item), rule=rule,
                    layout={"coordinates": widget.coords(item)})
                if row is not None:
                    row["colors"] = {"normal": {"fill": widget.itemcget(item, "fill"),
                        "background": widget.cget("background")}}
        for child in widget.winfo_children(): walk(child)
    root.update_idletasks(); root.update()
    walk(root)


def markdown(rows):
    def cell(value): return str(value).replace("|", "\\|").replace("\n", " ")
    out = ["# GUI 逐控件设计清单", "", "由 `tools/gui_design_audit.py` 从真实 Tk 控件树生成；全部使用临时示例数据。",
        "", "矢量路径记录保留原始坐标和实色；Tk 9 将它们转成当前物理尺寸的抗锯齿 SVG 渲染层。边缘过渡像素由覆盖率计算，不是额外的语义颜色。公共外壳只在首次出现时列出。每个表单字段、表头、页签、菜单项另列。数据行复用表格规则，不为每条学生数据虚构不同的设计理由。",
        "", "布局参数是 Tk 请求值；bounds 为父容器内的 x/y/w/h。隐藏页签、滚动区外内容和未展开菜单的 bounds 不代表截图中的可见位置。",
        "", "前景/底色、边框按实际样式解析；不适用于某控件的样式属性不代表绘制像素。原生菜单与系统窗口边框不能由这些请求值推断实际系统配色。",
        "", "每行的位置及颜色理由完整保留，相同状态不重复写出。审查命令还会在指定输出目录生成完整状态 JSON。设计规则与颜色词典见 [设计决策表](gui-control-decisions.md)。", ""]
    scene = None
    for row in rows:
        if row["scene"] != scene:
            scene = row["scene"]
            out += ["", "## "+scene, "", "| ID / 控件 | 来源、布局与边界 | 位置理由 | 颜色与状态 | 颜色理由 |", "| --- | --- | --- | --- | --- |"]
        c = row["colors"]
        states = [f"{state}: "+", ".join(f"{k}={v}" for k,v in values.items() if v) for state,values in c.items() if state == "normal" or values != c["normal"]]
        details = f"{row['origin']} / {row['layout']} / bounds={row['bounds']} / mapped={row['mapped']}"
        out.append("| "+" | ".join(map(cell,[row["id"]+" "+row["label"], details, row["position_reason"], "; ".join(states), row["color_reason"]]))+" |")
    return "\n".join(out)+"\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inventory", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows, seen = [], set()
    _enable_windows_dpi_awareness()
    original_home = os.environ.get("XINGYUAN_HOME")
    with TemporaryDirectory(prefix="xingyuan-design-") as temp, trace_origins():
        os.environ["XINGYUAN_HOME"] = str(Path(temp)/"auth")
        root = None
        try:
            db = Path(temp)/"preview.db"
            initialize_database(db)
            service = XingyuanService(db); service.seed_demo()
            own = service.student_by_no("20260001")["class_code"]
            service.create_announcement(title="选课确认", body="请核对本学期选课记录。", class_code=own)
            root = tk.Tk(); root.title("星原 SiS"); root.geometry("1280x820+16+16")
            root.tk.call("tk", "scaling", 96/72); configure_styles(root); install_icon(root)
            window = MainWindow(root, db, Identity("Administrator", "admin"), on_logout=lambda:None)
            window.pack(fill="both", expand=True)
            for page, _ in window.navigation:
                window.show_page(page)
                if page == "academics":
                    for key in ("departments", "majors", "classes", "families", "branches"):
                        window._academic_page(key)
                        if window.tree.get_children(): window.tree.selection_set(window.tree.get_children()[0]);window.inspect()
                        snapshot(root, "管理员 / "+key, rows, seen)
                else:
                    if window.collection and window.tree.get_children(): window.tree.selection_set(window.tree.get_children()[0]);window.inspect()
                    snapshot(root, "管理员 / "+page, rows, seen)
            window.show_page("students"); window.tree.selection_set("20260001"); window.inspect()
            snapshot(root, "学生详情 / 学籍", rows, seen)
            tabs = next(child for child in window.inspector.winfo_children() if isinstance(child, ttk.Notebook))
            for i in (1,2): tabs.select(i);snapshot(root, "学生详情 / 页签"+str(i), rows, seen)
            for key in COLLECTIONS:
                for edit in (False, True) if key != "announcements" else (False,):
                    original = window.controller.rows(key)[0] if edit else None
                    dialog = RecordDialog(window, window.controller, key, original)
                    snapshot(root, ("编辑 / " if edit else "新增 / ")+key,rows,seen)
                    dialog.destroy()
            for cls, title in ((PasswordDialog,"修改密码"),(ResultDialog,"操作结果")):
                dialog = cls(window,window.controller) if cls is PasswordDialog else cls(window,title,"操作已完成。")
                snapshot(root,title,rows,seen);dialog.destroy()
            root.geometry("960x640+16+16");window.theme_var.set("afterhours");window.zoom_var.set(1.5);window.change_theme()
            snapshot(root,"深色 / 150% / 960×640",rows,set())
            window.compact_tabs.select(1);snapshot(root,"深色 / 150% / 内嵌资料",rows,seen)
            window.destroy();root.geometry("1280x820+16+16");configure_styles(root)
            student = MainWindow(root,db,Identity("20260001","student","20260001"),on_logout=lambda:None)
            student.pack(fill="both",expand=True)
            for page,_ in student.navigation:
                student.show_page(page);snapshot(root,"学生身份 / "+page,rows,seen)
            student.destroy()
            login = LoginView(root,db,on_success=lambda _:None);login.pack(fill="both",expand=True)
            for mode in ("setup","login","forced-password"):
                login.mode=mode;login._render_form();snapshot(root,"身份 / "+mode,rows,seen)
        finally:
            if root is not None: root.destroy()
            if original_home is None: os.environ.pop("XINGYUAN_HOME",None)
            else: os.environ["XINGYUAN_HOME"]=original_home
    (args.output/"control-inventory.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
    document = markdown(rows)
    (args.output/"control-inventory.md").write_text(document,encoding="utf-8")
    if args.inventory: args.inventory.write_text(document,encoding="utf-8")
    print(f"Exported {len(rows)} controls and subcontrols, {len(set(r['scene'] for r in rows))} scenes.")


if __name__ == "__main__": main()
