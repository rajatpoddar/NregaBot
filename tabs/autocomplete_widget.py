# tabs/autocomplete_widget.py
import customtkinter as ctk

class AutocompleteEntry(ctk.CTkEntry):
    def __init__(self, parent, suggestions_list=None, app_instance=None, history_key=None, **kwargs):
        super().__init__(parent, **kwargs)

        self.suggestions = suggestions_list if suggestions_list is not None else []
        self.app = app_instance
        self.history_key = history_key
        
        self._suggestion_toplevel = None
        self._suggestion_listbox = None
        
        # --- PERFORMANCE FIX: Widget Pooling ---
        # Bar-bar widgets create/destroy karne se lag hota hai.
        # Hum 5 frames pehle hi bana lenge aur unhe reuse karenge.
        self._pool_frames = [] 
        self._pool_labels = []
        self._pool_buttons = []
        self._MAX_SUGGESTIONS = 5
        self._visible_suggestions = []
        
        # --- Debounce Timer ---
        self._typing_timer = None
        self._is_selecting = False 
        
        # --- Keyboard Navigation ---
        self._active_suggestion_index = -1

        self.bind("<KeyRelease>", self._on_key_release)
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<Down>", self._on_arrow_down)
        self.bind("<Up>", self._on_arrow_up)
        self.bind("<Return>", self._on_enter)

    def _on_key_release(self, event):
        if self._is_selecting: return
        if event.keysym in ("Up", "Down", "Return", "Enter", "Tab", "Escape"): return
        if event.keysym in ("Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"): return

        # Debounce: Fast typing pe lag na ho
        if self._typing_timer: self.after_cancel(self._typing_timer)
        self._typing_timer = self.after(150, self._process_filtering)

    def _process_filtering(self):
        if not self.winfo_exists(): return
        current_text = self.get().lower()
        
        if not current_text:
            self._hide_suggestions()
            return

        # Optimized Search: Sirf pehle 5 match dhundo
        matches = []
        count = 0
        for s in self.suggestions:
            if current_text in s.lower():
                matches.append(s)
                count += 1
                if count >= self._MAX_SUGGESTIONS: break
        
        if matches:
            self._show_suggestions(matches)
        else:
            self._hide_suggestions()

    def _init_popup(self):
        """Popup window aur widgets ko ek baar initialize karein."""
        if self._suggestion_toplevel and self._suggestion_toplevel.winfo_exists(): return

        self._suggestion_toplevel = ctk.CTkToplevel(self)
        self._suggestion_toplevel.wm_overrideredirect(True)
        # FOCUS FIX: Transient set karein taaki ye main window se juda rahe
        try: self._suggestion_toplevel.transient(self.winfo_toplevel())
        except: pass
        self._suggestion_toplevel.attributes("-topmost", True)
        self._suggestion_toplevel.withdraw()

        self._suggestion_listbox = ctk.CTkFrame(self._suggestion_toplevel, fg_color=("gray90", "gray20"))
        self._suggestion_listbox.pack(expand=True, fill="both")

        # Pool create karein
        self._pool_frames = []
        self._pool_labels = []
        self._pool_buttons = []

        for i in range(self._MAX_SUGGESTIONS):
            frame = ctk.CTkFrame(self._suggestion_listbox, fg_color="transparent", corner_radius=0)
            frame.grid_columnconfigure(0, weight=1)
            
            lbl = ctk.CTkLabel(frame, text="", anchor="w", padx=5)
            lbl.grid(row=0, column=0, sticky="ew")
            
            btn = None
            if self.app and self.history_key:
                btn = ctk.CTkButton(frame, text="✕", width=20, height=20, fg_color="transparent", 
                                  text_color="gray", hover_color="gray70", font=("Arial", 10))
                btn.grid(row=0, column=1, padx=(0, 2))
            
            # Events
            frame.bind("<Button-1>", lambda e, idx=i: self._on_click_suggestion(idx))
            lbl.bind("<Button-1>", lambda e, idx=i: self._on_click_suggestion(idx))
            frame.bind("<Enter>", lambda e, idx=i: self._highlight_suggestion(idx))
            
            self._pool_frames.append(frame)
            self._pool_labels.append(lbl)
            self._pool_buttons.append(btn)

    def _show_suggestions(self, suggestions):
        self._init_popup()
        self._visible_suggestions = suggestions
        
        # Position calculation
        try:
            x = self.winfo_rootx()
            y = self.winfo_rooty() + self.winfo_height()
            w = self.winfo_width()
            self._suggestion_toplevel.wm_geometry(f"{w}x{len(suggestions)*30}+{x}+{y}")
            self._suggestion_toplevel.deiconify()
            self._suggestion_toplevel.lift()
        except: return

        self._active_suggestion_index = -1

        # Reuse Widgets (No Destroy)
        for i in range(self._MAX_SUGGESTIONS):
            if i < len(suggestions):
                text = suggestions[i]
                self._pool_labels[i].configure(text=text)
                if self._pool_buttons[i]:
                    self._pool_buttons[i].configure(command=lambda v=text: self._delete_suggestion(v))
                self._pool_frames[i].pack(fill="x", ipady=2)
                self._pool_frames[i].configure(fg_color="transparent")
            else:
                self._pool_frames[i].pack_forget()

    def _hide_suggestions(self):
        if self._typing_timer:
            self.after_cancel(self._typing_timer)
            self._typing_timer = None
        if self._suggestion_toplevel:
            self._suggestion_toplevel.withdraw()
        self._active_suggestion_index = -1

    def _on_click_suggestion(self, index):
        if 0 <= index < len(self._visible_suggestions):
            self._select_suggestion(self._visible_suggestions[index])

    def _select_suggestion(self, value):
        if self._typing_timer: self.after_cancel(self._typing_timer)
        self._is_selecting = True
        
        self.delete(0, "end")
        self.insert(0, value)
        
        # --- FOCUS BUG FIX ---
        # Window ko turant destroy mat karo, thoda delay do taaki click event complete ho jaye
        # Aur focus wapas entry par force karo
        self.after(50, self._hide_suggestions)
        self.focus_force() 
        
        self.event_generate("<KeyRelease>") 
        self._is_selecting = False

    def _on_focus_out(self, event):
        # Delay badhaya taaki click register ho sake
        self.after(250, self._hide_suggestions)

    def _delete_suggestion(self, value):
        if self.app and self.history_key:
            self.app.remove_history(self.history_key, value)
            if value in self.suggestions:
                self.suggestions.remove(value)
            self.focus()
            self._process_filtering()

    def _highlight_suggestion(self, index):
        for i, frame in enumerate(self._pool_frames):
            if not frame.winfo_ismapped(): continue
            color = ("gray80", "gray30") if i == index else "transparent"
            frame.configure(fg_color=color)
        self._active_suggestion_index = index

    def _on_arrow_down(self, event):
        if not self._visible_suggestions: return
        self._active_suggestion_index = (self._active_suggestion_index + 1) % len(self._visible_suggestions)
        self._highlight_suggestion(self._active_suggestion_index)
        return "break"

    def _on_arrow_up(self, event):
        if not self._visible_suggestions: return
        self._active_suggestion_index = (self._active_suggestion_index - 1) % len(self._visible_suggestions)
        self._highlight_suggestion(self._active_suggestion_index)
        return "break"

    def _on_enter(self, event):
        if self._visible_suggestions and self._active_suggestion_index != -1:
            self._select_suggestion(self._visible_suggestions[self._active_suggestion_index])
            return "break"