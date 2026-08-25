"""Headless layout audit: instantiates EVERY tab and inspects the widget tree
to verify the Pending-Bills UI pattern:
  1. A header card exists (CTkFrame at grid row 0, corner_radius=12, 2+ labels,
     first label bold) — or a known custom header for utility tabs.
  2. Bordered cards exist (CTkFrame / CTkScrollableFrame with border_width >= 1).
  3. Start/Stop/Reset action buttons exist.
  4. Action buttons are OUTSIDE any bordered card (always visible).

Run: venv/bin/python _audit_tab_layout.py
This is informational — it does NOT modify any files. Custom-designed tabs
(Home, WhatsApp Chat, About, etc.) are reported as INFO, not FAIL.
"""
import sys
import traceback

import customtkinter as ctk
from tkinter import messagebox

# Silence messageboxes during construction
messagebox.showwarning = lambda *a, **k: None
messagebox.showerror = lambda *a, **k: None
messagebox.showinfo = lambda *a, **k: None
messagebox.askyesno = lambda *a, **k: False
messagebox.askokcancel = lambda *a, **k: False

# Reuse the smoke-test fakes
from _smoke_test_tabs import FakeApp  # noqa: E402


def _walk(widget):
    """Yield all descendant widgets (including the widget itself)."""
    yield widget
    try:
        children = widget.winfo_children()
    except Exception:
        return
    for ch in children:
        yield from _walk(ch)


def _is_bordered_card(w):
    try:
        bw = w.cget("border_width")
        if bw and float(bw) >= 1:
            return True
    except Exception:
        pass
    return False


def _is_header_card(w):
    """Header card: CTkFrame at grid row 0, containing a bold title label AND a
    second subtitle label (checked anywhere in the subtree — supports custom
    headers like Settings/About/File Manager whose labels sit in nested frames)."""
    try:
        if not isinstance(w, ctk.CTkFrame) or isinstance(w, ctk.CTkScrollableFrame):
            return False
        info = w.grid_info()
        if not info or int(info.get("row", -1)) != 0:
            return False
        cr = w.cget("corner_radius")
        if cr is not None and int(cr) not in (0, 10, 12, 13):
            return False
        labels = [c for c in _walk(w) if isinstance(c, ctk.CTkLabel)]
        if len(labels) < 2:
            return False
        bold_count = 0
        for lbl in labels[:6]:
            font = lbl.cget("font")
            if font is not None and hasattr(font, "cget"):
                try:
                    if "bold" in str(font.cget("weight")).lower():
                        bold_count += 1
                except Exception:
                    pass
        return bold_count >= 1
    except Exception:
        return False


def _action_buttons(tab):
    """Collect (widget, label) pairs that are PRIMARY run buttons.

    Config buttons that legitimately live INSIDE the settings card (Browse,
    Select Files, Set Date & Scrape, Extract, Clear, Refresh) are excluded —
    they are card content, not the Start/Stop/Reset action row.
    """
    found = []
    for attr in ("start_button", "start_btn", "login_btn"):
        w = getattr(tab, attr, None)
        if w is not None:
            found.append((w, attr))
    if found:
        return found
    # Fallback only for utility tabs without a primary run button:
    # match action-y text, but NOT config verbs (extract/select/browse/scrape/clear)
    for w in _walk(tab):
        if not isinstance(w, ctk.CTkButton):
            continue
        try:
            txt = str(w.cget("text") or "")
        except Exception:
            continue
        low = txt.lower()
        if any(k in low for k in ("start", "run ", "launch", "merge", "▶")):
            found.append((w, txt[:20]))
    return found


def _inside_bordered_card(w):
    """Return True if any ancestor of w (excluding w) is a bordered card."""
    parent = w.master
    depth = 0
    while parent is not None and depth < 20:
        if _is_bordered_card(parent):
            return True
        parent = parent.master
        depth += 1
    return False


def main():
    ctk.set_appearance_mode("light")
    root = ctk.CTk()
    root.withdraw()

    from src.tab_config import get_tabs_definition
    definitions = get_tabs_definition(FakeApp())

    all_tabs = []
    for category, tabs in definitions.items():
        for name, info in tabs.items():
            all_tabs.append((category, name, info["creation_func"], info.get("key")))

    print(f"Total tabs found: {len(all_tabs)}\n")
    print(f"{'RESULT':<6} {'CATEGORY':<22} {'TAB':<28} header  border  buttons-outside")
    print("-" * 92)

    stats = {"PASS": 0, "WARN": 0, "INFO": 0, "FAIL": 0}
    detail = []
    for category, name, creation_func, key in all_tabs:
        try:
            app = FakeApp()
            tab = creation_func(root, app)
            root.update()

            header_found = any(_is_header_card(w) for w in _walk(tab))
            bordered = [w for w in _walk(tab) if _is_bordered_card(w)]
            buttons = _action_buttons(tab)
            if buttons:
                buttons_outside = not any(_inside_bordered_card(w) for w, _ in buttons)
            else:
                buttons_outside = None  # no action buttons (utility/custom tab)

            # Verdict
            if header_found and bordered and buttons_outside:
                verdict = "PASS"
            elif not header_found and not bordered and not buttons:
                verdict = "INFO"   # custom-designed tab (Home, About, WhatsApp Chat…)
            elif header_found and bordered and buttons_outside is False:
                verdict = "WARN"   # buttons still inside a card
            elif buttons_outside is None and header_found:
                verdict = "INFO"   # utility tab with header, no start/stop
            else:
                verdict = "WARN"

            stats[verdict] += 1
            hs = "yes" if header_found else "no "
            bs = f"{len(bordered)}" if bordered else "0"
            bo = "yes" if buttons_outside else ("n/a" if buttons_outside is None else "NO ")
            print(f"{verdict:<6} {category:<22} {name:<28} {hs:<6} {bs:<7} {bo}")
            detail.append((verdict, category, name, header_found, len(bordered), buttons_outside, len(buttons)))
            tab.destroy()
        except Exception as e:
            stats["FAIL"] += 1
            print(f"FAIL   {category:<22} {name:<28} {e}")
            traceback.print_exc()

    root.destroy()

    print("\n" + "=" * 92)
    print(f"SUMMARY: PASS={stats['PASS']}  WARN={stats['WARN']}  INFO={stats['INFO']}  FAIL={stats['FAIL']}")
    if stats["WARN"] or stats["FAIL"]:
        print("\nTabs needing attention:")
        for verdict, cat, name, h, b, bo, nb in detail:
            if verdict in ("WARN", "FAIL"):
                print(f"  - [{verdict}] {cat}/{name}: header={h}, bordered={b}, buttons_outside={bo} ({nb} buttons)")


if __name__ == "__main__":
    main()
