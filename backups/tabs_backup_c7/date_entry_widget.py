import tkinter
import customtkinter as ctk
from tkcalendar import Calendar
from datetime import datetime

class DateEntry(ctk.CTkFrame):
    """A custom widget that combines a CTkEntry with a calendar popup button."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent")

        self.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(self, **kwargs)
        self.entry.grid(row=0, column=0, sticky="ew")

        # You can replace the "📅" with text like "Select" if the emoji doesn't render well
        self.button = ctk.CTkButton(self, text="📅", width=30, command=self.pick_date)
        self.button.grid(row=0, column=1, padx=(5, 0))

        self.calendar_window = None

    def pick_date(self):
        if self.calendar_window is not None and self.calendar_window.winfo_exists():
            self.calendar_window.lift()
            return

        self.calendar_window = ctk.CTkToplevel(self)
        self.calendar_window.title("Select Date")
        self.calendar_window.transient(self.winfo_toplevel())
        self.calendar_window.grab_set()
        self.calendar_window.resizable(False, False)

        try:
            current_date = datetime.strptime(self.entry.get(), "%d/%m/%Y")
            cal = Calendar(self.calendar_window, selectmode='day', date_pattern='d/m/y',
                           year=current_date.year, month=current_date.month, day=current_date.day)
        except ValueError:
            cal = Calendar(self.calendar_window, selectmode='day', date_pattern='d/m/y')

        cal.pack(padx=10, pady=10)

        def on_date_select():
            selected_date = cal.get_date()
            self.entry.delete(0, tkinter.END)
            self.entry.insert(0, selected_date)
            self.calendar_window.destroy()
            self.calendar_window = None

        ok_button = ctk.CTkButton(self.calendar_window, text="OK", command=on_date_select)
        ok_button.pack(pady=(0, 10))
        
        # Center the popup on the parent window
        self.calendar_window.update_idletasks()
        parent_x = self.winfo_toplevel().winfo_x()
        parent_y = self.winfo_toplevel().winfo_y()
        parent_w = self.winfo_toplevel().winfo_width()
        parent_h = self.winfo_toplevel().winfo_height()
        win_w = self.calendar_window.winfo_width()
        win_h = self.calendar_window.winfo_height()
        x = parent_x + (parent_w // 2) - (win_w // 2)
        y = parent_y + (parent_h // 2) - (win_h // 2)
        self.calendar_window.geometry(f"+{x}+{y}")


    def get(self):
        """Returns the date from the entry field."""
        return self.entry.get()

    def set_date(self, date_string):
        """Sets the date in the entry field."""
        self.entry.delete(0, tkinter.END)
        self.entry.insert(0, date_string)

    def clear(self):
        """Clears the entry field."""
        self.entry.delete(0, tkinter.END)
        
    def configure(self, **kwargs):
        """Allows configuring the underlying entry widget."""
        self.entry.configure(**kwargs)