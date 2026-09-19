# FINDINGS-DETAIL — `nregabot-run-1`

Complete source path and target-neutral reproduction for the single `medium` confirmed record.

---

## `in-app-update-accepts-unverified-core-payload` — medium

### Ordered trace

| # | Kind | File:line | Scope | What happens |
|---|---|---|---|---|
| 1 | entrypoint | `src/managers/services.py:223` | `ServiceManager.download_and_install_update(url, version)` | In-app update apply flow; `url`/`update_info` come from the `version.json` feed via the About-tab update prompt |
| 2 | propagation | `src/managers/services.py:239` | transport guard | Only precondition enforced: URL is a string starting `https://nregabot.com/`; a missing/empty declared hash is not refused |
| 3 | propagation | `src/managers/services.py:259` | `expected_hash = (self.app.update_info or {}).get("hash") or ""` | Empty server hash accepted; becomes the value that disables verification |
| 4 | propagation | `src/managers/services.py:260` | `if expected_hash:` | SHA-256 verification of the downloaded file exists only inside this branch — with `""`, the downloaded bytes proceed unverified |
| 5 | sink | `src/managers/services.py:285` | `os.startfile(dl_path)` (Windows) / `subprocess.call(["open", dl_path])` (288) | Unverified payload handed to the OS; Windows path executes it and `os._exit(0)` makes it the next-boot code source; macOS `.zip` payloads are copied to `core.zip` by `_apply_smart_update` |

Sibling control proving the codebase's own invariant: `loader.py:690` — *"server did not provide an integrity hash … Refusing unverified update."*

### Evidence

| File:line | Fact |
|---|---|
| `src/managers/services.py:259` | Empty hash falls through to the skip |
| `src/managers/services.py:260` | Verification strictly nested; no `else` refusal |
| `loader.py:690` | The loader refuses the identical payload shape — the vendor's intended fail-closed policy |
| `lite_loader.py:436` (comment) | Empty generic hash accepted on Lite *because* "verification still runs whenever a hash IS present" — skip-vs-verify is publisher-controlled |
| `config/version.json:10` | Generic `hash` field is empty in the live feed; platform hashes present — reachability is a field-choice away |
| `agents/parent-hunter/artifacts/harness_local_check_2.py` + `local_check_2_output.txt` | Sandboxed reproduction artifact |

### Dummy attacker / affected resource

Auditor-as-publisher (dummy fixture): the writer of `version.json` publishes a trusted-host payload without a hash field. Affected dummy resource: the downloaded file the client would install. No real endpoint or payload was contacted; the download GET fails offline inside the sandbox and is irrelevant — the defect is established at the guard/verification branch, before bytes flow.

### Native input and bounded instructions

```
url        = https://nregabot.com/updates/core_win_v3.2.11.zip
update_info = {"is_smart_update": True, "hash": ""}        # target case
url        = http://evil.example/payload.zip               # negative control
update_info = {"is_smart_update": True, "hash": "a"*64}

sandbox-exec -f /tmp/net-deny.sb python3 \
  nrega-security-audit-output/harness_local_check_2.py
```

Seatbelt profile (all four controls verified before the run): `deny default`, `deny network*`, `allow file-read*`, `allow file-write*` only under `/private/tmp/nregabot-audit-scratch`; target/toolchain read-only; empty environment except allowlisted vars; bounded wall-clock (default 120 s).

### Observed output and the invariant it proves

```
--- NEGATIVE CONTROL: http foreign host ---      attempted download URL: []   (refused pre-GET)
--- TARGET: https://nregabot.com/ with empty hash ---
                                                attempted download URL: ['https://nregabot.com/updates/core_win_v3.2.11.zip']
[result] negative-control refused: True
[result] empty-hash accepted past guard (GET attempted): True
GUARD BYPASS CONFIRMED: empty declared hash passes transport guard and reaches
the install branch without any integrity check
```

This proves the invariant violation: *any payload reaching the install branch must be hash-verified*. The negative control shows the harness detects refusal when the code refuses, so the target-case result is attributable to the missing check, not to harness blindness.

### Conditions and containment

- `version.json` must present a trusted-host payload with an empty platform hash (publisher mistake or origin compromise; TLS keeps on-path attackers out).
- User must accept the in-app update prompt.
- Containment: sandbox confined the observation to the guard decision; no download occurred, nothing persisted, no availability or cost impact.

### Source-level remediation and regression case

Strategy: make the in-app path fail closed exactly like the loader; one policy, three consumers (loader, lite_loader, services).

```python
# src/managers/services.py — inside download_and_install_update, after the guard
expected_hash = (self.app.update_info or {}).get("hash") or ""
if not expected_hash:
    self.app.after(0, messagebox.showerror, "Update Failed",
                   "Update payload has no integrity hash — refusing to install. "
                   "Please reinstall from nregabot.com.")
    self.app.after(0, lambda: about.update_button.configure(state="normal", text="Retry Update"))
    return
```

Regression case: extend `tests/` with a service-level test asserting `download_and_install_update("https://nregabot.com/updates/core_win_v3.2.11.zip", "3.2.11")` with `update_info["hash"] == ""` performs **no** download and surfaces the refusal UI — mirroring the existing rollback/gate tests for `loader.py`.
