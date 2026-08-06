<div align="center">
  <img src="https://nregabot.com/logo.png" alt="NREGA Bot Logo" width="96"/>
</div>

# <div align="center">NREGA Bot</div>

<p align="center">
  <b>v3.1.2 | Powerful NREGA Automation — Windows, macOS & Lite</b><br />
  <a href="https://nregabot.com/#downloads"><strong>Download Now »</strong></a><br /><br />
  <a href="https://nregabot.com/how-to-use.html">View Instructions</a> ·
  <a href="https://nregabot.com/contact.html">Report Bug</a> ·
  <a href="https://nregabot.com/#faq">Request Feature</a>
</p>

---

## 📌 Overview

**NREGA Bot** is a powerful and intuitive desktop application designed to eliminate the manual, repetitive work involved with the NREGA portal. By automating your most tedious data entry, processing, and verification tasks, NREGA Bot saves you countless hours and reduces manual errors.

The application works by securely controlling a web browser on your computer, allowing you to focus on what matters most.

---

## 🆕 What's New in v3.1.2

- 🐞 **Fix (About tab crash):** Resolved the 'humanize module missing' error — About tab and File Manager no longer crash if the humanize package isn't bundled.
- ▶️ **Running Automation Indicator:** The footer now shows exactly which automation is currently running (e.g. `▶ Running: MR Tracking`) next to the status.
- 🖥️ **Footer Layout:** Cleaner `© 2025 NREGA Bot | ▶ Running: X | Status: ...` footer ordering.

## 🆕 What's New in v3.1.1

- 🐞 **Fix (Pending Bills):** Resolved the missing `beautifulsoup4` library — the Pending Bills scraper was failing because bs4 was not bundled with the app.
- ⚡ **Smart Hash Updates:** Added SHA-256 verified same-version updates — small code fixes can now be delivered instantly without a version bump, with automatic download-corruption detection.

## 🆕 What's New in v3.1.0

- 🚀 **New Settings Panel:** Completely redesigned Settings tab with cloud backup & restore, one-time announcement popups, and a Location Fix wizard that validates your State/District against server records.
- 🚀 **New Automation (Pending Bills):** Added the Pending Bills automation tab to track and process pending bills efficiently.
- 💬 **WhatsApp Integration:** Send files and messages directly to WhatsApp (Evolution API) with a dedicated WhatsApp chat tab + automated notifications on task completion.
- 📍 **Auto-Fetch Locations:** State/District/Block now auto-fetch from the server with a filtered location hierarchy — no more manual spelling errors.
- ☁️ **Cloud Sync:** User data & settings now sync to your account — activate on any PC or restore after factory reset in one click.
- 🔐 **Security Fix:** License key is no longer exposed in URLs.
- 🏠 **Home Page Fix:** Blocked/premium tabs can no longer be opened from the Home page shortcuts.
- 🌐 **Browser Launch:** Default launch URLs are now centralized in config — added vbgramg.nregabot.com at startup.
- 🖥️ **UI Overhaul:** Improved layouts across all automation tabs; dashboard & issued-report fixes; standardized logs and status output.
- 📊 **Report Fixes:** MIS reports fixed and Excel result output standardized.
- ⚡ **All Villages Option:** Added 'All Villages' support in multiple automation tabs for faster bulk processing.
- 🔄 **Beta Builds:** Added beta portable build support with auto-update bypass for testing.

---

## 🚀 Key Features

An intuitive, tab-based interface organized into categories for efficiency:

### 🔹 General & Application
- 🚀 **Background Mode** - Automations continue running smoothly even if you minimize the browser window.
- ✨ **Retry Failed Button** - Quickly re-process only the failed entries in any automation with a single click.
- ✨ **Microsoft Edge Support** - Launch and use Microsoft Edge directly from the dashboard for all automations.
- ⚡ **Smart Updates** - Loader Architecture with SHA-256 verified core updates. Small fixes ship instantly (KB size) without re-installing.
- 📅 **Calendar UI** - A modern calendar popup across all automations with colored indicators for Sundays/Mondays.
- 🛡️ **Friendly Error Handling** - The app stops gracefully with a clear message if the browser is closed manually.
- 🚀 **Headless Reporting** - Reports like 'MR Tracking' run in the background so you can keep working.
- ✨ **Referral Program** - Get 15 days of extra validity when a user you refer purchases their first plan.
- 💳 **Auto-Renewal** - Enable auto-renewal (subscription) from the website.
- ✨ **Device Renaming** - Rename your activated devices from the app or website.
- 🎨 **Dynamic UI** – A modern interface with Dark/Light theme support, Skeleton Loading, and sound effects.
- ☁️ **Cloud Sync & Backup** - Backup and restore your data and settings, or move to a new PC in one click.
- 🏠 **Activity Log** - Automatically track your daily tasks with timestamps and Panchayat/Block context.
- ⚙️ **Full Settings Panel** - Sound, minimize-on-start, WhatsApp notifications, cloud backup, and more in one place.

### 🏗️ MR & Wage Management
- ✨ **Demand Automation** - Demand laborers from a CSV. Supports GP logins, auto-adjusts for 100-day limits.
- 🗑️ **Delete Demand** - Effortlessly delete incorrect demands for single or multiple villages. Smartly handles NREGA portal bugs and auto-recovers.
- ✨ **Work Allocation** - Automatically allocate work, and remove allocations across multiple dates.
- 🗂️ **Muster Roll Generator** – Automatically generate and download Muster Roll PDFs. Includes a **Merge PDFs** button.
- 👥 **Mate/Mistri MR** – Generate skilled/semi-skilled muster rolls for Mate & Mistri workers.
- ✨ **MR Fill** - Automatically fill Muster Rolls with smart holiday handling.
- ⚙️ **MR Payment (MSR)** – Process and save Muster Rolls from the MSR Payment page.
- 📤 **FTO Generation** – Automates FTO verification with a workflow to **Check Pending ABPS Labour**. Supports older Firefox versions.
- 📋 **Generate Wagelist / Send Wagelist** – Generate new wagelists and send them for e-FMS payment.
- ✨ **Duplicate MR Print** – Find, save as PDF, and print all Muster Rolls. Includes a **Merge PDFs** button.
- 🧱 **Material Entry** – Dynamic material rows (up to 15), saved material profiles, live GST totals, and CSV export.
- 🏁 **Scheme Closing** - Automate the process of closing schemes for completed work.
- ✅ **Physical Complete** - Mark physical completion for work codes and auto-forward to Scheme Closing.

### 👷 JE & AE Automation
- ✏️ **eMB Entry** – Automate filling the MB entry page. Supports Professional Export (Excel/PDF) and Retry Logic.
- 🔍 **eMB Verify** – Quickly verify Measurement Book (MB) entries in bulk.

### 📝 Records & Workcode
- 🏗️ **Workcode Generator (Dynamic)** – Create new work codes in bulk by loading categories from the website and reading data from a simple CSV file.
- 🔧 **IF Editor (Dynamic)** – Automate the multi-page IF editing process with a flexible UI and a simple CSV for inputs.
- 🪄 **Add Activity** - Automate the process of adding activities to work codes.
- ✨ **Update Estimated Outcome** – Quickly update the 'Estimated Outcome' for a list of work codes.

### 🛠️ Utilities & Verification
- ⛺ **Sarkar Aapke Dwar** - Bulk entry automation for camps, including Applicant/Scheme Remarks.
- 📊 **SAD Update Status** - Update status for Sarkar Aapke Dwar applications.
- ✨ **Zero MR** - Submit 'Zero MR' for muster rolls. Integrated directly with MR Tracking data.
- ✅ **Jobcard Verification** – Verify job cards for an entire village and automatically upload the correct family photo.
- 💳 **Verify ABPS** – Automate checking worker Aadhaar numbers with NPCI.
- ✨ **Resend Rejected Wagelist** - Automate reprocessing wagelist payments rejected by the bank.
- 🗑️ **Delete Applicant** – Bulk-delete jobcard applicants via eKYC Report Excel or CSV upload.
- ✨ **PDF Merger** - A standalone utility to quickly merge multiple selected PDF files.
- ✂️ **Workcode Extractor** – Parse and extract clean lists of work codes.

### 📊 Reporting
- 💸 **Pending Bills** – Scrape unpaid Muster Rolls & Bills from the MGNREGA Liability & Expenditure report into a professional color-coded Excel sheet.
- 📅 **NMMS Daily Attendance** — Scrape and export daily NMMS attendance data, group photos, and worker details into a professional Excel report.
- ✨ **MR Tracking** - Track MR status in real-time (Headless). Features **Pendency Report (T0-T8)** generation and **Zero MR forwarding**.
- ✨ **Dashboard Report** - Fetch and view comprehensive dashboard reports with full export capabilities.
- ✨ **Issued MR Details** - Fetch all 'e-muster issued' works. Includes **ABPS Pending Demand** scan for blocks.
- 📊 **MIS Reports** - Solves CAPTCHA and downloads multiple MIS reports into a single, multi-sheet Excel file.
- 📈 **Social Audit Reports** - Automates the process of fetching Social Audit issue details.
- 🆔 **eKYC Report** - Generate professional eKYC pending reports.

### 🧠 Smart Tools
- 🚀 **Macro Manager** – The ultimate automation hub. Queue multiple tasks to run sequentially. Supports **Bulk Demand via CSV** file upload.
- ✨ **Login Automation** - One-click auto-login to the NREGA portal.
- 💬 **WhatsApp Chat** - Send files and messages directly to WhatsApp, plus automatic completion notifications.
- 📁 **File Manager** - A built-in cloud file manager to save, organize, and **Share Folders** via links.

---

## 🛠 Prerequisites

You only need to have a supported web browser installed on your system:

- 🌐 **Google Chrome (Recommended)**
- 🔵 **Microsoft Edge**
- 🦊 **Mozilla Firefox**

---

## ⚙️ Installation & Setup

### 1️⃣ Download the Application

Download the latest version from the official website:

- Website: [nregabot.com/#downloads](https://nregabot.com/#downloads)
- **For Windows**: `NREGABot-v3.1.2-Setup.exe`
- **For macOS**: `NREGABot-v3.1.2-macOS.dmg`
- **Lite (Low-end PCs)**: `NREGABot-Lite-v3.1.2-Setup.exe` or portable ZIP

### 2️⃣ First-Time Launch & Trial

Download the app and get your 30-day free trial by registering on our website. After registering, you will receive a trial key via email. Activate the app using your registered email or the provided key.

👉 **[Register for Free Trial](https://nregabot.com/trial)**

---

## 📘 How to Use

1. Launch NREGA Bot from your applications folder or desktop.
2. From the app's dashboard, click the **"Chrome"**, **"Edge"**, or **"Firefox"** button. This will open a special, controlled browser window.
3. In that new browser window, log in to the NREGA portal as you normally would.
4. Navigate to the tab in the NREGA Bot app for the task you want to automate.
5. Fill in the required details (e.g., Panchayat name, work codes).
6. Click **"Start Automation"** and watch the magic happen!
7. You can monitor progress in the Logs & Status area and stop the process at any time with the **Stop** button.

---

## 📸 Screenshots

<img src="https://nregabot.com/assets/Muster_Roll_Generator.png" width="700"/><br/>
<em>Modern, intuitive dashboard with powerful features.</em>

<br/><br/>

<img src="https://nregabot.com/assets/Duplicate_MR_Print.png" width="700"/><br/>
<em>The new Duplicate MR Print feature in action.</em>

---

## 📜 Changelog

### v3.1.2
- 🐞 Fixed 'humanize module missing' crash in the About tab (built-in fallback + bundled in all builds)
- ▶️ Footer now shows which automation is running (e.g. `▶ Running: MR Tracking`)
- 🖥️ Footer reordered: `© 2025 NREGA Bot | ▶ Running: X | Status: ...`
- 📘 Added `CODEBASE.md` developer guide documenting the app architecture

### v3.1.1
- 🐞 Fixed missing `beautifulsoup4` library in the Pending Bills scraper
- ⚡ Smart hash-based updates: same-version code fixes ship instantly with SHA-256 integrity verification

### v3.1.0
- 🚀 New Settings Panel with cloud backup & restore and Location Fix wizard
- 🚀 New Pending Bills automation (unpaid MR/Bill scraping → Excel)
- 💬 WhatsApp Integration: dedicated chat tab + automated completion notifications
- 📍 Auto-Fetch Locations from the server (State/District/Block)
- ☁️ Cloud Sync for user data & settings
- 🔐 Security fix: license key no longer exposed in URLs
- 🖥️ UI overhaul across all automation tabs; dashboard & issued-report fixes
- ⚡ 'All Villages' option in multiple automations for faster bulk processing
- 🔄 Beta portable builds with auto-update bypass

### v3.0.7
- 🧹 Repository cleanup and optimized release pipeline

### v3.0.6
- 🚀 Delete Applicant overhaul — accepts eKYC Report Excel files directly
- 🚀 MB Entry auto-processes ALL works when no work codes are provided

### v3.0.5
- 🐞 Fixed Physical Complete pointing to the wrong portal URL (now VB-G-RAM-G)

### v3.0.4
- 🐞 Fixed Mate/Mistri MR generation automation
- 🐞 Fixed NMMS Daily Attendance automation failing to complete (navigation & scraping fixes)

### v3.0.3
- 📅 NMMS Daily Attendance (initial release) with Professional Excel Report & group photo download
- ☑️ Select All / Clear All panchayat selection
- 🐞 Fixed header row appearing in Block Overview and MR list
- 🐞 Fixed timestamp parsing (Taken, Uploaded, Geo, Taken By, Designation)
- 🐞 Fixed all navigation to use click-based flow (no Access Denied errors)

### v3.0.2
- 🌐 VB-G-RAM-G portal support across all automations
- 🐞 Fixed blank page in MR PDFs (Chrome)
- 🐞 Fixed Delete Demand village dropdown wait issue
- ✨ Demand tab UI overhaul with Quick-Select JC Bar

### v3.0.1
- 🚀 New Physical Complete automation
- ⚡ Auto-forward to Scheme Closing after physical completion
- 🕵️ MR Tracking updated to FY 2026-2027

### v3.0.0
- ✨ Material Entry overhaul — dynamic rows, material profiles, live totals

### v2.9.x
- 🚀 Macro Manager, Zero MR, Issued MR Details, PDF Merger, Work Allocation, eKYC integration and dozens of stability fixes

---

## 📜 License & Pricing

- **Trial**: This software comes with a 30-day fully-functional free trial upon web registration.
- **License**: After the trial period, a license key is required to continue using the automation features.

Affordable Monthly, Quarterly, Half-Yearly, and Yearly license plans are available. Please visit our website to purchase a key.

👉 **[Get Your License Key](https://nregabot.com/buy)**

🎉 **New Referral Program!** Refer a new user with your code (from your 'My Account' page) and get 15 extra days when they buy their first plan!

---

## 📞 Support

For questions, bug reports, or feature requests, please contact us:

- **Email**: [nregabot@gmail.com](mailto:nregabot@gmail.com)
- **WhatsApp Community**: [Join our Group](https://nregabot.com/contact.html)

---

## ⚠️ Disclaimer

This tool automates interactions with a live government website. The author is not responsible for any changes to the NREGA portal that may cause the application to malfunction.

> This software is provided "AS IS" without warranty of any kind. Always double-check automated data for accuracy.

---

## 🧑‍💻 Author

**Rajat Poddar**
🔗 [GitHub Profile](https://github.com/rajatpoddar)
