#!/usr/bin/env python3
"""Parent-owned audit tooling: builds coverage-ledger.json for run nregabot-run-1.
Not target code. Encodes coverage_ids per RECONNAISSANCE.md (RFC 3986, '::' join).
"""
import json
import os
import urllib.parse

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "coverage-ledger.json")

AC = "ATTACK-CLASSES.md#"
SC = "SUPPLY-CHAIN-AND-RELEASE.md#"
DK = "DESKTOP-MOBILE-AND-LOCAL-IPC.md#"
WB = "WEB-PROTOCOL-AND-AUTH.md#"
DA = "DATA-ISOLATION-AND-LIFECYCLE.md#"
CL = "CLOUD-AND-DEPLOYMENT.md#"

SC_SEL = [SC + "Core discipline",
          SC + "Dependency and build-input attack classes",
          SC + "CI and automation attack classes",
          SC + "Release and update attack classes",
          SC + "Universal moves",
          SC + "Validation rules"]
DK_SEL = [DK + "Core discipline",
          DK + "Local IPC and exported-component attack classes",
          DK + "Privileged-helper and local-file attack classes",
          DK + "Application-state and device-lifecycle attack classes",
          DK + "Universal moves",
          DK + "Validation rules"]
WB_SEL = [WB + "Core discipline",
          WB + "Browser-session attack classes",
          WB + "API-key and mTLS attack classes",
          WB + "Universal moves",
          WB + "Validation rules"]
DA_SEL = [DA + "Core discipline",
          DA + "Derived-data and disclosure attack classes",
          DA + "Export, backup, restore, and migration attack classes",
          DA + "Deletion, revocation, and lifecycle attack classes",
          DA + "Universal moves",
          DA + "Validation rules"]
CL_SEL = [CL + "Core discipline",
          CL + "Workload identity and IAM attack classes",
          CL + "Ingress, network, and control-plane attack classes",
          CL + "Configuration and secret lifecycle attack classes",
          CL + "Universal moves",
          CL + "Validation rules"]
EXC_DESK = [{"block": DK + "Webview and native-bridge attack classes",
             "reason": "No webview exists; Selenium drives the government portal in the user's own browser."},
            {"block": DK + "Deep-link, callback, and navigation attack classes",
             "reason": "No custom-scheme deep-link handler is registered in source."}]
EXC_CLOUD = [{"block": CL + "Container and orchestration attack classes",
              "reason": "No container/k8s manifests in desktop repo."},
             {"block": CL + "Managed storage, events, and edge attack classes",
              "reason": "No cloud resource manifests in desktop repo; NAS deployment is server-repo scope."}]
EXC_WEB = [{"block": WB + "HTTP framing and cache attack classes",
            "reason": "Client-side only; the client does not terminate proxies or caches."},
           {"block": WB + "Federated-identity attack classes",
            "reason": "No JWT/OAuth-RP parsing in client; OAuth is server-mediated via /api/oauth/*."},
           {"block": WB + "MFA, passkey, and account-transition attack classes",
            "reason": "No MFA/passkey flows in client; OTP verification is server-side."}]
EXC_DATA = [{"block": DA + "Tenant and object-isolation attack classes",
             "reason": "Single-user desktop client; server-side tenancy is out of scope."}]


def enc(s: str) -> str:
    return urllib.parse.quote(s, safe="-._~")


def cid(surface: str, boundary: str, subsystem: str, attack_class: str) -> str:
    return "::".join(enc(x) for x in (surface, boundary, subsystem, attack_class))


SUP = "SUPPLY-CHAIN-AND-RELEASE.md (dependency/build-input/CI/release/update classes)"
DESK = "DESKTOP-MOBILE-AND-LOCAL-IPC.md (IPC/local-file/credential-store/lifecycle classes)"
WEB = "WEB-PROTOCOL-AND-AUTH.md (API-key/credential-transport/session classes)"
DATA = "DATA-ISOLATION-AND-LIFECYCLE.md (derived-data/export-backup/deletion classes)"
CLOUD = "CLOUD-AND-DEPLOYMENT.md (CI/workload/secret-lifecycle classes)"

# Canonical subsystem refs: repository package paths (stable, source-derived).
SUBSYS_REF = {
    "Update pipeline (loader/lite_loader)": "loader.py",
    "In-app update (services/main_app/lite_app)": "src/managers/services.py",
    "Loader + app control files": "src/utils.py",
    "License manager": "src/managers/services.py",
    "License/telemetry HTTP client": "src/app/app_license.py",
    "Heartbeat/app-config consumer": "src/app/app_license.py",
    "PII masking + telemetry sync": "src/utils.py",
    "Cloud backup": "src/app/app_license.py",
    "Cloud file manager": "src/tabs/file_management_tab.py",
    "Local IPC": "main_app.py",
    "Browser manager": "src/managers/browser_manager.py",
    "Tab file handling": "src/tabs/base_tab.py",
    "CI release pipeline": ".github/workflows/release.yml",
    "Packaging": "scripts/build_update.py",
    "Dependencies": "requirements.txt",
    "Repo hygiene": ".gitignore",
    "Misc subsystems": "src/ui_components.py",
    "Crash/OAuth flows": "src/app/app_license.py",
}

ORD = {
    "injection": AC + "Injection",
    "access": AC + "Access control",
    "file": AC + "Resource and file handling",
    "crypto": AC + "Cryptography and secrets",
    "logic": AC + "Business logic",
    "abuse": AC + "Feature abuse and data leakage",
    "chain": AC + "Chained vulnerabilities and trust boundaries",
    "wild": AC + "Wildcard",
    "obvious": AC + "Obvious things",
}

units = []


def add(surface, boundary, subsystem, aclass, starting, companions, excluded, subsys_ref):
    starting = [p for p in starting if not p.endswith("/")]
    units.append({
        "coverage_id": cid(surface, boundary, SUBSYS_REF[subsystem], ORD[aclass]),
        "canonical_refs": {
            "surface": surface,
            "boundary": boundary,
            "subsystem": SUBSYS_REF[subsystem],
            "attack_class": ORD[aclass],
        },
        "surface": surface,
        "boundary": boundary,
        "subsystem": subsystem,
        "attack_class": ORD[aclass],
        "starting_paths": starting,
        "ordinary_attack_class_block": ORD[aclass],
        "selected_companion_blocks": companions,
        "excluded_blocks": excluded,
        "prior_status": "none",
        "attempts": [],
        "wave": 1,
        "status": "planned",
        "agent_id": None,
        "reviewed_paths": [],
        "local_checks": [],
        "result_fingerprints": [],
        "unresolved": [],
    })


EXC_DESK = [{"block": DK + "Webview and native-bridge attack classes",
             "reason": "No webview exists; Selenium drives the government portal in the user's own browser."},
            {"block": DK + "Deep-link, callback, and navigation attack classes",
             "reason": "Custom-scheme deep links are covered only where a real handler exists; none registered in source."}]
EXC_CLOUD = [{"block": CL + "Container and orchestration attack classes",
              "reason": "No container/k8s manifests in desktop repo."},
             {"block": CL + "Managed storage, events, and edge attack classes",
              "reason": "No cloud resource manifests in desktop repo; NAS deployment is server-repo scope."}]
EXC_WEB = [{"block": WB + "HTTP framing and cache attack classes",
            "reason": "Client-side only; client does not terminate proxies/caches."},
           {"block": WB + "Federated-identity attack classes",
            "reason": "No JWT/OAuth-RP parsing in client; OAuth is server-mediated via /api/oauth/*."},
           {"block": WB + "MFA, passkey, and account-transition attack classes",
            "reason": "No MFA/passkey flows in client; OTP is server-side."}]
EXC_DATA = [{"block": DA + "Tenant and object-isolation attack classes",
             "reason": "Single-user desktop client; server-side tenancy is out of scope."}]

SC_CORE = SC_SEL
DK_CORE = DK_SEL
WB_CORE = WB_SEL
DA_CORE = DA_SEL
CL_CORE = CL_SEL

B_UPD = "loader.py#check_for_updates/extract_zip (update authority boundary)"
B_LIC = "src/managers/services.py#check_license + save_license_dat (license-trust boundary)"
B_NET = "src/config.py#LICENSE_SERVER_URL + requests sessions (client-server TLS boundary)"
B_PII = "src/utils.py#mask_* + base_tab._extract_tree_columns_rows (PII cloud boundary)"
B_LOCL = "src/utils.py#get_data_path state files + main_app 127.0.0.1:60123 (local-trust boundary)"
B_CFG = ".github/workflows/release.yml#on push main (release authority boundary)"
B_FLAG = "src/app/app_license.py#/api/app-config consumer (server-control boundary)"
B_FILE = "src/tabs/file_management_tab.py#files/api client (cloud storage boundary)"

U = ["loader.py", "lite_loader.py", "src/managers/services.py", "main_app.py", "lite_app.py"]

# 1 Supply-chain / update pipeline (loader)
add("Update metadata + payload download (loader)", B_UPD, "Update pipeline (loader/lite_loader)", "file", U, SC_CORE, EXC_WEB + EXC_DATA + EXC_CLOUD, SC)
add("Update metadata + payload download (loader)", B_UPD, "Update pipeline (loader/lite_loader)", "chain", U, SC_CORE, EXC_WEB + EXC_DATA + EXC_CLOUD, SC)
add("Update metadata + payload download (loader)", B_UPD, "Update pipeline (loader/lite_loader)", "logic", U, SC_CORE, EXC_WEB + EXC_DATA + EXC_CLOUD, SC)
# 2 In-app update (services + main_app smart update + lite_app)
add("In-app update + smart update + updater.bat", B_UPD, "In-app update (services/main_app/lite_app)", "file", U, SC_CORE, EXC_WEB + EXC_DATA + EXC_CLOUD, SC)
add("In-app update + smart update + updater.bat", B_UPD, "In-app update (services/main_app/lite_app)", "chain", U, SC_CORE, EXC_WEB + EXC_DATA + EXC_CLOUD, SC)
# 3 Local state-file trust (loader/app control files)
add("Local state files as control input (core_version.json, force_rollback, blocked, maintenance, boot_state)", B_LOCL, "Loader + app control files", "logic", ["loader.py", "lite_loader.py", "src/utils.py", "src/app/app_license.py"], DK_CORE, EXC_WEB + EXC_DATA + EXC_CLOUD, DESK)
add("Local state files as control input (core_version.json, force_rollback, blocked, maintenance, boot_state)", B_LOCL, "Loader + app control files", "file", ["loader.py", "lite_loader.py", "src/utils.py", "src/app/app_license.py"], DK_CORE, EXC_WEB + EXC_DATA + EXC_CLOUD, DESK)
# 4 License storage & validation
add("license.dat storage, load, local expiry check", B_LIC, "License manager", "crypto", ["src/managers/services.py", "src/utils.py", "src/app/app_license.py"], DK_CORE, EXC_WEB + EXC_DATA + EXC_CLOUD, DESK)
add("license.dat storage, load, local expiry check", B_LIC, "License manager", "logic", ["src/managers/services.py", "src/utils.py", "src/app/app_license.py"], DK_CORE, EXC_WEB + EXC_DATA + EXC_CLOUD, DESK)
# 5 License server credential transport
add("License key transport (headers, heartbeat query param, auth-token flow)", B_NET, "License/telemetry HTTP client", "abuse", ["src/app/app_license.py", "src/managers/services.py"], WB_CORE, EXC_DATA + EXC_CLOUD, WEB)
add("License key transport (headers, heartbeat query param, auth-token flow)", B_NET, "License/telemetry HTTP client", "obvious", ["src/app/app_license.py", "src/managers/services.py"], WB_CORE, EXC_DATA + EXC_CLOUD, WEB)
add("License key transport (headers, heartbeat query param, auth-token flow)", B_NET, "License/telemetry HTTP client", "crypto", ["src/app/app_license.py", "src/managers/services.py"], WB_CORE, EXC_DATA + EXC_CLOUD, WEB)
# 6 Server-driven controls
add("Server-driven config consumption (feature flags, states registry, maintenance/rollback/blocked)", B_FLAG, "Heartbeat/app-config consumer", "logic", ["src/app/app_license.py", "src/config.py"], CL_CORE, EXC_WEB + EXC_DATA, CLOUD)
add("Server-driven config consumption (feature flags, states registry, maintenance/rollback/blocked)", B_FLAG, "Heartbeat/app-config consumer", "obvious", ["src/app/app_license.py", "src/config.py"], CL_CORE, EXC_WEB + EXC_DATA, CLOUD)
# 7 PII masking boundaries
add("PII masking at cloud sync boundaries (results sync, backup, logs, crash)", B_PII, "PII masking + telemetry sync", "abuse", ["src/tabs/base_tab.py", "src/app/app_automation.py", "src/app/app_license.py", "src/tabs/history_manager.py", "src/utils.py", "src/error_context.py"], DA_CORE, EXC_WEB + EXC_CLOUD, DATA)
add("PII masking at cloud sync boundaries (results sync, backup, logs, crash)", B_PII, "PII masking + telemetry sync", "chain", ["src/tabs/base_tab.py", "src/app/app_automation.py", "src/app/app_license.py", "src/tabs/history_manager.py", "src/utils.py", "src/error_context.py"], DA_CORE, EXC_WEB + EXC_CLOUD, DATA)
# 8 Cloud backup/restore
add("User-data backup push/pull/restore (config+staff maps write-back)", B_PII, "Cloud backup", "logic", ["src/app/app_license.py"], DA_CORE, EXC_WEB, DATA)
add("User-data backup push/pull/restore (config+staff maps write-back)", B_PII, "Cloud backup", "file", ["src/app/app_license.py"], DA_CORE, EXC_WEB, DATA)
# 9 Cloud file manager
add("Cloud file manager client (upload/download paths, whatsapp-send)", B_FILE, "Cloud file manager", "file", ["src/tabs/file_management_tab.py", "src/tabs/demand_tab.py", "src/tabs/musterroll_gen_tab.py"], DA_CORE, EXC_WEB, DATA)
add("Cloud file manager client (upload/download paths, whatsapp-send)", B_FILE, "Cloud file manager", "abuse", ["src/tabs/file_management_tab.py", "src/tabs/demand_tab.py", "src/tabs/musterroll_gen_tab.py"], DA_CORE, EXC_WEB, DATA)
# 10 Local IPC
add("Single-instance loopback socket 60123/60124", B_LOCL, "Local IPC", "access", ["main_app.py", "lite_app.py"], DK_CORE, EXC_WEB + EXC_DATA + EXC_CLOUD, DESK)
# 11 Browser manager
add("Managed browser launch (remote-debugging-port, profile dirs, URL args)", B_LOCL, "Browser manager", "injection", ["src/managers/browser_manager.py", "src/tabs/login_automation_tab.py"], DK_CORE, EXC_WEB + EXC_DATA + EXC_CLOUD, DESK)
# 12 File sinks / path handling in tabs
add("Report/export file sinks (downloads dir, startfile/open, zip/csv imports)", B_LOCL, "Tab file handling", "file", ["src/tabs/base_tab.py", "src/tabs/musterroll_gen_tab.py", "src/tabs/pdf_merger_tab.py", "src/utils.py"], DK_CORE, EXC_WEB + EXC_DATA + EXC_CLOUD, DESK)
add("Report/export file sinks (downloads dir, startfile/open, zip/csv imports)", B_LOCL, "Tab file handling", "abuse", ["src/tabs/base_tab.py", "src/tabs/musterroll_gen_tab.py", "src/tabs/pdf_merger_tab.py", "src/utils.py"], DK_CORE, EXC_WEB + EXC_DATA + EXC_CLOUD, DESK)
# 13 CI/release workflow
add("GitHub Actions release workflow (triggers, permissions, artifact trust)", B_CFG, "CI release pipeline", "obvious", [".github/workflows/release.yml"], SC_CORE, EXC_WEB + EXC_DATA + EXC_CLOUD, SC)
add("GitHub Actions release workflow (triggers, permissions, artifact trust)", B_CFG, "CI release pipeline", "chain", [".github/workflows/release.yml"], SC_CORE, EXC_WEB + EXC_DATA + EXC_CLOUD, SC)
add("GitHub Actions release workflow (triggers, permissions, artifact trust)", B_CFG, "CI release pipeline", "injection", [".github/workflows/release.yml"], SC_CORE, EXC_WEB + EXC_DATA + EXC_CLOUD, SC)
# 14 Packaging whitelist
add("Packaging whitelist + PyInstaller specs + build scripts", B_CFG, "Packaging", "obvious", ["scripts/build_update.py", "scripts/build_windows.bat", "scripts/build_macos.sh", "scripts/build_locales.py", ".gitignore"], SC_CORE, EXC_WEB + EXC_DATA + EXC_CLOUD, SC)
# 15 Dependencies
add("Third-party dependency floors (requirements.txt, unclaimed deps)", B_CFG, "Dependencies", "obvious", ["requirements.txt", "requirements-dev.txt"], SC_CORE, EXC_WEB + EXC_DATA + EXC_CLOUD, SC)
# 16 Repo hygiene / secrets
add("Repo hygiene (committed secrets, .env, .gitignore coverage)", B_CFG, "Repo hygiene", "obvious", [".gitignore", "run_server.py", "requirements.txt"], SC_CORE, EXC_WEB + EXC_DATA + EXC_CLOUD, SC)
# 17 Wildcard / boring code
add("Wildcard sweep (sound manager, icon manager, ui_components, i18n, onboarding)", B_LOCL, "Misc subsystems", "wild", ["src/managers/sound_manager.py", "src/managers/icon_manager.py", "src/ui_components.py", "src/i18n.py", "src/tabs/whatsapp_chat_tab.py"], DK_CORE, EXC_WEB + EXC_DATA + EXC_CLOUD, DESK)
# 18 Crash reporter + OTP/OAuth flows
add("Crash reporter upload payload + OTP/OAuth activation flows", B_NET, "Crash/OAuth flows", "crypto", ["src/utils.py", "src/app/app_license.py"], WB_CORE, EXC_DATA + EXC_CLOUD, WEB)
add("Crash reporter upload payload + OTP/OAuth activation flows", B_NET, "Crash/OAuth flows", "abuse", ["src/utils.py", "src/app/app_license.py"], WB_CORE, EXC_DATA + EXC_CLOUD, WEB)

units.sort(key=lambda u: u["coverage_id"])
ids = [u["coverage_id"] for u in units]
assert len(ids) == len(set(ids)), "duplicate coverage_id"

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(units, f, indent=1, ensure_ascii=False)
print(f"Wrote {len(units)} units -> {OUT}")
