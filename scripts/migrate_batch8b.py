"""migrate_batch8b.py — wrap remaining unwrapped messagebox dialogs found by the
repo-wide final audit in mb_entry_tab.py and material_entry_tab.py.

These tabs were migrated in batch 2 but their messagebox dialogs were missed.
Uses exact source→replacement (regex unsafe across f-strings / multiline).

Usage:  python3 scripts/migrate_batch8b.py
"""
import json
import re

EN_PATH = "src/locales/en.json"
HI_PATH = "src/locales/hi.json"

# Exact replacements: (old, new)
REPLACEMENTS = [
    # ── mb_entry_tab ──
    ('messagebox.askokcancel("Reset Form?", "Clear all inputs and logs?"):',
     'messagebox.askokcancel(tr("dialogs.reset_form"), tr("dialogs.reset_confirm_logs")):'),
    ('messagebox.showinfo("Retry", "No results found to retry.")',
     'messagebox.showinfo(tr("base.error_tab.retry_btn"), tr("base.retry_no_results"))'),
    ('messagebox.showinfo("Great!", "No failed items found.")',
     'messagebox.showinfo(tr("dialogs.great"), tr("base.retry_no_fails"))'),
    ('messagebox.askyesno("Retry Failed", f"Found {len(failed_items)} failed items.\\nDo you want to retry them now?"):',
     'messagebox.askyesno(tr("base.retry_confirm_title"), tr("dialogs.retry_failed_now", count=len(failed_items))):'),
    ('messagebox.showwarning("Input Error", "MB No. field is required when \'Auto\' is unchecked.")',
     'messagebox.showwarning(tr("errors.input_error"), tr("dialogs.mb_no_required"))'),
    ('messagebox.showwarning("Input Error", "All configuration fields must be filled out.")',
     'messagebox.showwarning(tr("errors.input_error"), tr("dialogs.all_config_required"))'),
    ('messagebox.showerror("Input Error", "Please provide at least one Mate Name.")',
     'messagebox.showerror(tr("errors.input_error"), tr("dialogs.mate_name_required"))'),
    ('messagebox.showinfo("Complete", "e-MB Entry process has finished.")',
     'messagebox.showinfo(tr("dialogs.complete"), tr("dialogs.emb_finished"))'),
    ('messagebox.showerror("Automation Error", f"An error occurred:\\n\\n{e}")',
     'messagebox.showerror(tr("base.automation_error.title"), tr("dialogs.an_error_occurred_detail", error=e))'),

    # ── material_entry_tab ──
    ('messagebox.showerror("Profile Error", f"Could not save profiles:\\n{e}", parent=self)',
     'messagebox.showerror(tr("dialogs.profile_error"), tr("dialogs.could_not_save_profiles", error=e), parent=self)'),
    ('messagebox.showwarning("Profile Name", "Please enter a profile name.", parent=self)',
     'messagebox.showwarning(tr("dialogs.profile_name"), tr("dialogs.enter_profile_name"), parent=self)'),
    ('messagebox.showwarning("No Data", "Fill at least one material row before saving.", parent=self)',
     'messagebox.showwarning(tr("errors.no_data"), tr("dialogs.fill_material_row"), parent=self)'),
    ('messagebox.showinfo("Saved", f"Profile \'{name}\' saved successfully.", parent=self)',
     'messagebox.showinfo(tr("dialogs.saved"), tr("dialogs.profile_saved", name=name), parent=self)'),
    ('messagebox.showwarning("No Profile", "Select a valid profile to load.", parent=self)',
     'messagebox.showwarning(tr("dialogs.no_profile"), tr("dialogs.select_valid_profile"), parent=self)'),
    ('messagebox.showwarning("No Profile", "Select a valid profile to delete.", parent=self)',
     'messagebox.showwarning(tr("dialogs.no_profile"), tr("dialogs.select_profile_delete"), parent=self)'),
]

FILES = [
    "src/tabs/mb_entry_tab.py",
    "src/tabs/material_entry_tab.py",
]


def main() -> None:
    en = json.load(open(EN_PATH, encoding="utf-8"))
    hi = json.load(open(HI_PATH, encoding="utf-8"))

    total = 0
    for path in FILES:
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        orig = src
        count = 0
        for old, new in REPLACEMENTS:
            if old in src:
                src = src.replace(old, new)
                count += 1
        if src != orig:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(src)
            print(f"  {path}: {count} wrapped")
        total += count

    # Extra keys (all new)
    extra_en = {
        "dialogs.retry_failed_now": "Found {count} failed items.\nDo you want to retry them now?",
        "dialogs.mb_no_required": "MB No. field is required when 'Auto' is unchecked.",
        "dialogs.all_config_required": "All configuration fields must be filled out.",
        "dialogs.mate_name_required": "Please provide at least one Mate Name.",
        "dialogs.complete": "Complete",
        "dialogs.emb_finished": "e-MB Entry process has finished.",
        "dialogs.profile_error": "Profile Error",
        "dialogs.could_not_save_profiles": "Could not save profiles:\n{error}",
        "dialogs.profile_name": "Profile Name",
        "dialogs.enter_profile_name": "Please enter a profile name.",
        "dialogs.fill_material_row": "Fill at least one material row before saving.",
        "dialogs.saved": "Saved",
        "dialogs.profile_saved": "Profile '{name}' saved successfully.",
        "dialogs.no_profile": "No Profile",
        "dialogs.select_valid_profile": "Select a valid profile to load.",
        "dialogs.select_profile_delete": "Select a valid profile to delete.",
    }
    extra_hi = {
        "dialogs.retry_failed_now": "{count} विफल आइटम मिले।\nक्या आप अभी उन्हें पुनः प्रयास करना चाहते हैं?",
        "dialogs.mb_no_required": "'Auto' अनचेक होने पर MB नं. फ़ील्ड आवश्यक है।",
        "dialogs.all_config_required": "सभी कॉन्फ़िगरेशन फ़ील्ड भरे जाने चाहिए।",
        "dialogs.mate_name_required": "कृपया कम से कम एक मेट नाम प्रदान करें।",
        "dialogs.complete": "पूर्ण",
        "dialogs.emb_finished": "e-MB एंट्री प्रक्रिया समाप्त हो गई।",
        "dialogs.profile_error": "प्रोफ़ाइल त्रुटि",
        "dialogs.could_not_save_profiles": "प्रोफ़ाइलें सेव नहीं हो सकीं:\n{error}",
        "dialogs.profile_name": "प्रोफ़ाइल नाम",
        "dialogs.enter_profile_name": "कृपया प्रोफ़ाइल नाम दर्ज करें।",
        "dialogs.fill_material_row": "सेव करने से पहले कम से कम एक मटेरियल पंक्ति भरें।",
        "dialogs.saved": "सेव हो गया",
        "dialogs.profile_saved": "प्रोफ़ाइल '{name}' सफलतापूर्वक सेव हुई।",
        "dialogs.no_profile": "कोई प्रोफ़ाइल नहीं",
        "dialogs.select_valid_profile": "लोड करने के लिए एक मान्य प्रोफ़ाइल चुनें।",
        "dialogs.select_profile_delete": "हटाने के लिए एक मान्य प्रोफ़ाइल चुनें।",
    }
    added = 0
    for k, v in extra_en.items():
        if k not in en:
            en[k] = v
            added += 1
    for k, v in extra_hi.items():
        hi[k] = v

    json.dump(en, open(EN_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(hi, open(HI_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nTotal wrapped: {total}; new en.json keys: {added}")


if __name__ == "__main__":
    main()
