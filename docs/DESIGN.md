# NREGA Bot - Design System

> **Source of truth for the design conventions used by NREGA Bot.** Architecture lives in [`docs/ARCHITECTURE.md`](ARCHITECTURE.md); rules in [`docs/RULES.md`](RULES.md); product intent in [`docs/PRD.md`](PRD.md).
>
> **Audience:** Engineers extending the UI. Use this to avoid inventing new design patterns.
>
> **Status:** Verified against the current repository on **30 Aug 2026** at version **3.2.7**.
>
> **Convention vs rule:** This document distinguishes two things:
> - **Explicit rule** - mandated by `docs/RULES.md` or enforced by lint/CI.
> - **Observed convention** - consistent practice visible in current code; not enforced but deviations are noteworthy.

---

## 1. Color and theme system

### 1.1 Color palette

**The palette lives in `src/config.py:78` as `COLORS: Dict[str, ColorValue]`.** Most values are either hex strings OR `(light, dark)` 2-tuples (theme-aware).

**Explicit rule:** Never hard-code colors. Always use `config.COLORS[...]`. See `docs/RULES.md` RULE-UI-001.

**Color categories in the palette:**

| Category | Examples | Purpose |
|---|---|---|
| Text | `text_dark`, etc. | Headings, primary text |
| Log tags | info, warning, error, success | Log-line color highlights |
| Buttons | primary, hover, disabled | CTAs |
| Nav buttons | active, inactive, hover | Sidebar highlighting |
| Footer status | success, warning, error | Running / failed indicators |
| Header / controls | various | Top bar |
| Dropdown / combobox | various | Pickers |
| Skeleton | loading colors | Pre-render placeholders |
| About tab | various | Settings page |
| Device / activation | various | License flow |

**Observed convention:** the palette supports light/dark mode by storing `(light, dark)` tuples. Theme toggle is in the header (`UIMixin._cycle_theme`).

### 1.2 CustomTkinter theme

The CustomTkinter theme lives at `config/theme.json`. Verified values (excerpt):

```json
{
  "CTk": {"fg_color": ["#FFFFFF", "#212325"]},
  "CTkToplevel": {"fg_color": ["#EAEAEA", "#212325"]},
  "CTkFont": {"family": "Helvetica", "size": 13, "weight": "normal", ...},
  "CTkFrame": {"corner_radius": 6, "border_width": 0,
               "fg_color": ["#F9F9FA", "#2B2B2B"], ...},
  "CTkButton": {"corner_radius": 6, "border_width": 0,
                "fg_color": ["#3B8ED0", "#1F6AA5"],
                "hover_color": ["#36719F", "#144870"], ...}
}
```

**Observed convention:** `corner_radius = 6` for frames and buttons; `border_width = 0` for flat look. These are global defaults; individual widgets may override.

### 1.3 Theme cycling

`UIMixin._cycle_theme` cycles light -> dark -> system. Default mode is "System" (set in `main_app.py:93-94`). All custom colors via `COLORS[(light, dark)]` switch automatically.

---

## 2. Typography

**Observed convention:** Default family is **Helvetica, size 13** (per `config/theme.json`). CustomTkinter does not expose a global weight toggle; bold is applied per widget.

**Fonts shipped (in `assets/fonts/`):**

- DejaVu - default Latin
- NotoSansDevanagari - Hindi PDF reports
- Regional scripts (Kannada, Bengali) - regional PDFs

**Where used:** Default for UI; regional fonts for PDF reports (`src/managers/` PDF code path).

---

## 3. Common UI components

**Observed convention:** Always prefer existing widgets from these modules:

- `src/ui_components.py` - toasts, badges, loading skeletons, About-tab badges, status pills.
- `src/tabs/autocomplete_widget.py` - `AutocompleteEntry` (Full SKU) and `LiteDropdown` (Lite SKU, monkey-patched at startup).
- `src/tabs/date_picker_popup.py` - calendar date picker.
- `src/tabs/_imports.py` - shared tab-side imports.

**Explicit rule:** Check these modules before creating new widgets. See `docs/RULES.md` RULE-UI-005.

---

## 4. Navigation and sidebar

**Observed convention:**

- Sidebar uses 7 collapsible categories (Full SKU) / fewer (Lite SKU).
- Each tab button has an icon (PNG via `LazyIconManager` in Full; Unicode emoji in Lite).
- Active tab highlight uses a category-color tint.
- Search box at top (Full SKU only) - Ctrl+K focus, case-insensitive.
- Category filter pill ("All Automations" default).

**Shortcuts (Full SKU only):**

- `Ctrl+Enter` -> start current tab automation
- `Ctrl+S` -> stop current tab
- `Ctrl+R` -> retry failed
- `Ctrl+K` -> focus sidebar search

Bindings use `bind_all` + `add="+"` + one-time flag to prevent duplicate bindings across nav rebuilds (`_nav_search_shortcut_bound` / `_automation_shortcuts_bound`).

---

## 5. Tab layout

**Observed convention:** Every automation tab follows this skeleton (inherited from `BaseAutomationTab`):

```
[Tab Header (title + sub-title)]
[Tab Body]
  [Activity row: panchayat/village dropdowns + Start/Stop/Retry]
  [Form area: selectors + inputs + action buttons]
  [Treeview results (cols: serial, name, status, message)]
  [Log area at bottom (scrollable)]
```

Treeview rows use color-tinted tags:
- `success` (green) - successful entries
- `error` (red) - failed entries
- `warning` (yellow) - warnings
- `pending` (gray) - skipped/not-run

Export actions in the result panel: Excel (openpyxl), PDF (reportlab), CSV, PNG (screenshot of the treeview).

---

## 6. Forms

**Observed convention:**

- Autocomplete dropdowns (`AutocompleteEntry`) for portal-derived values (panchayat, village, work code).
- Date pickers (`date_picker_popup`) for date selection.
- Combo boxes for fixed sets (state, fin year).
- File dialog for file management.

Form state is preserved on tab switch via the `_has_automated` flag + the tab instance cache (`tab_instances` dict in `AppState`).

---

## 7. Tables

**Observed convention:**

- `tkinter.ttk.Treeview` with `selectmode="extended"` for multi-select.
- Columns: `serial` (auto), `name`, `status`, `message` (free-form).
- Vertical scrollbar always present.
- Right-click context menu: Export Excel, Export CSV, Copy row, Retry this row (where supported).
- Status column uses color tags (success/error/warning/pending).
- Header click sorts (where implemented; some tabs sort by serial only).

---

## 8. Buttons

**Observed convention:**

- Primary CTA: filled background using `COLORS["primary"]`.
- Secondary: outline style using `COLORS["border"]`.
- Destructive (Stop All): red tint using `COLORS["danger"]` (light red -> red hover).
- Disabled: faded (`COLORS["text_disabled"]` per theme).
- Corner radius matches theme (6px).

**Footer "Stop All" button:** explicit pill-button look - border, padding, hover background (per changelog 3.2.7).

---

## 9. Notifications and toasts

**Observed convention:**

- Non-blocking toast notifications for transient events (`src/ui_components.py`).
- `messagebox.showwarning/showerror/showinfo` for blocking dialogs.
- `play_sound()` for sound feedback (start, success, error sounds in `src/managers/sound_manager.py`).
- Sound: enabled by default; user can mute via settings.

**Toast types:**

- `info` (blue) - generic info, success
- `success` (green) - automation finished
- `warning` (yellow) - non-fatal issue, "Browser Closed" warnings
- `error` (red) - automation failed

---

## 10. Loading and error states

**Loading states:**

- Skeleton widgets (`COLORS["skeleton_*"]`) during lazy tab load.
- Footer progress bar (`automation_progress` in `AppState`) reports 0.0-1.0 fraction when automation emits progress.
- Footer "% (count)" indicator (per changelog 3.2.7 visual fix).
- Footer spinner for indeterminate progress.

**Error states:**

- Inline log line color (red) on automation error.
- Toast on automation finished-with-error.
- Activity log records `status="failed"` + structured `error_*` fields.
- Crash reporter (`install_crash_reporter` in `src/utils.py`) captures uncaught exceptions and sends PII-masked crash report to server.

---

## 11. Animations and sounds

**Observed convention:**

- Splash: `ModernSplashScreen` (Full SKU) - animated; Lite SKU has no splash.
- Theme transition: `_is_theme_transitioning` flag prevents rapid re-triggering.
- Sounds: start (button click), success (chime), error (buzz); see `src/managers/sound_manager.py`.
- Animations: minimal - this is a desktop automation tool, not a game. Splashes and status pulses are the main animated elements.

---

## 12. Assets

**Asset locations (in `assets/`):**

- `assets/logo.png` - app logo (in README + splash)
- `assets/icons/` - PNG icons for nav buttons (Full SKU)
- `assets/sounds/*.wav` - start/success/error sounds
- `assets/fonts/` - DejaVu, NotoSansDevanagari, regional scripts
- `assets/infobefore.txt` - placeholder (now zero-byte after recent move)

**Observed convention:** Keep asset file size reasonable; PNG icons are typically <50 KB each.

---

## 13. Localization

**Explicit rule:** User-facing text goes through `tr()` from `src/i18n.py`. See `docs/RULES.md` RULE-LOC-003.

**Locales shipped:**

- English (en.json) - source of truth
- Hindi (hi.json) - manually edited
- Kannada (kn.json), Bengali (bn.json), Hinglish (hinglish.json) - **generated** from `scripts/translations_{kn,bn,hing}_{1..5}.py` part files via `scripts/build_locales.py`

**Adding a new i18n key** (see `docs/RULES.md` RULE-LOC-002 for full protocol):

1. Add to `en.json` AND `hi.json` (manually edited).
2. Add to `translations_kn_5.py`, `translations_bn_5.py`, `translations_hing_5.py` (last part files).
3. Run `venv/bin/python scripts/build_locales.py` - exit 0.
4. `{placeholder}` tokens identical across all languages.

**Fallback:** `tr()` accepts a default fallback string, so partial locale coverage never crashes the UI.

---

## 14. Accessibility

**Supported (observed):**

- Keyboard shortcuts (Full SKU: Ctrl+Enter / Ctrl+S / Ctrl+R / Ctrl+K).
- Standard Tk focus traversal (Tab to next widget, Shift+Tab to previous).
- Light/dark theme toggle (`UIMixin._cycle_theme`).

**Not currently supported (be aware):**

- Screen reader labels - CustomTkinter widgets have limited ARIA support.
- High-contrast mode beyond the light/dark toggle.
- Resizable text (fonts are fixed at Helvetica 13).

If you add accessibility features, do NOT break the existing keyboard shortcut bindings (one-time-flag pattern).

---

## 15. What this doc does NOT cover

- **Server-side admin panel design** - lives in `nrega-server/app/templates/` (Jinja templates). Different stack; separate documentation.
- **Marketing website** - `nrega-server/web/`; not part of the desktop app.
- **Browser-injected markers** - see `AUTOMATION_MARKER_JS` (`browser_manager.py:27-45`); this is browser-side DOM styling, not CustomTkinter design.
