# Telegram Number + Temp Mail Bot — Render Ready

এই package-টি Render Web Service-এ deploy করার জন্য প্রস্তুত। এতে Number/OTP panel এবং Temp Mail system দুটোই আছে।

## Package-এ যা আছে

- `main.py` — সম্পূর্ণ bot source code
- `requirements.txt` — Python dependencies
- `Procfile` — web-service start command
- `render.yaml` — Render build/deploy/health-check configuration
- `run.sh` — alternative start script
- `.env.example` — required variables-এর নমুনা
- `.gitignore` — secret/database ignore rules
- `runtime.txt` — Python runtime

## এই সংস্করণের গুরুত্বপূর্ণ fixes

- ZebraSMS এখন `Get Number` এবং `View Range`-এর primary source। Zebra থেকে
  usable number না এলে তবেই অন্য enabled panel fallback হিসেবে চেষ্টা হবে।
- Zebra-এর বিভিন্ন response shape, endpoint এবং authentication-header
  variation handle করা হয়েছে।
- Auto SMS এখন প্রতিটি enabled panel-এর জন্য background poller দিয়ে চলবে,
  Telegram send ব্যর্থ হলে retry করবে, এবং SQLite ledger-এর কারণে restart-এর
  পর duplicate SMS পাঠাবে না।
- Admin → Settings → Others Link-এ `Main Channel` যোগ হয়েছে। Forwarded OTP
  card-এ `GO TO PANEL` এবং configured `GO TO CHANNEL` button দেখা যাবে।
- `Shop` button এখন Main router-এর সঙ্গে সঠিকভাবে wired; Shop navigation,
  media upload এবং inline callback একই bot instance-এ কাজ করে।
- Checkout ও admin price/stock/coupon input-এ invalid, negative এবং malformed
  value আটকানো হয়েছে; stale callback এলে polling process আর ভেঙে যায় না।
- Admin Backup এখন SQLite-এর consistent snapshot তৈরি করে; Main bot-এর data-এর
  সঙ্গে Shop products, orders, wallet, top-ups, coupons এবং settings-ও সম্পূর্ণ
  backup file-এ থাকে।
- Main SQLite connections context শেষ হলে বন্ধ হয়; WAL mode প্রতি query-তে
  আবার সেট না করে startup-এ একবার configure হয়।
- Polling শুরু করার আগে পুরনো Telegram webhook সরানো হয়; pending updates বাদ
  দেওয়া হয় না।
- Free ও persistent-disk Render configuration আলাদা করা হয়েছে; Free profile-এ
  UptimeRobot-এর `/health` monitor নির্দেশনা যোগ হয়েছে।

Auto SMS-এর জন্য bot-কে target group/channel-এ admin করা এবং numeric chat ID
সঠিকভাবে সেট করা আবশ্যক। ZebraSMS-এর API response যদি সম্পূর্ণ আলাদা হয়,
logs-এ `ZebraSMS ... raw=` line দেখে panel-এর official endpoint/body
অনুযায়ী `ZEBRA_*_PATHS` adjust করতে হবে।

## Render-এ deploy করার ধাপ

1. ZIP extract করে সব ফাইল একটি **private GitHub repository**-র root-এ upload করুন (`main.py` root-এ থাকতে হবে)।
2. Render → **New → Blueprint** → repository নির্বাচন করুন। `render.yaml` Free Web Service তৈরি করবে.
3. Render Environment-এ `BOT_TOKEN` ও numeric `ADMIN_ID` যোগ করুন। Secret GitHub বা chat-এ রাখবেন না।
4. Deploy শেষে Render-এর public `onrender.com` URL কপি করুন। Render health check `/health` ব্যবহার করে।
5. Bot-কে Telegram-এ `/start` পাঠিয়ে পরীক্ষা করুন।

### UptimeRobot দিয়ে Free Web Service জাগিয়ে রাখা

Bot-এর HTTP health endpoint কোডে আগে থেকেই আছে; আলাদা keep-alive code দরকার নেই।

1. UptimeRobot-এ **Add New Monitor → HTTP(s)** নিন।
2. URL দিন `https://YOUR-SERVICE.onrender.com/health` — নিজের Render URL বসাবেন।
3. HTTP method **GET** নির্বাচন করুন, interval **5 minutes** দিন (Free monitor interval)
   এবং monitor চালু করুন। Latest package-এ GET ও HEAD দুটিই support করে।

Render Free service 15 মিনিট inbound traffic না পেলে sleep করে। এই monitor-এর
request idle sleep ঠেকাতে সাহায্য করবে; তবে Render restart বা redeploy আটকায় না।

### SQLite data হারানোর বিষয়ে গুরুত্বপূর্ণ

Free Web Service-এর filesystem ephemeral। `Developer By SUMON VAI.db` ও `temp_mail_users.json`
সেখানে থাকে, তাই Render restart, spin-down বা redeploy হলে সেগুলো হারাতে পারে।
UptimeRobot sleep কমায়, কিন্তু persistent storage দেয় না। Render-এ SQLite data
নিশ্চিতভাবে রাখতে `render-persistent.yaml`-এর paid plan ও `/var/data` disk ব্যবহার
করুন, অথবা Free service-এর সঙ্গে external persistent database-এ migrate করুন।
একই `DATA_DIR`-এ আগের `voltx.db` থাকলে startup-এ সেটির data নতুন database নামে
copy হবে; অন্য `DATA_DIR`-এ থাকলে আগে backup/restore করুন।

## Temp Mail কীভাবে কাজ করে

- Mail.gw থেকে domain নেওয়া হয়
- নতুন email account এবং password তৈরি হয়
- token সংগ্রহ করা হয়
- নতুন mail background-এ নিয়মিত চেক হয় (fresh mailbox-এ দ্রুত interval-সহ)
- একই message ID দ্বিতীয়বার পাঠানো হয় না
- email, password, token এবং seen message ID JSON state-এ রাখা হয়
- দুই ঘণ্টা পর পুরনো mailbox state মুছে যায়
- notification-এ privacy-friendly ভাবে শুধু প্রয়োজনীয় mail OTP code দেখানো হয়

## জরুরি নিরাপত্তা

- `BOT_TOKEN` কখনো GitHub, screenshot বা public chat-এ দেবেন না।
- Real `.env` file upload করবেন না।
- Render Environment Variables-এই secret values রাখবেন।
- Repository private রাখাই নিরাপদ।

## Data reset / restart diagnosis

`/start` handler database tables বা Shop products মুছে না; এটি user record
update করে। Main settings ও Shop data একই `Developer By SUMON VAI.db`-এ থাকে।
`DATA_DIR` path বদলালে নতুন empty database খোলা হয়। Render Free-তে local database এবং Temp Mail
JSON state restart/sleep/redeploy-এর পর টিকে থাকার নিশ্চয়তা নেই। Free hosting-এ
UptimeRobot idle sleep কমাতে পারে, কিন্তু persistent storage-এর বিকল্প নয়।

একই `BOT_TOKEN` দিয়ে একটির বেশি long-polling process চালাবেন না (যেমন পুরনো
Replit process ও নতুন Render process একসঙ্গে); Telegram updates conflict হলে
polling ব্যাহত হতে পারে। Runtime crash নির্ণয়ে Render → Logs-এ প্রথম traceback
দেখুন; token বা API key-সহ log/source কাউকে পাঠাবেন না।

## Update — Premium build

* **Temp Mail OTP now arrives automatically.** Mail bodies are converted from
  HTML to text before scanning, the OTP matcher understands many more wordings
  (OTP / verification / security / login code, digits or letters), a fresh
  mailbox is polled every 2 seconds for the first 3 minutes, and the dead
  `mail.gw` provider is now the last fallback instead of the first choice.
  Each mail notification now shows only the extracted OTP code—not the sender,
  subject, or full mail body.
* **ZebraSMS numbers.** Number allocation now tries every Zebra base URL
  (`/api/v1`, `/api`, `/publicapi`, bare host), every known endpoint, JSON +
  form + query bodies and all auth header names — the same behaviour as the
  other panels. Zebra is also part of the normal round-robin fallback, and
  "Live Access" reports the exact last failure.
* **Premium emoji set** across every menu, card and notification.
* **Health server** no longer crashes the bot when its port is busy.

---

## ZebraSMS integration (same flow as VoltXSMS / FastXOTPs)

ZebraSMS is wired in as a normal provider of the existing panel system — same
allocation path (`fetch_api_number`), same OTP poller (`fetch_otps_from_api`),
same delivery, duplicate-prevention, expiry, retry, statistics and admin UI.
Only the provider-specific HTTP calls are Zebra-specific:

| Purpose | Documented endpoint |
|---|---|
| Get number | `POST https://api.zebrasms.com/api/v1/publicapi/getnum` — header `MAuth`, body `{"range":"RANGE"}` |
| OTP updates | `GET  /publicapi/getupdate` — header `MAuth` |
| Live ranges | `GET  /publicapi/liveaccess[?sender=...]` — header `MAuth` |

`data.rows[]` is mapped into the shared panel structure (number, range,
country, iso2, operator, dial_code, mccmnc, expires_ms). No undocumented
endpoint is ever called.

Admin Panel → Settings → API Management → **ZebraSMS**: set key, enable/disable,
remove key, Live Access check — exactly like every other panel.

## Auto SMS

Admin Panel → Settings → Auto SMS: turn it on and set the group/channel ID.
The bot learns the connected panel's **top ranges and top countries**, keeps
real numbers active on them, and forwards every genuine SMS from those
ranges to the group with **GO TO BOT** and **GO TO CHANNEL** buttons.

Set the two button links in Admin Panel → Settings → Others Link:
- 🤖 Auto SMS Bot Link → where the **GO TO BOT** button goes
- 📢 Auto SMS Channel Link → where the **GO TO CHANNEL** button goes

## Deploying on Render

`render.yaml` selects the Free Web Service profile. `render-persistent.yaml` is
the separate paid-disk profile for durable SQLite storage. Render Blueprint
auto-detects only `render.yaml`; to use the persistent profile, use its contents
as the repository's `render.yaml` before creating the Blueprint.

No bot token or admin ID is stored in the source code. The app uses long polling,
so run exactly one active service/instance with a given bot token; multiple
pollers for one token can conflict.

- Profile-based referral panel with share/copy buttons and an admin-set one-time referral bonus
