import unittest


def contrast(a, b):
    def luminance(color):
        channels = [int(color[i:i+2], 16)/255 for i in (1, 3, 5)]
        linear = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in channels]
        return sum(v*weight for v, weight in zip(linear, (.2126, .7152, .0722)))
    low, high = sorted((luminance(a), luminance(b)))
    return (high+.05)/(low+.05)


class StaticDesignColorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
        except ImportError as error:
            raise unittest.SkipTest(f"Tk unavailable: {error}")
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except tk.TclError as error:
            # The suite also runs on build workers without a desktop display.
            raise unittest.SkipTest(f"Tk display unavailable: {error}")

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def rgb(self, value):
        return "#"+"".join(f"{component//257:02x}" for component in self.root.winfo_rgb(value))

    def test_vector_edges_are_antialiased_and_resize_without_image_leaks(self):
        from xingyuan_sis.gui.vector import VectorCanvas
        import tkinter as tk
        window = tk.Toplevel(self.root)
        self.addCleanup(window.destroy)
        window.geometry("160x100")
        canvas = VectorCanvas(window, background="#000000", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        self.root.update()
        if not canvas.antialiased:
            self.skipTest("This Tk has no built-in SVG handler")
        before = set(self.root.tk.call("image", "names"))
        for width, height in ((160, 100), (240, 150), (320, 200)):
            window.geometry(f"{width}x{height}")
            self.root.update()
            canvas.delete("all")
            canvas.create_polygon(1, 1, width-1, height*.71, 1, height-1,
                                  fill="#ffffff", outline="")
            label = canvas.create_text(20,20,text="Native text",fill="red")
            canvas.render()
            self.assertEqual(canvas.type(canvas.find_all()[0]),"image")
            self.assertEqual(canvas.itemcget(label,"text"),"Native text")
            self.assertNotIn("Native text",canvas.svg_source)
            self.assertEqual((canvas.image.width(), canvas.image.height()), (width, height))
            # Hard raster edges have only black/white. Intermediate coverage is
            # evidence that the actual SVG renderer antialiases our diagonal.
            colors = {canvas.image.get(x, y)[0] for y in range(2, height-2) for x in range(2, width-2)}
            self.assertTrue(any(0 < value < 255 for value in colors))
            self.assertEqual(len(set(self.root.tk.call("image", "names"))-before), 1)
        canvas.destroy()
        self.assertEqual(set(self.root.tk.call("image", "names")), before)

    def test_no_dotted_focus_elements_or_scrollbar_arrows(self):
        from xingyuan_sis.gui.theme import configure_styles
        style = configure_styles(self.root)
        for name in ("TButton","TNotebook.Tab","TNotebook","TEntry","TCombobox","Treeview","Treeview.Heading"):
            self.assertNotIn(".focus",str(style.layout(name)))
            for obsolete in ("Button.border", "Notebook.tab", "Notebook.client", "Combobox.field", "Entry.field", "Treeview.field", "Treeheading.border"):
                self.assertNotIn(obsolete,str(style.layout(name)))
        self.assertNotIn("Entry.field",str(style.layout("Read.TEntry")))
        for name in ("Vertical.TScrollbar","Horizontal.TScrollbar"):
            self.assertNotIn("arrow",str(style.layout(name)))

    def test_scrollbar_hides_when_idle_keeps_gutter_and_reappears_on_scroll(self):
        import tkinter as tk
        from xingyuan_sis.gui.interaction import AutoScrollbar
        from xingyuan_sis.gui.theme import configure_styles
        configure_styles(self.root)
        window = tk.Toplevel(self.root)
        self.addCleanup(window.destroy)
        window.geometry("360x200")
        window.columnconfigure(0,weight=1);window.rowconfigure(0,weight=1)
        text = tk.Text(window,width=1,height=1)
        text.grid(row=0,column=0,sticky="nsew")
        bar = AutoScrollbar(window,viewport=text,orient="vertical",command=text.yview)
        bar.grid(row=0,column=1,sticky="ns")
        text.configure(yscrollcommand=bar.set)
        self.root.update()
        self.assertFalse(bar.winfo_ismapped())
        text.insert("1.0","line\n"*100)
        self.root.update()
        self.assertTrue(bar.winfo_ismapped())
        width = text.winfo_width()
        self.root.after(1250,self.root.quit)
        self.root.mainloop()
        self.assertFalse(bar.winfo_ismapped())
        self.assertEqual(text.winfo_width(),width)
        text.yview_scroll(1,"units")
        self.root.update()
        self.assertTrue(bar.winfo_ismapped())
        bar._press(None);bar._hide()
        self.assertTrue(bar.winfo_ismapped())
        bar._release(None)

    def test_control_text_remains_readable_in_all_pointer_and_disabled_states(self):
        from xingyuan_sis.gui.theme import PALETTES, configure_styles
        controls = ("TButton", "Accent.TButton", "Danger.TButton", "CutNav.TButton",
            "CutSelected.TButton", "TabSelected.TButton", "StageNav.TButton", "TNotebook.Tab")
        states = ((), ("active",), ("pressed",), ("focus",), ("disabled",), ("disabled", "active"))
        for mode in PALETTES:
            style = configure_styles(self.root, mode)
            self.assertEqual(style.lookup("Read.TEntry","background",("readonly",)),PALETTES[mode].surface)
            for control in controls:
                for state in states:
                    with self.subTest(mode=mode, control=control, state=state):
                        foreground = self.rgb(style.lookup(control, "foreground", state=state))
                        background = self.rgb(style.lookup(control, "background", state=state))
                        self.assertGreaterEqual(contrast(foreground, background), 4.5)

    def test_flat_combo_arrow_and_scrollbar_thumb_keep_native_pointer_actions(self):
        import tkinter as tk
        from tkinter import ttk
        from xingyuan_sis.gui.theme import configure_styles
        from xingyuan_sis.gui.interaction import AutoScrollbar
        configure_styles(self.root)
        window = tk.Toplevel(self.root)
        self.addCleanup(window.destroy)
        window.geometry("360x260")
        combo = ttk.Combobox(window,values=("学院一","学院二"))
        text = tk.Text(window,width=1,height=1)
        text.insert("1.0","内容\n"*100)
        bar = AutoScrollbar(window,viewport=text,orient="vertical",command=text.yview)
        bar.grid(row=1,column=1,sticky="ns")
        combo.grid(row=0,column=0,sticky="ew")
        text.grid(row=1,column=0,sticky="nsew")
        window.columnconfigure(0,weight=1);window.rowconfigure(1,weight=1)
        text.configure(yscrollcommand=bar.set)
        self.root.update()
        combo.event_generate("<ButtonPress-1>",x=combo.winfo_width()-10,y=combo.winfo_height()//2)
        self.root.update()
        popdown = str(combo.tk.call("ttk::combobox::PopdownWindow",str(combo)))
        self.assertTrue(int(combo.tk.call("winfo","ismapped",popdown)))
        combo.tk.call("ttk::combobox::Unpost",str(combo))
        self.root.update()
        x = bar.winfo_width()//2
        y = next(y for y in range(bar.winfo_height()) if bar.identify(x,y).endswith("thumb"))
        bar.event_generate("<ButtonPress-1>",x=x,y=y)
        bar.event_generate("<B1-Motion>",x=x,y=y+60,state=256)
        bar.event_generate("<ButtonRelease-1>",x=x,y=y+60)
        self.root.update()
        self.assertGreater(text.yview()[0],0)

    def test_data_text_and_filled_input_states_remain_readable(self):
        from xingyuan_sis.gui.theme import PALETTES, configure_styles
        for mode, palette in PALETTES.items():
            style = configure_styles(self.root, mode)
            for foreground, background in ((palette.text, palette.surface), (palette.text, palette.row_alt),
                    (palette.muted, palette.surface), (palette.muted, palette.background),
                    (palette.selected_text, palette.selection), (palette.rail_muted, palette.rail),
                    (palette.on_stage,palette.stage), (palette.paper,palette.ink),
                    (palette.paper,palette.roster_alt)):
                self.assertGreaterEqual(contrast(foreground, background), 4.5)
            for state in ((), ("readonly",), ("disabled",), ("focus",), ("invalid",)):
                for control in ("TEntry", "TCombobox"):
                    foreground = self.rgb(style.lookup(control, "foreground", state=state))
                    background = self.rgb(style.lookup(control, "fieldbackground", state=state))
                    self.assertGreaterEqual(contrast(foreground, background), 4.5)
                    self.assertEqual(style.lookup(control,"borderwidth"),0)
            for control in ("TEntry", "TCombobox"):
                self.assertNotEqual(style.lookup(control,"background"),style.lookup(control,"background",("focus",)))


if __name__ == "__main__": unittest.main()
