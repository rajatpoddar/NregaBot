# tabs/autocomplete_widget.py
import customtkinter as ctk

class AutocompleteEntry(ctk.CTkEntry):
    def __init__(self, parent, suggestions_list=None, app_instance=None, history_key=None, **kwargs):
        super().__init__(parent, **kwargs)

        self.suggestions = suggestions_list if suggestions_list is not None else []
        self.app = app_instance
        self.history_key = history_key
        
        self._suggestion_toplevel = None
        
        # --- For keyboard navigation ---
        self._active_suggestion_index = -1
        self._suggestion_labels = []
        self._suggestion_frames = []
        
        # --- Debounce Timer variable ---
        self._typing_timer = None
        
        # --- NEW: Flag to prevent re-opening after selection ---
        self._is_selecting = False 

        self.bind("<KeyRelease>", self._on_key_release)
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<Down>", self._on_arrow_down)
        self.bind("<Up>", self._on_arrow_up)
        self.bind("<Return>", self._on_enter)

    def _on_key_release(self, event):
        # --- FIX: Agar abhi selection kiya hai, to search mat karo ---
        if self._is_selecting:
            return

        # Navigation keys ko ignore karein
        if event.keysym in ("Up", "Down", "Return", "Enter", "Tab", "Escape"):
            return
        if event.keysym in ("Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"):
            return

        # Debouncing Logic
        # Agar purana timer chal raha hai toh use cancel karein
        if self._typing_timer:
            self.after_cancel(self._typing_timer)
        
        # Naya timer start karein (150ms delay) - smooth typing ke liye
        self._typing_timer = self.after(150, self._process_filtering)

    def _process_filtering(self):
        """Filters suggestions and updates the UI."""
        if not self.winfo_exists(): return

        current_text = self.get().lower()
        
        if not current_text:
            self._hide_suggestions()
            return

        # Filter suggestions
        matching_suggestions = [s for s in self.suggestions if current_text in s.lower()]
        
        if matching_suggestions:
            self._show_suggestions(matching_suggestions)
        else:
            self._hide_suggestions()

    def _show_suggestions(self, suggestions):
        # Agar window pehle se hai, toh use REUSE karein (Destroy mat karein)
        if not self._suggestion_toplevel or not self._suggestion_toplevel.winfo_exists():
            self._suggestion_toplevel = ctk.CTkToplevel(self)
            self._suggestion_toplevel.wm_overrideredirect(True)
            self._suggestion_toplevel.attributes("-topmost", True)
            
            # Initial Listbox Frame
            self._suggestion_listbox = ctk.CTkFrame(self._suggestion_toplevel, fg_color=("gray90", "gray20"))
            self._suggestion_listbox.pack(expand=True, fill="both")
        else:
            # Agar window hai, to bas purane widgets hatayein
            for widget in self._suggestion_listbox.winfo_children():
                widget.destroy()

        # Position calculation
        try:
            x = self.winfo_rootx()
            y = self.winfo_rooty() + self.winfo_height()
            w = self.winfo_width()
            self._suggestion_toplevel.wm_geometry(f"{w}x{y}+{x}+{y}")
            self._suggestion_toplevel.lift()
        except Exception:
            return # Agar widget destroy ho gaya ho calculation ke dauran

        self._suggestion_labels.clear()
        self._suggestion_frames.clear()
        self._active_suggestion_index = -1

        # Sirf top 5 suggestions dikhayein
        for i, item in enumerate(suggestions[:5]):
            item_frame = ctk.CTkFrame(self._suggestion_listbox, fg_color="transparent")
            item_frame.pack(fill="x")
            item_frame.grid_columnconfigure(0, weight=1)

            label = ctk.CTkLabel(item_frame, text=item, anchor="w", padx=5)
            label.grid(row=0, column=0, sticky="ew")
            
            # Delete button
            if self.app and self.history_key:
                del_button = ctk.CTkButton(
                    item_frame, text="✕", width=25, height=25,
                    fg_color="transparent", text_color=("gray40", "gray60"), hover_color="gray70",
                    command=lambda val=item: self._delete_suggestion(val)
                )
                del_button.grid(row=0, column=1, padx=(0, 5))
            
            # Bindings
            item_frame.bind("<Button-1>", lambda e, val=item: self._select_suggestion(val))
            label.bind("<Button-1>", lambda e, val=item: self._select_suggestion(val))
            
            item_frame.bind("<Enter>", lambda e, index=i: self._on_mouse_enter(index))
            item_frame.bind("<Leave>", lambda e, index=i: self._on_mouse_leave(index))
            
            self._suggestion_labels.append(label)
            self._suggestion_frames.append(item_frame)

    def _hide_suggestions(self):
        # Timer cancel karein taaki focus out ke baad popup wapas na aa jaye
        if self._typing_timer:
            self.after_cancel(self._typing_timer)
            self._typing_timer = None

        if self._suggestion_toplevel:
            self._suggestion_toplevel.destroy()
            self._suggestion_toplevel = None
            
        self._suggestion_labels.clear()
        self._suggestion_frames.clear()
        self._active_suggestion_index = -1

    def _select_suggestion(self, value):
        # Timer cancel karein
        if self._typing_timer: self.after_cancel(self._typing_timer)
        
        # --- FIX: Flag set karein taaki KeyRelease event ignore ho jaye ---
        self._is_selecting = True
        
        self.delete(0, "end")
        self.insert(0, value)
        self._hide_suggestions()
        self.focus()
        
        # Trigger manual event (Validation triggers ke liye)
        self.event_generate("<KeyRelease>") 
        
        # --- FIX: Flag reset karein ---
        self._is_selecting = False

    def _on_focus_out(self, event):
        # Thoda delay dein taki click register ho sake (agar user list par click kare)
        self.after(200, self._hide_suggestions)

    def _delete_suggestion(self, value):
        if self.app and self.history_key:
            self.app.remove_history(self.history_key, value)
            
            if value in self.suggestions:
                self.suggestions.remove(value)
            
            # Turant refresh karein bina delay ke
            self.focus()
            self._process_filtering()

    # --- Formatting / Highlight Logic ---
    def _highlight_suggestion(self, index):
        for i, frame in enumerate(self._suggestion_frames):
            if i == index:
                frame.configure(fg_color=("gray80", "gray30")) # Thoda dark highlight
            else:
                frame.configure(fg_color="transparent")

    def _on_mouse_enter(self, index):
        if 0 <= index < len(self._suggestion_frames):
            self._suggestion_frames[index].configure(fg_color=("gray80", "gray30"))
            self._active_suggestion_index = index

    def _on_mouse_leave(self, index):
        if 0 <= index < len(self._suggestion_frames):
            self._suggestion_frames[index].configure(fg_color="transparent")
            self._active_suggestion_index = -1

    def _on_arrow_down(self, event):
        if not self._suggestion_toplevel or not self._suggestion_frames: return
        self._active_suggestion_index += 1
        if self._active_suggestion_index >= len(self._suggestion_frames):
            self._active_suggestion_index = 0
        self._highlight_suggestion(self._active_suggestion_index)
        return "break"

    def _on_arrow_up(self, event):
        if not self._suggestion_toplevel or not self._suggestion_frames: return
        self._active_suggestion_index -= 1
        if self._active_suggestion_index < 0:
            self._active_suggestion_index = len(self._suggestion_frames) - 1
        self._highlight_suggestion(self._active_suggestion_index)
        return "break"

    def _on_enter(self, event):
        if self._suggestion_toplevel and self._suggestion_labels:
            if 0 <= self._active_suggestion_index < len(self._suggestion_labels):
                selected_value = self._suggestion_labels[self._active_suggestion_index].cget("text")
                self._select_suggestion(selected_value)
                return "break"