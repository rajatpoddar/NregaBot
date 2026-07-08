<div align="center">
  <img src="https://nregabot.com/logo.png" alt="NREGA Bot Logo" width="96"/>
</div>

# <div align="center">NREGA Bot</div>

<p align="center">
  <b>v3.0.3 | NMMS Daily Attendance Automation Live!</b><br />
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

## 🆕 What's New in v3.0.3

- 🚀 **New: NMMS Daily Attendance** — Fully automated attendance scraping from the NMMS portal. Scrapes panchayat list, MR details, worker attendance, group photos, timestamps, and geo-coordinates.
- 📊 **NMMS Professional Excel Report** — Multi-sheet report with MR Summary, Workers Detail, and Block Overview with styled headers and auto-sized columns.
- 📷 **Group Photo Download** — Auto-downloads Photo-1 and Photo-2 for each MR by clicking the 'large image' link directly on the portal.
- ☑️ **Select All Panchayats** — Instantly select or deselect all panchayats with a single click.
- 🐞 **Fix — Header Row Filter** — Column-number rows (`1 2 3 4 5`) no longer appear in Block Overview or MR list.
- 🐞 **Fix — Timestamp Parsing** — Taken, Uploaded, Geo Coordinates, Taken By, and Designation now correctly extracted from the portal's multi-line cell format.
- 🐞 **Fix — Navigation** — All portal navigation is now click-based (no direct URL access) to avoid 'Access Denied' errors on the government portal.

---

## 🚀 Key Features

An intuitive, tab-based interface organized for efficiency:

### 🔹 General & Application
- 🚀 **Background Mode** - Automations continue running smoothly even if you minimize the browser window.
- ✨ **Retry Failed Button** - Quickly re-process only the failed entries in any automation with a single click.
- ✨ **Microsoft Edge Support** - Launch and use Microsoft Edge directly from the dashboard for all automations.
- 🚀 **Smart Updates** - New Loader Architecture ensures future updates are instant and lightweight (KB size).
- 📅 **Calendar UI** - A modern calendar popup across all automations with colored indicators for Sundays/Mondays.
- 🛡️ **Friendly Error Handling** - The app now stops gracefully with a clear message if the browser is closed manually.
- 🚀 **Headless Reporting** - Reports like 'MR Tracking' now run in the background.
- ✨ **Referral Program** - Get 15 days of extra validity when a user you refer purchases their first plan.
- 💳 **Auto-Renewal** - Enable auto-renewal (subscription) from the website.
- ✨ **Device Renaming** - Rename your activated devices from the app or website.
- 🎨 **Dynamic UI** – A modern interface with Dark/Light theme support, Skeleton Loading, and sound effects.
- ✨ **Reseller Panel** - Resellers can view user stats and send email reminders.

### 🏗️ Core NREGA Tasks
- ✨ **Demand Automation** - Demand laborers from a CSV. Supports GP logins, auto-adjusts for 100-day limits.
- 🗑️ **Delete Demand** - Effortlessly delete incorrect demands for single or multiple villages. Smartly handles NREGA portal bugs and auto-recovers.
- ✨ **Work Allocation** - Automatically allocate work.
- 🗂️ **MR Generator** – Automatically generate and download Muster Roll PDFs. Includes a **Merge PDFs** button.
- ✨ **MR Fill** - Automatically fill Muster Rolls. Now supports **Retry Failed** logic.
- ⚙️ **MSR Processor** – Process and save Muster Rolls from the MSR Payment page.
- 📤 **FTO Generation** – Automates FTO verification with a workflow to **Check Pending ABPS Labour**. Now supports older Firefox versions.
- 📋 **Wagelist Automation** – Generate new wagelists and send them for e-FMS payment. Option to **save as PDF**.
- ✨ **Duplicate MR Print** – Find, save as PDF, and print all Muster Rolls. Includes a **Merge PDFs** button.
- 🏁 **Scheme Closing** - Automate the process of closing schemes for completed work.
- 🗑️ **Delete Work Allocation** - Remove work allocations across multiple dates. Improved engine prevents stuck states on blank rows.

### 👷 JE & AE Automation
- ✏️ **eMB Entry** – Automate filling the MB entry page. Supports Professional Export (Excel/PDF) and Retry Logic.
- 🔍 **eMB Verify** – Quickly verify Measurement Book (MB) entries in bulk.

### 📝 Records & Workcode
- 🏗️ **Workcode Generator (Dynamic)** – Create new work codes in bulk by loading categories from the website and reading data from a simple CSV file.
- 🔧 **IF Editor (Dynamic)** – Automate the multi-page IF editing process with a flexible UI and a simple CSV for inputs.
- 🪄 **Add Activity** - Automate the process of adding activities to work codes.
- ✨ **Update Estimated Outcome** – Quickly update the 'Estimated Outcome' for a list of work codes.

### 🛠️ Utilities & Verification
- ⛺ **Sarkar Aapke Dwar** - Bulk entry automation for camps.
- ✨ **Zero MR** - Submit 'Zero MR' for muster rolls. Integrated directly with MR Tracking data.
- ✅ **Jobcard Verification** – Verify job cards for an entire village and automatically upload the correct family photo.
- 💳 **Verify ABPS** – Automate checking worker Aadhaar numbers with NPCI.
- ✨ **Resend Rejected Wagelist** - Automate reprocessing wagelist payments rejected by the bank.
- ✨ **PDF Merger** - A standalone utility to quickly merge multiple selected PDF files.
- ✂️ **Workcode Extractor** – Parse and extract clean lists of work codes.
- 📁 **File Manager** - A built-in cloud file manager to save, organize, and **Share Folders** via links.

### 📊 Reporting
- 📅 **NMMS Daily Attendance (New!)** — Scrape and export daily NMMS attendance data, group photos, and worker details into a professional Excel report.
- ✨ **MR Tracking** - Track MR status in real-time (Headless). Features **Pendency Report (T0-T8)** generation and **Zero MR forwarding**.
- ✨ **Dashboard Report** - Fetch and view comprehensive dashboard reports with full export capabilities.
- ✨ **Issued MR Details** - Fetch all 'e-muster issued' works. Includes **ABPS Pending Demand** scan for blocks.
- 📊 **MIS Reports** - Solves CAPTCHA and downloads multiple MIS reports into a single, multi-sheet Excel file.
- 📈 **Social Audit Reports** - Automates the process of fetching Social Audit issue details.

### 🧠 Smart Tools
- 🚀 **Macro Manager** – The ultimate automation hub. Queue multiple tasks to run sequentially. Supports **Bulk Demand via CSV** file upload.
- ✨ **Login Automation** - One-click auto-login to the NREGA portal.
- ✂️ **Workcode Extractor** – Parse and extract clean lists of work codes from any text.
- 📁 **File Manager** - Cloud file manager to save, organize, and share folders via links.
- ✨ **PDF Merger** - Quickly merge multiple PDF files into one.

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
- **For Windows**: `NREGABot-v3.0.3-Setup.exe`
- **For macOS**: `NREGABot-v3.0.3-macOS.dmg`

### 2️⃣ First-Time Launch & Trial

Download the app and get your 30-day free trial by registering on our website. After registering, you will receive a trial key via email. Activate the app using your registered email or the provided key.

👉 **[Register for Free Trial](https://license.nregabot.com/trial)**

---

## 📘 How to Use

1. Launch NREGA Bot from your applications folder or desktop.
2. From the app's dashboard, click the **"Chrome"** or **"Firefox"** button. This will open a special, controlled browser window.
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

### v3.0.3
- 🚀 New NMMS Daily Attendance tab with full scraping, photo download, and Excel report export
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

---

## 📜 License & Pricing

- **Trial**: This software comes with a 30-day fully-functional free trial upon web registration.
- **License**: After the trial period, a license key is required to continue using the automation features.

Affordable Monthly, Quarterly, Half-Yearly, and Yearly license plans are available. Please visit our website to purchase a key.

👉 **[Get Your License Key](https://license.nregabot.com/buy)**

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

---

## 📌 Overview

**NREGA Bot** is a powerful and intuitive desktop application designed to eliminate the manual, repetitive work involved with the NREGA portal. By automating your most tedious data entry, processing, and verification tasks, NREGA Bot saves you countless hours and reduces manual errors.

The application works by securely controlling a web browser on your computer, allowing you to focus on what matters most.

---

## 🚀 Key Features

An intuitive, tab-based interface organized for efficiency:

### 🔹 General & Application
- 🚀 **Background Mode (New!)** - Automations now continue running smoothly even if you minimize the browser window.
- ✨ **Retry Failed Button (New!)** - Quickly re-process only the failed entries in any automation with a single click.
- ✨ **Microsoft Edge Support** - Launch and use Microsoft Edge directly from the dashboard for all automations.
- 🚀 **Smart Updates** - New Loader Architecture ensures future updates are instant and lightweight (KB size).
- 📅 **Calendar UI** - A modern calendar popup across all automations with colored indicators for Sundays/Mondays.
- 🛡️ **Friendly Error Handling** - The app now stops gracefully with a clear message if the browser is closed manually.
- 🚀 **Headless Reporting** - Reports like 'MR Tracking' now run in the background.
- ✨ **Referral Program** - Get 15 days of extra validity when a user you refer purchases their first plan.
- 💳 **Auto-Renewal** - Enable auto-renewal (subscription) from the website.
- ✨ **Device Renaming** - Rename your activated devices from the app or website.
- 🎨 **Dynamic UI** – A modern interface with Dark/Light theme support, Skeleton Loading, and sound effects.
- ✨ **Reseller Panel** - Resellers can view user stats and send email reminders.

### 🏗️ Core NREGA Tasks
- ✨ **Demand Automation** - Demand laborers from a CSV. Supports GP logins, auto-adjusts for 100-day limits.
- 🗑️ **Delete Demand (New!)** - Effortlessly delete incorrect demands for single or multiple villages. Smartly handles NREGA portal bugs and auto-recovers.
- ✨ **Work Allocation** - Automatically allocate work. 
- 🗂️ **MR Generator** – Automatically generate and download Muster Roll PDFs. Includes a **Merge PDFs** button.
- ✨ **MR Fill** - Automatically fill Muster Rolls. Now supports **Retry Failed** logic.
- ⚙️ **MSR Processor** – Process and save Muster Rolls from the MSR Payment page.
- 📤 **FTO Generation** – Automates FTO verification with a workflow to **Check Pending ABPS Labour**. Now supports older Firefox versions.
- 📋 **Wagelist Automation** – Generate new wagelists and send them for e-FMS payment. Option to **save as PDF**.
- ✨ **Duplicate MR Print** – Find, save as PDF, and print all Muster Rolls. Includes a **Merge PDFs** button.
- 🏁 **Scheme Closing** - Automate the process of closing schemes for completed work.
- 🗑️ **Delete Work Allocation** - Remove work allocations across multiple dates. Improved engine prevents stuck states on blank rows.

### 👷 JE & AE Automation
- ✏️ **eMB Entry** – Automate filling the MB entry page. **Now supports Professional Export (Excel/PDF)** and Retry Logic. Fixed Work Name selection bug.
- 🔍 **eMB Verify** – Quickly verify Measurement Book (MB) entries in bulk.

### 📝 Records & Workcode
- 🏗️ **Workcode Generator (Dynamic)** – Create new work codes in bulk by loading categories from the website and reading data from a simple CSV file.
- 🔧 **IF Editor (Dynamic)** – Automate the multi-page IF editing process with a flexible UI and a simple CSV for inputs.
- 🪄 **Add Activity** - Automate the process of adding activities to work codes.
- ✨ **Update Estimated Outcome** – Quickly update the 'Estimated Outcome' for a list of work codes.

### 🛠️ Utilities & Verification
- ⛺ **Sarkar Aapke Dwar** - Bulk entry automation for camps. Now supports 'Applicant/Scheme Remarks' columns.
- ✨ **Zero MR** - Submit 'Zero MR' for muster rolls. Integrated directly with MR Tracking data.
- ✅ **Jobcard Verification** – Verify job cards for an entire village and automatically upload the correct family photo.
- 💳 **Verify ABPS** – Automate checking worker Aadhaar numbers with NPCI.
- ✨ **Resend Rejected Wagelist** - Automate reprocessing wagelist payments rejected by the bank.
- ✨ **PDF Merger** - A standalone utility to quickly merge multiple selected PDF files.
- ✂️ **Workcode Extractor** – Parse and extract clean lists of work codes (Bug fixes applied).
- 📁 **File Manager** - A built-in cloud file manager to save, organize, and **Share Folders** via links.

### 📊 Reporting
- ✨ **MR Tracking** - Track MR status in real-time (Headless). Features **Pendency Report (T0-T8)** generation and **Zero MR forwarding**.
- ✨ **Dashboard Report** - Fetch and view comprehensive dashboard reports with full export capabilities.
- ✨ **Issued MR Details** - Fetch all 'e-muster issued' works. Now includes **ABPS Pending Demand** scan for blocks.
- 📊 **MIS Reports** - Solves CAPTCHA and downloads multiple MIS reports into a single, multi-sheet Excel file.
- 📈 **Social Audit Reports** - Automates the process of fetching Social Audit issue details.

### 🧠 Smart Tools (New!)
- 🚀 **Macro Manager** – The ultimate automation hub. Queue multiple tasks to run sequentially. Now supports **Bulk Demand via CSV** file upload.
- ✨ **Login Automation** - One-click auto-login to the NREGA portal.
- ✂️ **Workcode Extractor** – Parse and extract clean lists of work codes from any text.
- 📁 **File Manager** - Cloud file manager to save, organize, and share folders via links.
- ✨ **PDF Merger** - Quickly merge multiple PDF files into one.

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
- **For Windows**: `NREGABot-v3.0.3-Setup.exe`
- **For macOS**: `NREGABot-v3.0.3-macOS.dmg`

### 2️⃣ First-Time Launch & Trial

Download the app and get your 30-day free trial by registering on our website. After registering, you will receive a trial key via email. Activate the app using your registered email or the provided key.

👉 **[Register for Free Trial](https://license.nregabot.com/trial)**

---

## 📘 How to Use

1. Launch NREGA Bot from your applications folder or desktop.
2. From the app's dashboard, click the **"Chrome"** or **"Firefox"** button. This will open a special, controlled browser window.
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

## 📜 License & Pricing

- **Trial**: This software comes with a 30-day fully-functional free trial upon web registration.
- **License**: After the trial period, a license key is required to continue using the automation features.

Affordable Monthly, Quarterly, Half-Yearly, and Yearly license plans are available. Please visit our website to purchase a key.

👉 **[Get Your License Key](https://license.nregabot.com/buy)**

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