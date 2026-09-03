
#### NREGA Bot · Phase 1 companion app · Design contract v1

# Android companion app for the people who run MGNREGA paperwork.
Hi-fi screens for all eleven in-scope surfaces with their loading, empty, error, offline, expired and quota-full states — plus the written spec, flows, screen → API map, technical blueprint and open decisions your engineers implement against.

#### Foundation
Material 3 on Jetpack Compose, re-themed with the §4.1 brand tokens. Flat treatment: 6 dp buttons, 8 dp cards, 12 dp sheet tops, tonal and outline differentiation instead of shadow.

#### Copy
Hindi-first in every mock, English as the secondary line where a term is unavoidable (नवीनीकरण — Renewal). Five locales via resource files; nothing hardcoded.

#### Not in here
No Kotlin. No bot execution, no admin surfaces, no Play Billing. Every endpoint named below is verified in §5 of the brief; anything invented is marked NEW.

#### Before the screens — what I assumed

##

## Six assumptions. Correct any one and I'll rework the screens it touches.
**1. License key is the login.** Renu has the key on the desktop and often has no working email. Key entry ships in v0.1; email+OTP is designed but gated behind a NEW mobile session endpoint. Full trade-off in H1.
**2. An expired license keeps the app readable.** Files stay viewable and downloadable, support stays open, renew is the only prominent action. Losing file access at expiry would break trust at the worst moment. See D3.
**3. Bottom navigation, four destinations.** Home · Files · Activity · Account. Support, notifications and settings hang off Home and Account. A drawer costs a hidden gesture Renu has no reason to discover.
**4. WhatsApp send happens on the server.** The phone posts file ids and a number to `/files/api/whatsapp-send`; it never opens WhatsApp with an attachment. Local share-sheet fallback only after a download completes.
**5. Storage is the upsell, expiry is the retention risk.** Both get a persistent home surface, not a modal. Quota nags appear at 90% and block only at 100%.
**6. Every screen has a last-known cached read.** Offline shows stale data with a timestamp instead of an error. Only writes queue; reads never block on the network.
The one metric this app should move: **on-time renewals** — share of licenses renewed before expiry date rather than after a lapse. Everything on Home is arranged around that number. Support deflection is the secondary metric, measured as chat threads opened per active license per month.

#### A. Product spec

##

## Goal, priorities, metric
Renu runs muster rolls from the Panchayat office desktop, then spends half her week in the field. The phone app is the place she confirms her license is alive, pulls a report she generated yesterday and sends it to a Secretary on WhatsApp, and pays a renewal without waiting to get back to the desktop. It never runs the bot.

#### Must have — v0.1 beta
- Login (license key) + secure session
- Home: plan, expiry countdown, storage gauge
- Files: browse, view, download, WhatsApp send
- Renew via server-created Razorpay order
- Offline cached reads + retry everywhere

#### Should have — v1.0
- Storage upgrade upsell at 90% / 100%
- Devices: rename, remove, slots
- Activity feed with day grouping
- Support chat with offline outbox
- Notification inbox + FCM push
- Language switcher, dark theme

#### Later
- Email+OTP login (needs backend)
- Upload from phone camera roll
- Public share-link management
- Merged-PDF creation on phone
- Biometric unlock
- Field data capture, remote job queue (out of scope, modules left open)

#### B. Information architecture

##

## Four thumb destinations, everything else one tap deep
Bottom navigation wins for this user for three reasons. It is permanently visible, so there is nothing to learn or discover. It sits in the thumb arc of a 5 inch phone held one-handed while standing at a worksite. And it survives translation into Kannada and Bengali, where a label can double in width, because each item gets an icon above short text rather than a single line.
Support and notifications are deliberately *not* destinations. They are reached from a persistent app-bar row on Home, where they read as help rather than as features to explore.
Every route below is reachable in at most three taps from cold launch.
Splash / license pre-check
├─ Login  · key entry ▸ OTP (later)
└─ Shell (bottom nav)
   ├─ 1 Home
   │  ├─ License status card ▸ Buy / Renew
   │  ├─ Storage gauge ▸ Storage upgrade
   │  ├─ Quick actions (4)
   │  ├─ Notifications inbox
   │  └─ Support chat ▸ FAQ
   ├─ 2 Files
   │  ├─ Folder ▸ Folder ▸ File
   │  ├─ File actions sheet
   │  ├─ Send to WhatsApp
   │  ├─ Upload picker + permission
   │  └─ Downloads / progress
   ├─ 3 Activity
   │  └─ Day groups · filter
   └─ 4 Account
      ├─ Plan & billing history
      ├─ Devices ▸ rename / remove
      ├─ Settings ▸ language · theme
      │  · notifications · about
      └─ Logout / switch license
ScreenPurposeKey contentPrimary actionReached from**Splash**Decide session vs login before any UI flashesBrand mark, one status lineNone (auto)Cold launch**Login**Bind the phone to a licenseKey field, help link, paste affordanceActivateSplash, logout**Home**Answer "am I safe?" in two secondsStatus card, countdown, storage gauge, 4 quick actions, latest filesRenew (when relevant)Nav 1, notification tap**Files**Find and send yesterday's outputBreadcrumb, folders, files with size + date, searchSend to WhatsAppNav 2, Home quick action**Buy / Renew**Take money safelyServer-quoted plan + price, coupon, expiry mathPayHome card, expiry notification**Storage upgrade**Unblock an uploadCurrent usage, tiers from server, priceUpgradeGauge, 90%/100% banner, failed upload**Devices**Free a slot for a new phone or PCDevice list, slots used, last seenRemove deviceAccount**Activity**Prove the desktop work landedDay groups, task name, counts, statusNone (read)Nav 3**Support chat**Get a human, from anywhereThread, outbox queue, FAQ entrySendHome, Account, error states**Notifications**Hold what push may have missedExpiry, announcement, result itemsOpen targetHome bell**Settings**Language and theme, nothing clever5 locales, theme, notif prefs, versionNoneAccount

#### C. Screen designs

##

## Eleven screens, twenty-eight states
Each screen below is drawn at 360 × 760 dp — the smallest device we support — so nothing here depends on a large display. Touch targets are 48 dp minimum; primary numbers use tabular figures so a countdown does not shift width as it ticks down.

#### Color roles as drawn
Blue **#3B8ED0** = valid, primary action. Amber **#7A5300** on **#FFF0D2** = expiring, quota warning. Red **#B3261E** on **#F9DEDC** = expired, blocked, failure. No fourth accent.

#### Flat, per the mood brief
Cards are a 1 dp outline on **#F9F9FA**, not an elevated surface. The only shadow in the app is the 2 dp lip above a bottom sheet. Buttons are full-width and left-labelled.

#### State legend
Every frame caption names the trigger. Where a state is a variant of the frame beside it, the caption says what changed rather than repeating the whole screen.

#### C1 · Splash + license pre-check

##

## Decide before you draw
The splash holds until `/api/app-config` and the cached session verdict both resolve, capped at 2.5 s. Past the cap we route on cached state and revalidate behind Home — a slow 2G handshake must never look like a broken app. Maintenance and blocked-version are the only two screens allowed to be dead ends.
9:41******
**
NREGA Bot
साथी ऐप
लाइसेंस जाँच रहे हैं…
Checking your license
C1a — Splash, pre-check runningMax 2.5 s. Then route on cache and revalidate silently.
9:41******
**
सर्वर पर काम चल रहा है
Scheduled maintenance
आज शाम 7:30 बजे तक सेवा बंद रहेगी। आपकी फ़ाइलें सुरक्षित हैं। डाउनलोड की गई फ़ाइलें अभी भी खुलेंगी।
Message from server
भुगतान सिस्टम अपग्रेड — 30 Aug
**फिर कोशिश करें**सहायता से बात करें
C1b — Maintenance modeTrigger: `/api/app-config` maintenance flag. Support stays reachable; nothing else does.
9:41******
**
नया अपडेट ज़रूरी है
Update required to continue
यह वर्ज़न 1.0.2 अब काम नहीं करता। नया वर्ज़न 1.1.0 डाउनलोड करें।
Installed1.0.2
Required1.1.0
Size14.2 MB
**अपडेट डाउनलोड करें
APK from nregabot.in · SHA-256 shown before install
C1c — Blocked versionTrigger: current versionCode in `app-config` blocked list. Hard stop, no dismiss.

#### C2 · Login

##

## One field, pasteable, forgiving
The key is 20 characters in four dash-separated blocks. The field auto-uppercases, inserts dashes, strips pasted whitespace, and never hides the value — masking a key the user is reading off a desktop screen only causes typos. Validation is server-side via `POST /api/validate`; the client never guesses whether a key looks real beyond length.
9:41******
**
लाइसेंस की चाबी डालें
Enter your license key
यह चाबी आपके कंप्यूटर के NREGA Bot ऐप में **Settings → License** में दिखती है।
License key
XXXX-XXXX-XXXX-XXXX
4 blocks of 4 · dashes added for you0/16चालू करेंActivate**क्लिपबोर्ड से चिपकाएँ
चाबी नहीं मिल रही?**WhatsApp पर सहायता लें
C2a — Key entry, emptyActivate stays disabled until 16 characters. Paste is a visible button, not a long-press.
9:41******
**
लाइसेंस की चाबी डालें
Enter your license key
License key
NRG7-4K2P-88QT-1MZX
**
यह चाबी 12 Jul 2026 को खत्म हो गई थी
This license expired. Renew to continue, or use a different key.**नवीनीकरण करें**दूसरी चाबी डालें

#### Other server verdicts, same slot
**Invalid** · यह चाबी सही नहीं है। कंप्यूटर से दोबारा देखें।
**Blocked** · यह चाबी बंद कर दी गई है। सहायता से बात करें।
**No slots** · सभी डिवाइस भर गए हैं। पुराना डिवाइस हटाएँ। → C7c
C2b — Rejected keyFour server verdicts, four different next actions. Never one generic "login failed".
9:41******
**ईमेल से लॉगिन
कोड डालें
हमने **renu.g***@gmail.com** पर 6 अंकों का कोड भेजा है
4
9
1
दोबारा भेजें 00:24 मेंResendआगे बढ़ें
**
Wrong code state
कोड सही नहीं है। 2 कोशिश बची हैं।
**इसकी जगह लाइसेंस चाबी डालें
C2c — OTP entry NEW backendNeeds a mobile session-token contract (G2). Designed now, shipped after the endpoint exists.
9:41******
**
लाइसेंस की चाबी डालें
Enter your license key
NRG7-4K2P-88QT-1MZX
**
इंटरनेट नहीं है
चाबी जाँचने के लिए इंटरनेट चाहिए। नेटवर्क आने पर हम अपने आप कोशिश करेंगे।**फिर कोशिश करें
Auto-retry in 8s · attempt 2 of 5
Activation is the one action that cannot be queued offline — it is the only network-required step in the app.
C2d — Login, no connectivityExponential backoff, 5 attempts, key preserved. Nothing else in the app blocks like this.

#### C3 · Home / license dashboard

##

## The countdown is the product
Days remaining is the largest element on the screen because it is the one number that changes behaviour. It reads blue above 15 days, amber at 15 and below, red at zero or past. The storage gauge sits directly under it so the two paid concerns — time and space — are answered in one glance, then quick actions take the four things Renu actually does from the field.
9:41******
नमस्ते, रेणु
Karnataka · Hosakote GP
****
Your plan
Yearly Pro**चालू
118दिन बाकी
Expires 29 Dec 2026 · समाप्ति
क्लाउड जगह**3.1** / 5.0 GB
62% used · 1.9 GB free
**मेरी फ़ाइलेंFiles
**WhatsApp भेजेंSend report
**नवीनीकरणRenew
**सहायताSupport
हाल की फ़ाइलेंसभी देखें
**
**MR_Hosakote_Aug.pdf***1.2 MB · 2 Sep, 6:12 pm***
**
**Payment_File_29Aug.xlsx***318 KB · 29 Aug, 11:04 am***
**होम
**फ़ाइलें
**गतिविधि
**खाता
C3a — Home, license healthyCountdown blue. Renew present as a quick action, not a banner.
9:41******
****
**होम
**फ़ाइलें
**गतिविधि
**खाता
C3b — First-load skeletonShown only when there is no cache. With cache we render stale data instantly and refresh in place — no skeleton flash.
9:41******
नमस्ते, रेणु
Karnataka · Hosakote GP
****
Your plan
Yearly Pro**खत्म हो रहा
7दिन बाकी
Expires 10 Sep 2026
समय खत्म होने पर बॉट काम करना बंद कर देगा। फ़ाइलें और सहायता चालू रहेंगी।**अभी नवीनीकरण करें₹1,499
क्लाउड जगह**3.1** / 5.0 GB
**मेरी फ़ाइलें
**WhatsApp भेजें
**पिछले भुगतान
**सहायता
**
आपके प्लान पर **छूट** लागू है — 15 Sep तक
**होम
**फ़ाइलें
**गतिविधि
**खाता
C3c — Expiring, 15 days or fewerCard turns amber, Renew becomes the in-card primary with the server-quoted price. Storage demotes to a strip.
9:41******
**ऑफ़लाइन · 2 Sep, 7:40 pm का डेटा
नमस्ते, रेणु
Karnataka · Hosakote GP
****
Your plan
Yearly Pro**खत्म
14दिन पहले खत्म हुआ
Expired 20 Aug 2026
कंप्यूटर पर बॉट बंद है। यहाँ फ़ाइलें देखना, डाउनलोड और सहायता चालू है।**नवीनीकरण करें₹1,499
**मेरी फ़ाइलेंRead-only
**सहायताSupport
**अपलोडLocked
**WhatsAppLocked
नवीनीकरण के बाद सब कुछ अपने आप चालू हो जाएगा। कोई फ़ाइल नहीं हटेगी।
**होम
**फ़ाइलें
**गतिविधि
**खाता
C3d — Expired + offline, dark themeTwo states at once: stale-data bar at top, expired card below. Writes locked, reads intact.

#### C4 · Cloud files

##

## Find yesterday's PDF, send it, move on
Files is a single list that shows folders above files, with a breadcrumb rather than a back-stack the user has to remember. Every row carries size and date because on a shared license the file name alone is rarely enough. The row overflow opens an actions sheet; long-press starts multi-select for the WhatsApp send, which is the one action Renu performs standing in a field.
9:41******
मेरी फ़ाइलें
****
Home**Muster Rolls**Aug 2026
**
3.1 / 5.0 GB इस्तेमाल · 62%
**
**MR — पहला पखवाड़ा***14 files · 22.4 MB***
**
**MR — दूसरा पखवाड़ा***9 files · 15.1 MB***
**
**MR_Hosakote_Aug.pdf***1.2 MB · 2 Sep, 6:12 pm***
**
**ZeroMR_Aug_Final.pdf***840 KB · 1 Sep, 4:55 pm***
**
**Payment_File_29Aug.xlsx***318 KB · 29 Aug, 11:04 am***
**
**JobCard_Verify_Aug.pdf***2.6 MB · 27 Aug, 9:30 am*डाउनलोड हो गई**
**नया
**होम
**फ़ाइलें
**गतिविधि
**खाता
C4a — Folder contentsFolders first, then files newest-first. Downloaded files carry a persistent chip so she knows what already works offline.
9:41******
मेरी फ़ाइलें
****
**
MR_Hosakote_Aug.pdf
1.2 MB · PDF · 2 Sep, 6:12 pm
**
**देखें***Open PDF viewer*
**
**WhatsApp पर भेजें***Server sends it for you*
**
**फ़ोन में डाउनलोड***Works offline after this*
**
**लिंक बनाएँ***Public share link*
**
**दूसरे फ़ोल्डर में डालें***Move NEW endpoint*
**
**हटाएँ***Asks to confirm*
C4b — File actions sheetSix actions, each with a plain-language subtitle. Rename and Move need NEW endpoints — see G2.
9:41******
**3 चुनी गईं4.2 MB
**
**MR_Hosakote_Aug.pdf***1.2 MB*
**
**ZeroMR_Aug_Final.pdf***840 KB*
**
**JobCard_Verify_Aug.pdf***2.6 MB*
WhatsApp पर भेजें
Our server sends the files. WhatsApp does not open.
Mobile number
+9198450 41288
**Secretary**BDO office**Last used
**तीनों PDF को एक फ़ाइल में जोड़ दें**भेजें3 files
C4c — Multi-select → WhatsApp sendMerge checkbox routes through `/files/merge-for-share` first. Number is masked in logs, never in the field.
9:41******
भेजना/लाना**

#### चल रहा है · In progress
**
IMG_20260902_1841.jpg
1.4 / 3.2 MB · 44% · 18s left**
**
JobCard_Verify_Aug.pdf
2.6 MB · 91% · finishing**
**
नेटवर्क धीमा है। ऐप बंद करने पर भी काम चलता रहेगा।
WorkManager keeps transfers alive through screen-off.

#### रुका हुआ · Failed
**
Scan_Muster_p3.pdf
जगह पूरी भर गई — 0 MB बची
जगह बढ़ाएँ**

#### पूरा हुआ · Done today
**
**MR_Hosakote_Aug.pdf***1.2 MB · 6:12 pm***
C4d — Transfers screenOne list for uploads and downloads. Quota failure resolves in place with the upgrade CTA — no dead end.
9:41******
**ऑफ़लाइन · 2 Sep, 7:40 pm की सूची
मेरी फ़ाइलें
****
**
**MR — पहला पखवाड़ा***14 files · needs internet***
**
**JobCard_Verify_Aug.pdf***2.6 MB · on this phone***
**
बाकी फ़ाइलें ऑफ़लाइन नहीं हैं
इंटरनेट आने पर पूरी सूची अपने आप आ जाएगी। डाउनलोड की गई फ़ाइलें अभी भी खुलती हैं।**फिर कोशिश करें

#### Empty folder (online) reads instead
इस फ़ोल्डर में कुछ नहीं है। This folder is empty — files appear here after the desktop bot generates them. **Primary action:** upload from phone.
**होम
**फ़ाइलें
**गतिविधि
**खाता
C4e — Offline list + empty copyCached rows stay tappable; uncached ones dim with a cloud-off marker rather than disappearing.
**Permission states.** Upload asks for media access only at the moment of tapping "Upload from phone", with a one-line rationale sheet: "फ़ोटो चुनने के लिए अनुमति चाहिए — हम बाकी फ़ोटो नहीं देखते।" On denial the sheet offers the system-picker path (Android 11+ document picker needs no permission at all), so a hard "Don't allow" never blocks the feature. Notification permission is requested separately — see C10.

#### C5 · Buy / renew

##

## The server quotes, the client never does
Every number on this screen arrives from `/api/check-renewal-status` and `/api/validate-coupon`. The client posts nothing but a plan id and an optional coupon code; price, discount and the new expiry date are all server-computed and displayed verbatim. After payment the app does not believe itself — it polls `/api/validate` until the license state actually changes.
9:41******
**नवीनीकरण Renewal
Yearly Proआपका प्लान
12 months · 5 GB cloud · 2 device slots · WhatsApp delivery
अभी की समाप्ति10 Sep 2026
नई समाप्ति10 Sep 2027
कूपन कोड · Coupon
GRS200लगाएँ
**कूपन लागू — ₹200 की छूट
प्लान₹1,699
छूट (GRS200)− ₹200
GST included—
कुल देना है₹1,499**भुगतान करें₹1,499
Razorpay · UPI, card, netbanking. रकम सर्वर से आती है, ऐप से नहीं।
C5a — Renewal summaryOld and new expiry dates both shown — the change is the thing being purchased.
9:41******
**Razorpay Checkout**
NREGA Bot · Yearly Pro
₹1,499
Order
order_Q8xR…
**
**UPI***GPay · PhonePe · Paytm***
**
**Card***Debit / credit***
**
**Netbanking***All major banks***
**
भुगतान Razorpay के पेज पर होता है। ऐप आपका कार्ड नहीं देखता।
Recommended: native Razorpay SDK. Trade-off in H2.

#### If she leaves mid-payment
On resume the app shows a "checking your payment" state and polls `/api/verify-payment` then `/api/validate`. Never a second charge, never a client-side success guess.
C5b — Checkout handoffOrder id visible so a support agent can find the payment from a screenshot.
9:41******
**
भुगतान हो गया
आपका लाइसेंस 10 Sep 2027 तक चालू है। कंप्यूटर पर बॉट अगली बार खुलते ही चालू हो जाएगा।
Receipt · pay_Q8xRt71K · ₹1,499होम पर जाएँ
**
भुगतान जाँच रहे हैं
बैंक से पुष्टि आने में 2 मिनट लग सकते हैं। ऐप बंद कर सकती हैं — हम सूचना भेजेंगे।
Pending verification · polling every 5 s for 60 s, then push
**
भुगतान पूरा नहीं हुआ
पैसे नहीं कटे। दोबारा कोशिश करें या दूसरा तरीका चुनें।
फिर कोशिश करें**

#### "Already renewed?" escape hatch**लाइसेंस की स्थिति ताज़ा करें
Forces `/api/validate`, bypassing cache. Present on every payment failure and on Home when a pending payment exists.
C5c — Success · pending · failureThree outcomes drawn together because they share one slot. Pending is a first-class state, not an error.

#### C6 · Storage upgrade

##

## Warn at 90%, block at 100%, sell at the point of failure
9:41******
**क्लाउड जगह
4.9/ 5.0 GB
98% भर गई — 102 MB बची

#### किस चीज़ ने जगह ली · Breakdown
**Muster rolls · PDF**2.8 GB
**Reports · PDF**1.4 GB
**Payment files**0.5 GB
**Photos from phone**0.2 GB**जगह बढ़ाएँ**पुरानी फ़ाइलें हटाएँ
Both paths shown. Deleting is free and we say so — an upsell that hides the free option loses the trust this product runs on.
C6a — Storage detail at 98%From `/files/api/storage-breakdown`. Category bar colours are one hue ramp, no rainbow.
9:41******
**क्लाउड जगह
जगह बढ़ाएँ
Storage upgrade · one-time, valid till your license expiry
+5 GB → कुल 10 GB₹299
+15 GB → कुल 20 GBसबसे ज़्यादा लिया जाता है₹699
+45 GB → कुल 50 GB₹1,499
**
बढ़ी हुई जगह तुरंत मिल जाती है। रुका हुआ अपलोड अपने आप फिर शुरू होगा।**भुगतान करें₹699
Tiers and prices come from the server. `/api/create-storage-order` → pay → `/api/verify-storage-payment` → `/api/update-storage`.
C6b — Upgrade sheetTriggered from the gauge, the 90% banner, or a quota-failed upload. Same sheet, same three server tiers, every time.

#### Where the upsell appears
**80%**Nothing. Gauge fills, no message.**90%**Amber strip on Home and at the top of Files. Dismissible, returns after 7 days.**98%**Amber gauge on the storage screen. Upload still allowed if the file fits.**100%**Upload blocked with the reason and two exits: upgrade, or delete. Desktop sync also pauses — we say that plainly.

#### Microcopy
**90%**
क्लाउड जगह लगभग भर गई — 90%
Cloud storage almost full
**100% on upload**
जगह पूरी भर गई। नई फ़ाइल नहीं जा सकती।
Storage full — this file cannot be uploaded
**After upgrade**
जगह बढ़ गई — अब 20 GB
Storage upgraded to 20 GB
We never delete a user's file to make room, and we never soft-delete silently. If the desktop hits a full quota it queues locally; the phone banner is the only place she learns this.
C6c — Trigger ladderThe rule set behind the two frames on the left.

#### C7 · Devices

##

## Slots, in the language of "which computer is this"
Device management exists because two GRS often share one desktop and Renu will eventually change phones. The list names devices the way she would: the machine at the office, the machine at home, this phone. Removal is destructive from the desktop's point of view, so it confirms with what will actually happen.
9:41******
**डिवाइस
**
2 में से 2 डिवाइस इस्तेमाल में
Device slots on Yearly Pro
**
**Renu ka phone यह डिवाइस***Redmi 9A · Android 11 · अभी सक्रिय***
**
**Panchayat office PC***Windows 10 · v3.2.7 · 2 Sep, 6:40 pm***
**
**DESKTOP-9F2K1L***Windows 10 · last seen 14 Jun***
**
नया कंप्यूटर जोड़ने के लिए उस पर NREGA Bot खोलें और यही चाबी डालें।
Devices register themselves at first heartbeat — nothing to add from here.

#### Row menu
**Rename** · `/api/set-device-name` · optimistic, reverts on failure
**Remove** · `/api/remove-device` · confirm first, never optimistic
**Deactivate license** · `/api/request-deactivation` · Account screen only
**होम
**फ़ाइलें
**गतिविधि
**खाता
C7a — Devices, slots fullA stale device (14 Jun) reads dimmed — the strongest hint about which slot to free.
9:41******
**डिवाइस
**
यह डिवाइस हटाएँ?
DESKTOP-9F2K1L पर NREGA Bot अगली बार खुलते ही बंद हो जाएगा। उस कंप्यूटर की फ़ाइलें नहीं हटेंगी।
Freed slot is usable immediately. Re-adding the same machine later uses a slot again.
हाँ, हटाएँरहने दें
C7b — Remove confirmationSays what breaks on the other machine. Destructive action is red-filled; cancel is the wider target by position.
9:41******
**
सभी डिवाइस भर गए हैं
All device slots are in use
इस फ़ोन को जोड़ने के लिए नीचे से कोई पुराना डिवाइस हटाएँ, या ज़्यादा स्लॉट वाला प्लान लें।
**
**Panchayat office PC***last seen 2 Sep, 6:40 pm*हटाएँ
**
**DESKTOP-9F2K1L***last seen 14 Jun*हटाएँ
The stale device gets the filled button — we point at the safe choice instead of making her compare dates.
**ज़्यादा स्लॉट वाला प्लान**सहायता से बात करें
C7c — New phone, no free slotReached from login (C2b) or a reinstall. Fixes itself here rather than sending her to the desktop.

#### C8 · Activity feed

##

## Proof that yesterday's work landed
Activity is read-only and exists for one reason: the desktop did something while Renu was away from it, and she needs to confirm it worked before telling a Secretary it did. Entries group by day with a per-day summary line, because "how many muster rolls went in on Monday" is the actual question. Failures surface with the server's reason, never a raw stack trace.
9:41******
गतिविधि**
सबMuster rollPaymentReport
आज · 2 Sep14 tasks · 1 failed
**
**मस्टर रोल भरे***Muster Roll Entry · 12 rows · Hosakote GP*6:12 pm
**
**रिपोर्ट बनी***MR_Hosakote_Aug.pdf · 1.2 MB · uploaded to cloud*6:12 pm
**
**पेमेंट फ़ाइल अटक गई***Payment File · portal session timed out at row 31*कंप्यूटर पर दोबारा चलाएँ4:02 pm
**
**WhatsApp पर भेजा***2 files → 98450 4*****11:20 am
कल · 1 Sep9 tasks
**
**ज़ीरो MR जमा किए***Zero MR · 6 works*4:55 pm
**
**जॉब कार्ड जाँचे***Job Card Verify · 48 cards*9:30 am
**होम
**फ़ाइलें
**गतिविधि
**खाता
C8a — Grouped by dayDay header carries the count and the failure tally. Failed rows say what to do, on which machine.
9:41******
गतिविधि**
**
अभी कोई गतिविधि नहीं
जब आप कंप्यूटर पर NREGA Bot चलाएँगी, हर काम का हिसाब यहाँ दिखेगा — कितने मस्टर रोल, कौन सी रिपोर्ट, कब।**कंप्यूटर पर शुरू कैसे करें

#### Other states in this slot
**Filter empty** — इस छाँट में कुछ नहीं मिला। Keeps the chips visible with a "clear filter" action.
**Offline** — cached days render normally with the stale-data bar; pagination beyond the cache shows a retry row, not an error page.
**Error** — हिसाब नहीं आ पाया। One retry row at the bottom of whatever did load.
**होम
**फ़ाइलें
**गतिविधि
**खाता
C8b — Empty, plus the state notesThe empty state teaches what fills it. New-license users land here on day one.

#### C9 · Support chat

##

## A thread that never loses a message
Support relays through our WhatsApp Business side, so the interface should feel like the app she already knows. The one thing it must do better than WhatsApp: be explicit about what has left the phone. Queued, sent, and delivered are three different marks, and a queued message survives app death because it is written to the outbox table before the send is attempted.
9:41******
**
**
NREGA Bot सहायता
आमतौर पर 10 मिनट में जवाब
2 सितंबर
नमस्ते रेणु जी, कैसे मदद कर सकते हैं?
10:58 am
पेमेंट फ़ाइल 31 नंबर पर अटक जाती है
11:02 am**
पोर्टल का सेशन खत्म हो गया था। कंप्यूटर पर लॉगिन दोबारा करके वही टैब चलाएँ। मैं स्क्रीनशॉट भेज रहा हूँ।
11:05 am
**Tap to load · 240 KB
11:05 am
ठीक है, कोशिश करती हूँ
11:07 am**
**
संदेश लिखें…
**
C9a — Thread, onlineImages load on tap, never automatically — a 4G edge connection should not spend her data on a screenshot she may not need.
9:41******
**
**
NREGA Bot सहायता
ऑफ़लाइन
**2 संदेश भेजने के लिए तैयार हैं
पोर्टल का सेशन खत्म हो गया था।
11:05 am
दोबारा चलाया, फिर अटक गया
भेजना बाकी**
**Screenshot_1102.png · 180 KB
भेजना बाकी**
**
नेटवर्क आने पर ये अपने आप चले जाएँगे। ऐप बंद करने से कुछ नहीं जाएगा।
Outbox is persisted; WorkManager flushes it on connectivity.
**
संदेश लिखें… (queues offline)
**
C9b — Offline outboxDashed border + clock = on this phone only. One check = server has it. Two = agent read it.

#### Support entry points
Chat is offered wherever the app fails, with the failure pre-filled as context the agent can see: license key, app version, screen name, and the last error code. Renu never has to describe a bug.

#### FAQ before agent
Tapping Support opens a short list of the six questions that generate most tickets — expiry, payment not reflected, storage full, device slots, portal session errors, WhatsApp not received — each a two-line answer. "Talk to a person" sits at the bottom, always reachable in one tap.
This is the support-deflection lever. Measure it: FAQ opens vs threads started.

#### Delivery marks
**भेजना बाकी**In outbox, on device only**भेजा**Server accepted (one check)**पढ़ा**Agent read it (two checks)**नहीं गया**5 attempts failed · tap to retry
Attachments are optional and capped at 2 MB, downscaled on device before upload. On a metered connection we ask once before sending anything over 500 KB.
C9c — Support rulesEntry points, FAQ layer, and the four delivery marks.

#### C10 · Notifications

##

## Push we do not have yet, an inbox we can ship today
There is no push infrastructure in the product today — the desktop polls. So the inbox is the source of truth and FCM is an accelerator layered on top: every push has a matching inbox row, and the inbox is populated by `/api/app-config` plus a NEW notifications endpoint. If push never arrives, or the user denies the permission, nothing is lost.
9:41******
**सूचनाएँसब पढ़ा
**
**लाइसेंस 7 दिन में खत्म***10 Sep को खत्म हो जाएगा। अभी नवीनीकरण करें — ₹1,499*नवीनीकरण करें
9:00 am
**
**पेमेंट फ़ाइल अटकी***कंप्यूटर पर पोर्टल सेशन खत्म हो गया था*4:02 pm
**
**नया वर्ज़न 3.2.7 आया***कंप्यूटर ऐप में ज़ीरो MR तेज़ हुआ*30 Aug
**
**WhatsApp पर भेजा गया***2 फ़ाइलें · 98450 4*****29 Aug
**
**क्लाउड जगह 90% भरी***जगह बढ़ाएँ या पुरानी फ़ाइलें हटाएँ*27 Aug
Four categories, four icons, one colour each. Unread rows tint; read rows are plain. Tapping routes to the target screen, never just marks read.
C10a — Notification inboxThe fallback that is actually the foundation. Works with push disabled, denied, or unbuilt.
9:41******
**सूचनाएँ
**
लाइसेंस खत्म होने से पहले बता दें?
Let us remind you before your license expires
**
समाप्ति से 15, 7 और 1 दिन पहले याद दिलाएँगे
**
कंप्यूटर का काम पूरा या अटकने पर खबर देंगे
**
कोई विज्ञापन नहीं भेजेंगेहाँ, बताएँअभी नहीं
Shown on the second launch, or right after the first successful file action — never on first run alongside login.
C10b — Permission rationale (Android 13+)Our sheet first, system dialog only on "हाँ". "अभी नहीं" re-asks once, 14 days later, from the inbox.

#### Notification matrix
EventPushLocalExpiry T−15 / 7 / 1yes**yes**Expired todayyes**yes**Payment verifiedyesnoPayment pending > 5 minyesnoStorage 90 / 100%yesnoDesktop task failedyesnoAnnouncementyesnoSupport replyyesno
Expiry reminders are scheduled *locally* from the cached expiry date as well as pushed, so they fire even if FCM is unavailable on the device — which it is on some low-end India-market builds without Play Services.

#### Channels
**License & payment** — high importance
**Desktop activity** — default
**Support replies** — high
**Announcements** — low
Four channels so a user can silence announcements without losing expiry warnings. Settings mirrors these four toggles.
C10c — Push / local matrixWhich events push, which are scheduled on device, and the four channels.

#### C11 · Account + settings

##

## Language changes the app instantly, in place
The language switcher is the most-used setting in a five-locale product and the easiest to get wrong. Selecting a locale recreates the activity with the new configuration immediately — no restart prompt, no "changes apply next launch". Each language is written in its own script so it is legible to someone who cannot read the current one.
9:41******
खाता
R
Renu Gowda
renu.g***@gmail.com · 98450 4****
NRG7-••••-••••-1MZX
**
**प्लान और भुगतान***Yearly Pro · 118 days left***
**
**क्लाउड जगह***3.1 / 5.0 GB***
**
**डिवाइस***2 / 2 used***
**
**भाषा***हिन्दी***
**
**थीम***Light · system default off***
**
**सूचना सेटिंग***4 channels***
**
**सहायता***FAQ · chat***
**
**ऐप के बारे में***v1.1.0 · latest*****लॉग आउट / दूसरी चाबी
**होम
**फ़ाइलें
**गतिविधि
**खाता
C11a — Account hubKey and contact details masked on screen as well as in logs. Every row shows its current value, so nothing needs opening to check.
9:41******
**भाषा
चुनते ही पूरी ऐप उसी भाषा में बदल जाएगी।
**हिन्दी***Hindi*
**English***English*
**ಕನ್ನಡ***Kannada*
**বাংলা***Bengali*
**Hinglish***Hindi in Roman script*
Numbers, dates and file sizes stay in Latin digits in all five locales — the portal, the muster roll and every colleague's WhatsApp use them. Only words translate.

#### Theme, same screen pattern
**
उजाला
**
अंधेरा
**
फ़ोन जैसा
C11b — Language + theme, darkEach locale in its own script. Dynamic color is a separate Android 12+ toggle in About, default off.

#### Microcopy sheet · the phrases that repeat
EnglishHindiRenewनवीनीकरण करेंDays leftदिन बाकीExpiredखत्म हो गयाCloud storageक्लाउड जगहStorage fullजगह भर गईDownloadडाउनलोड करेंSend on WhatsAppWhatsApp पर भेजेंTry againफिर कोशिश करेंNo internetइंटरनेट नहीं हैOffline dataपुराना डेटाQueued to sendभेजना बाकीSupportसहायताDevicesडिवाइसActivityगतिविधिPayment doneभुगतान हो गयाChecking paymentभुगतान जाँच रहे हैं
Rules: no transliterated English where a common Hindi word exists; keep WhatsApp, PDF, GB, UPI as-is; never abbreviate a status word.
C11c — Shared microcopyThese sixteen strings carry most of the app. Translate them first; the rest follows the same register.

#### D. User flows

##

## Eight flows, each with the path that fails

### D1 · First launch → login → home
- Cold launch → **C1a**. Parallel: read Keystore session, call `/api/app-config`.
- No session → **C2a**. She types or pastes the key from the desktop.
- `POST /api/validate`. Success → store key in Keystore-backed EncryptedSharedPreferences, register device via `/api/heartbeat`, land on **C3a**.
- First Home render uses only the validate response — no second round trip before pixels.
**Fails:** expired key → **C2b** renew path. Blocked → support only. No slots → **C7c**. Offline → **C2d** backoff. Server 5xx → same as offline, with a support link after the third attempt.

### D2 · Expiring in 7 days → renew → updated card
- Local reminder fires at T−7 (also pushed). Tap → **C5a**, price from `/api/check-renewal-status`.
- Optional coupon → `/api/validate-coupon`; total recomputed server-side.
- Pay → `/api/create-order` → Razorpay → `/api/verify-payment`.
- Verified → force `/api/validate` → **C5c** success → Home card returns to blue with the new date.
**Fails:** app killed mid-checkout → on resume, pending state polls verify then validate. Signature mismatch → failure card, no retry charge, support pre-filled with the order id. Webhook lands before the client returns → validate already shows the new expiry; success card renders from that.

### D3 · License expired — what stays usable
CapabilityAfter expiryBrowse + view cloud files**Yes**Download to phone**Yes**Open already-downloaded files**Yes**Activity history (read)**Yes**Support chat**Yes**Renew / pay**Yes**Upload from phone**No**WhatsApp send / share links**No**Create folder, delete, move**No**Desktop bot**Stops**
Reads stay open, writes close. Nothing is deleted, and the app says so on the expired card — a user who fears losing files renews out of panic once and churns after.

### D4 · Storage 98% → upload → upsell → retry
- Tap upload, pick a 140 MB scan. Client checks the cached quota before starting the transfer.
- Won't fit → the sheet from **C6b** opens with the shortfall named, not a generic "full".
- Pay → `/api/create-storage-order` → verify → `/api/update-storage` → refetch `/files/api/storage-breakdown`.
- The blocked transfer resumes automatically; **C4d** moves it from Failed to In progress.
**Fails:** quota grows but the upload 507s anyway → hard error with a support link. Payment fails → the file stays queued, not discarded.

### D5 · Share 3 PDFs to WhatsApp from the field
- Home quick action → Files, already in the last-visited folder.
- Long-press a row → multi-select (**C4c**). Running total of size in the app bar.
- Number entered or picked from three recent chips. Optional merge → `/files/merge-for-share`.
- `POST /files/api/whatsapp-send`. Optimistic "sending" row, confirmed by the response, then a notification when the server reports delivery.
**Fails:** signal drops after tap → the request is queued in the same outbox as chat and flushed on reconnect; the row reads भेजना बाकी. Invalid number → inline field error before any request. Expired license → action is hidden, not shown-then-refused.

### D6 · New phone / reinstall / slots exhausted
- Fresh install → **C2a** → key entry.
- Server reports no free slot → **C7c** with the license's devices listed and last-seen dates.
- Remove the stale device → `/api/remove-device` → retry validate automatically → Home.
Reinstall on the same phone should *not* consume a second slot: the device fingerprint sent to `/api/heartbeat` must be stable across reinstall (Android ID scoped to signing key, not a random UUID). Flagged as backend/verification work in G2.

### D7 · Support chat offline → queued → delivered
- Message typed offline → written to the outbox table, rendered with a dashed border and clock (**C9b**).
- Connectivity returns → WorkManager flushes in FIFO order, one attempt per message, 5 attempts with backoff.
- Server accepts → single check. Agent reads → double check via the next `/whatsapp-chat/messages` poll or push.
**Fails:** 5 attempts exhausted → row turns red with tap-to-retry; the text is never lost or silently dropped. Attachment over 2 MB → downscaled before queueing, so the queue never holds an unsendable item.

### D8 · Maintenance mode / blocked version
- `/api/app-config` is called on every cold start and on resume after 30 minutes.
- Maintenance flag → **C1b**, full-screen, support still reachable, downloaded files still openable.
- Version in the blocked list → **C1c**, hard stop with the APK link and the expected checksum.
- Announcement payload with no flag → inbox row + a dismissible strip on Home, never a modal.
Config is cached for 30 minutes. If the call fails we honour the last known config rather than assuming healthy — a maintenance window should survive a flaky first request.

#### E. Screen → API mapping

##

## Every screen, its calls, and when it refetches
Auth on all machine calls: `Authorization: Bearer <license_key>`. Anything marked NEW does not exist in §5 today.
Screen / actionEndpoint(s)Payload sketchRefresh & caching**Splash**`GET /api/app-config`
`POST /api/validate``{license_key, app_version, device_id}`Config TTL 30 min, cached. Validate on every cold start; hard timeout 2.5 s then use cache.**Login — key**`POST /api/validate`
`POST /api/heartbeat``{license_key}` → plan, expiry, user, slots
`{device_id, device_name, os, app_version}`No cache. Heartbeat immediately after first success to claim the slot.**Login — OTP**`POST /api/send-otp`
NEW`POST /api/mobile/verify-otp``{email}` → `{otp_id}`
`{otp_id, code, device_id}` → `{session_token, refresh_token, exp}`Token in Keystore. Refresh at 80% of lifetime; 401 → single silent refresh, then logout.**Home**`POST /api/validate`
`GET /files/api/storage-breakdown`
`GET /activity-log` (limit 3)—Cache-then-network on every foreground. Pull-to-refresh forces all three. TTL 5 min.**Files list**`GET /files/api/list`
`GET /files/api/list/<folder_id>`—Room-cached per folder, TTL 10 min. Stale data shown instantly with the offline bar when the refresh fails.**File — view**`GET /files/api/download/<file_id>`Range requests for large PDFsDownloaded files kept in app storage with an LRU cap of 200 MB, user-clearable in Settings.**File — download**`GET /files/api/download/<file_id>`—WorkManager, foreground service notification, survives screen-off. Resumable where the server supports Range.**File — WhatsApp**`POST /files/api/whatsapp-send`
`POST /files/merge-for-share``{file_ids[], phone}` · merge first when checkedQueued in outbox. Optimistic row; reconciled by the response. Number masked in every log line.**File — link**`GET /files/view/<file_id>`URL handed to the system share sheetNo cache. Link creation is not idempotent — the button disables until the response lands.**File — delete**`DELETE /files/api/delete/<item_id>`—Confirm first, never optimistic. On success invalidate that folder only.**File — rename / move**NEW`POST /files/api/rename`, `/move``{item_id, new_name}` · `{item_id, target_folder_id}`Optimistic with revert. Ship only after the endpoints exist; hidden behind a config flag until then.**New folder**`POST /files/api/create-folder``{name, parent_id}`Optimistic insert, reverted on failure.**Upload**`POST /files/api/upload`Multipart, one file per requestClient pre-checks cached quota. WorkManager with retry; on 507 route to the upgrade sheet.**Renew**`POST /api/check-renewal-status`
`POST /api/validate-coupon`
`POST /api/create-order`
`POST /api/verify-payment`
`POST /api/activate-subscription`
`POST /api/verify-subscription-payment``{plan_id, coupon?}` → server returns amount
`{order_id, razorpay_payment_id, signature}`Never cached. After verify, force-refresh validate. Pending → poll every 5 s for 60 s, then rely on push + a Home strip.**Buy link (fallback)**`POST /api/get-buy-link`→ signed URL, key never in the URLUsed if the native SDK route is rejected — see H2.**Storage upgrade**`POST /api/create-storage-order`
`POST /api/verify-storage-payment`
`POST /api/update-storage``{tier_id}` — never a byte count from the clientOn success refetch breakdown and resume the blocked transfer.**Devices**`POST /api/validate` (slots)
`POST /api/set-device-name`
`POST /api/remove-device`
`POST /api/request-deactivation``{device_id, name}` · `{device_id}`Rename optimistic; remove confirmed and never optimistic. Refetch after either.**Activity**`GET /activity-log`
`GET /activity-log/stats``?from&to&type&cursor`NEW paramsPaged 30/screen, Room-cached 7 days. Pull-to-refresh only; no polling.**Support chat**`GET /whatsapp-chat/messages`
`POST /whatsapp-chat/messages``{text, attachment?, client_msg_id}`Poll 15 s while the thread is open, 0 in background (push instead). `client_msg_id` makes retries idempotent — NEW field.**Notifications**NEW`GET /api/notifications`
NEW`POST /api/register-fcm-token``{cursor}` · `{token, device_id}`Fetch on open and on push receipt. Announcements also derived from `app-config` so the inbox is never empty for lack of a new endpoint.**Settings**`GET /api/app-config` (version check)—Everything else is local (DataStore). Language and theme never hit the network.
**Optimistic UI is allowed in exactly four places:** rename device, create folder, rename file, and outbound chat/WhatsApp queueing. Anything that costs money or destroys data waits for the server.

#### F. Android technical blueprint

##

## Stack, structure, and the things we will not do

### F1 · Stack, pinned
Kotlin2.0.xCompose BOM (material3)2024.09.xMin / target SDK26 / 35DIHilt 2.52NetworkingRetrofit 2.11 + OkHttp 4.12JSONKotlinx Serialization 1.7CacheRoom 2.6 + DataStore 1.1BackgroundWorkManager 2.9PushFirebase BOM 33.x (FCM only)Secretsandroidx.security-crypto 1.1PaymentsRazorpay Android SDK 1.6.xImagesCoil 2.7PDFSystem `PdfRenderer` — no third-party viewer
**Hilt over manual DI** — recommended. The team is new to Android; Hilt's compile-time errors teach the graph, and every Android tutorial they will read assumes it. Manual DI saves ~1 MB and one annotation processor, and costs a hand-written ViewModel factory per screen. Not worth it at 11 screens.
**PdfRenderer over a library** keeps the APK under 12 MB. It cannot do text search or annotations. Acceptable: Renu reads and forwards, she does not edit.

### F2 · Module structure
**Single Gradle module for Phase 1**, with package-level feature boundaries that map 1:1 to future modules:
app/
├─ core/ network · auth · storage
│        · sync · ui (theme, M3
│        overrides, shared parts)
├─ feature/
│  ├─ onboarding/  license/  files/
│  ├─ billing/  devices/  activity/
│  └─ support/  notifications/
│     settings/
└─ (reserved) fielddata/ · jobqueue/
Multi-module is the right end state and the wrong starting point for two engineers learning Gradle. Splitting later is a mechanical move if nothing in `feature/` ever imports another `feature/` — enforce that with a lint rule from day one.

### F3 · Networking & auth
- **Header:** one OkHttp interceptor attaches `Bearer <license_key>` (or session token, when that lands) from the encrypted store. No call site ever touches the key.
- **401 / 403:** single silent refresh attempt (OTP model only), then clear the session and route to login with a reason code. Key-auth mode maps 401 to "license invalid or blocked" and shows **C2b**.
- **Retry:** idempotent GETs retry 3× with 1 s / 4 s / 9 s jitter. Writes never auto-retry except through the outbox, which carries a `client_msg_id`.
- **Timeouts:** connect 10 s, read 30 s, upload/download none (WorkManager owns those).
- **Outbox:** one Room table for chat messages, WhatsApp sends and activity acks — one flush worker, FIFO, 5 attempts, then surfaced as a failed row.
- **Offline reads:** every repository is Room-first. The network layer only ever *updates* the cache; the UI never observes a network call directly.

### F4 · Localization for five locales
- `values/` (en) plus `values-hi`, `values-kn`, `values-bn`, and Hinglish as `values-hi-rIN-b+hinglish` via per-app locale (`LocaleManagerCompat`, AppCompat 1.6+) — Hinglish is not an ISO locale, so it needs the custom tag plus `locales_config.xml`.
- Plurals via `<plurals>` for day counts, file counts, device counts. Never string concatenation.
- Dates and numbers: Latin digits everywhere, formatted with an explicit `Locale("en","IN")` so a Hindi locale does not switch to Devanagari numerals.
- **Workflow:** English strings.xml is the source of truth in git; a CSV export per release for the translator; a CI check that fails the build on a missing key in any locale. Screenshot review in hi and kn before release — Kannada labels run ~30% longer and will break a fixed-width button.

### F5 · Notifications
- FCM for server-triggered events; **local** AlarmManager/WorkManager reminders scheduled from the cached expiry date for T−15/7/1 so expiry warnings work without Play Services.
- Four channels (C10c). Permission requested on the second launch or after the first successful file action, behind our own rationale sheet (**C10b**).
- Every push carries a `deeplink` and a `notification_id` that matches an inbox row, so tapping and opening the inbox reach the same place.

### F6 · Security checklist
- License key / session token in EncryptedSharedPreferences with a Keystore-backed key. Never in plain SharedPreferences, never in a log, never in a URL.
- Mask PII at the log boundary: Aadhaar, mobile, IFSC, account numbers — a single `redact()` on the logging interceptor, plus `HttpLoggingInterceptor` off in release.
- Certificate pinning on the NAS domain, with a backup pin. Network security config blocking cleartext.
- Optional biometric gate on app open (BiometricPrompt), off by default.
- `FLAG_SECURE` on the license-key and payment screens. R8 + resource shrinking in release.
- APK signed and published with a SHA-256 checksum shown in-app, matching the desktop distribution habit.

#### What we will NOT do
No Play Billing. No client-side price, plan or discount logic. No client-side payment verification. No key in SharedPreferences or in analytics. No bot/Selenium execution on the phone. No portal credentials stored in the app — ever. No third-party analytics SDK. No WebView for anything except, if H2 goes that way, a hosted checkout page.

### F7 · Observability on a self-hosted Flask backend
Skip Crashlytics-style SaaS. Ship crash and event reporting to our own server: a NEW`POST /api/app-telemetry` taking `{device_id, app_version, event, screen, error_code, stack_hash}`, batched and sent on Wi-Fi only, with a user-visible opt-out in Settings. Six events are enough to run the product: login result, renewal funnel step, payment outcome, upload/download failure, offline-queue depth, and crash. Query it in Postgres next to the license data we already have.

#### G. Build plan

##

## What ships, in what order, by people learning Android
Effort assumes 1–2 backend engineers new to Compose. The first three weeks are mostly learning, and the plan is arranged so that learning happens on the least risky screens. Calendar weeks, not ideal weeks.

### G1 · Milestones
MScopeEffort**M0**Project setup, theme + M3 token overrides, one static screen, CI building a debug APK. Deliberately throwaway — this is the learning tax.2 wk**M1**Networking core, encrypted storage, splash + key login, device registration. First real APK on a real phone.2 wk**M2**Home dashboard with all four license states, storage gauge, Room caching + offline bar.2 wk**M3**Files: browse, view, download via WorkManager, actions sheet, WhatsApp send.3 wk**M4****v0.1 beta** to 5 friendly users — Hindi + English only, no payments, no push.1 wk**M5**Renewal + storage upgrade with Razorpay, all payment states, pending-verification handling.2.5 wk**M6**Devices, Activity, Support chat with the persisted outbox.2.5 wk**M7**FCM + inbox, local expiry reminders, permission rationale.1.5 wk**M8**Remaining 3 locales, dark-theme pass, upload from phone, telemetry, hardening.2 wk**M9****v1.0** — APK distribution, checksum page, update check, 20-user rollout.1 wk
**Total ≈ 19–20 weeks** to v1.0 for one engineer, ~13 with two working in parallel after M1. The honest risks: Compose state management in month one, WorkManager's foreground-service rules on Android 12+, and Razorpay's callback lifecycle when the app is killed mid-payment. Budget a week of slack for each.
**Smallest useful v0.1 (M4):** log in with the license key, see the license state and days remaining, browse cloud files, download, and send a PDF to WhatsApp. No payments, no push, two languages. That is already worth carrying to the field.

### G2 · Backend work items this design implies
Start these in parallel with M0–M2. Everything else in the app runs on §5 as it stands today.
ItemWhy the app needs it**Mobile session token**
`POST /api/mobile/verify-otp`, `/refresh`Only if H1 chooses OTP. Short-lived signed token + refresh, so the key never lives on the phone.**FCM plumbing**
`POST /api/register-fcm-token` + server-side sendNo push infra exists today. Needed for payment-verified, task-failed, support-reply, announcement.**Notifications feed**
`GET /api/notifications`The inbox is the fallback for every push. Until it exists the inbox renders announcements from `app-config` only.**Activity params**
`?from&to&type&cursor` on `/activity-log`Day grouping and the filter chips need paging and a type filter server-side; the phone cannot fetch a year of rows.**Idempotency key**
`client_msg_id` on chat + WhatsApp sendThe offline outbox retries. Without it a reconnect can double-send a message or a file.**Rename / move**
`POST /files/api/rename`, `/move`Both actions are in the file sheet by user expectation. Hidden behind a flag until these ship.**Stable device id contract**
on `/api/heartbeat`A reinstall must not burn a device slot. Define the fingerprint and dedupe rule server-side.**Storage tier list**
in `/api/app-config` or a new callThe upgrade sheet must not hardcode tiers or prices. Client sends only a `tier_id`.**Telemetry sink**
`POST /api/app-telemetry`Crash and funnel data without a third-party SDK (F7).**Range support**
on `/files/api/download/<id>`Resumable downloads on a dropping 4G connection. Verify whether the current handler supports it.**Version + checksum**
fields in `/api/app-config`Blocked-version screen and the in-app update check need `min_android_version`, `latest`, `apk_url`, `sha256`.
Eleven items, of which four are hard blockers for v1.0 (FCM, notifications feed, activity params, idempotency key) and one is optional (session token). None block the v0.1 beta.

#### H. Open decisions

##

## Six calls I did not make silently

### H1 · Login model
**Recommendation: license key in v0.1, add email+OTP in v1.0, keep both forever.**
The key is physically in front of her on the desktop, needs zero new backend, and matches how she already thinks about the product. The cost: the key is a bearer credential sitting on a phone that may be shared or lost, and a shared-desktop pair will happily install the app on two phones against one license. OTP fixes both and gives us revocation, but it needs the new endpoint, assumes a working email — which many GRS users do not have — and adds a delivery step that fails silently on a slow inbox. Mobile-OTP instead of email would be better for this persona than either, and is a bigger backend ask than this design should assume. **Do not ship OTP-only.**

### H2 · Payment UX
**Recommendation: native Razorpay SDK, with the hosted `/api/get-buy-link` page as a fallback.**
Native gives UPI intent handoff to GPay/PhonePe, which is how this user pays for everything, and it survives a mid-payment app kill better than a WebView. Cost: ~2 MB of APK, an SDK to keep updated, and Razorpay's callback lifecycle to get right. The hosted page in a Custom Tab is less code and reuses the web flow you already run, but adds a browser round trip, is easier to abandon, and makes the "did my payment go through" state harder to recover. Keep the link path implemented as the recovery route when the SDK fails to init on an old device.

### H3 · Distribution
**Recommendation: APK-first now, Play later, and design for both from day one.**
APK-first matches how the desktop product is already distributed and how the licenses are already sold; no store review, no Play policy questions about a "government automation" tool. Cost: side-loading friction, no automatic updates, and FCM still needs Google Play Services on the device — which is present on virtually all retail India-market phones but not guaranteed on the very cheapest. That is why expiry reminders are also scheduled locally (F5). If Play becomes the primary channel later, Play's policy on external payments would need review; renewals for a desktop product bought outside the app are normally fine, but that is a legal question, not a design one.

### H4 · Naming and icon
**Recommendation: keep "NREGA Bot" as the store/APK name, subtitle it in-app.**
Two hundred users already say "NREGA Bot" to each other and to your support line; renaming the phone app splits that vocabulary. Add साथी ऐप ("companion app") as the in-app subtitle so it is obvious this is not the automation itself. If you do want a friendlier mark, सहायक ("assistant") tests better than any English coinage — but decide once, because the icon, the APK, the support script and the WhatsApp templates all carry it. **Icon direction:** the brand-blue rounded square with a shield-check, matching the desktop tray icon — recognisable at 48 dp on a cluttered home screen, and it reads as "your license is safe" rather than "a robot runs your work".

### H5 · Minimum Android version
**Recommendation: hold API 26 (8.0) for v1.0, revisit at 200 installs with real data.**
Every API we need works on 26. The real cost is not code, it is testing: notification permission behaviour differs on 13+, foreground-service rules on 12+, scoped storage on 10+, so QA spans four behavioural bands regardless of where the floor sits. Moving to API 29 (10) would cut roughly the oldest band and lose the ₹6k phones bought in 2018–19 that are exactly your persona's hardware. Ship at 26, then read the telemetry from F7 — if under 3% of installs are pre-10 after a quarter, raise it and stop testing that band.

### H6 · Three more I can't settle alone
**a. Does an expired license keep cloud files readable?** I designed yes (D3), because a user who fears losing files churns. This is a commercial call, not a design one — if files are the paid hook, say so and I will invert the expired state.
**b. Storage upgrade lifetime.** I drew it as one-time and valid until license expiry. If it is actually recurring, or resets on renewal, the sheet copy and the receipt both change.
**c. WhatsApp number provenance.** Sending to an arbitrary typed number is a delivery-policy question on your WhatsApp Business account. If only pre-verified numbers are permitted, the send sheet becomes a picker and the "type a number" path disappears — a materially different screen.

#### Next from me, once you have read this
Pick the login model and the payment route (H1, H2) and I will tighten those five screens to one path each instead of two. After that: a components sheet — the M3 overrides, the four license-state cards, the row types and the sheet patterns — drawn once at real size so the engineers build a theme rather than eleven screens. And if you want the beta scope pressure-tested, I can cut a v0.1-only version of section C so nothing in the file is a distraction during M0–M4.