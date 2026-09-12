# Deploying to GitHub and Streamlit Community Cloud

Step by step, assuming no prior GitHub experience. Allow about 20 minutes.

---

## Before you start — one decision about privacy

**Do not commit real export data to a public repository.**

This tool works with commercially sensitive material: exporter names, buyer
names, prices, volumes. If the repository is public, so is everything in
`data/`.

Choose one:

| Option | When it fits |
|---|---|
| **Private repository** (recommended) | You want real data in the app. Streamlit Community Cloud can deploy from a private repo on the free tier. |
| **Public repository, no real data** | You want to share the tool itself. Leave `data/dataset.json` empty; users upload their own extract each session. |

The steps below assume **private**. Where it differs for public, it is noted.

---

## Part 1 — Put the code on GitHub

### 1.1 Create a GitHub account

Go to <https://github.com> and sign up if you have not already.

### 1.2 Create the repository

1. Click the **+** in the top right → **New repository**.
2. **Repository name**: `rmb-3t-intel`
3. **Description**: `Rwanda 3T mineral export intelligence tool`
4. Select **Private**. *(Select Public only if you have removed all real data.)*
5. Do **not** tick "Add a README file" — this project already has one.
6. Click **Create repository**.

Leave the page open. GitHub shows commands you will need shortly.

### 1.3 Install Git

- **Windows**: <https://git-scm.com/download/win>, accept all defaults.
- **macOS**: open Terminal and type `git --version`. If not installed, macOS offers to install it.
- **Linux**: `sudo apt install git`

### 1.4 Upload the project

Unzip the project somewhere sensible — for example `C:\RMB-Fin intel\rmb-3t-intel`
or `~/projects/rmb-3t-intel`.

Open a terminal **in that folder**:

- **Windows**: open the folder in File Explorer, type `cmd` in the address bar, press Enter.
- **macOS**: right-click the folder → Services → New Terminal at Folder.
- **Linux**: right-click → Open in Terminal.

Then run these, one line at a time. Replace `YOUR-USERNAME` with your GitHub username:

```bash
git init
git add .
git commit -m "Initial commit - RMB 3T Export Intelligence V1-0a"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/rmb-3t-intel.git
git push -u origin main
```

If Git asks for credentials, use your GitHub username and a **personal access
token** (not your password):

1. GitHub → click your avatar → **Settings**
2. Scroll to **Developer settings** → **Personal access tokens** → **Tokens (classic)**
3. **Generate new token (classic)**, tick the **repo** scope, generate
4. Copy the token and paste it as the password. Save it somewhere safe — GitHub only shows it once.

Refresh your repository page. The files should be there.

---

## Part 2 — Deploy on Streamlit Community Cloud

### 2.1 Sign in

1. Go to <https://share.streamlit.io>
2. **Sign in with GitHub** and authorise it.
3. For a **private** repository you must also grant access to private repos when prompted. If you missed it: GitHub → Settings → Applications → Streamlit → Configure → grant repository access.

### 2.2 Create the app

1. Click **New app** → **Deploy a public app from GitHub** (this also covers private repos once access is granted).
2. Fill in:
   - **Repository**: `YOUR-USERNAME/rmb-3t-intel`
   - **Branch**: `main`
   - **Main file path**: `app/Home.py`  ← **must be exactly this**
3. Optionally set a custom subdomain under **Advanced settings**.
4. Click **Deploy**.

First build takes 2–5 minutes while dependencies install. When it finishes you
get a URL like `https://rmb-3t-intel.streamlit.app`.

### 2.3 Check it worked

1. The Home page loads with the green-and-gold header.
2. Press **🧪 LOAD DEMO DATA** — metrics populate.
3. Click through to **5 · Peer Benchmark** — charts render.

If the app shows an error, open **Manage app** (bottom right) to read the logs.
See Troubleshooting below.

---

## Part 3 — The save-and-commit cycle

**This is the most important operational point. Read it carefully.**

Streamlit Community Cloud gives each app a **temporary filesystem**. Anything
the app writes is erased when the app restarts, sleeps, or redeploys. The app
therefore never writes to disk. Work lives in your browser session until you
save it back to the repository yourself.

### The cycle

1. Open the app and do the work — upload an extract, approve harmonisation rules, set exclusions.
2. A yellow **UNSAVED CHANGES** banner appears.
3. Go to **1 · Data Management → 💾 Save & Commit**.
4. Download the files that changed:
   - `dataset.xlsx` and `dataset.json` — always, if you added records
   - `rules_harmonisation.json` — if you approved or removed a name rule
   - `rules_exclusions.json` — if you changed categories or exclusion rules
   - `intl_prices.json` — if you overrode a benchmark price
5. Replace the matching files in your local project's `data/` folder.
6. Commit and push:

```bash
git add data/
git commit -m "Update dataset - added August 2026 extract"
git push
```

7. Streamlit redeploys automatically (about a minute). The new files become the baseline.

### Updating files directly on GitHub

For a single file you can skip the terminal:

1. Go to the repository → `data/` folder → click the file.
2. Click the **pencil** icon → delete all contents → paste the new contents.
3. **Commit changes** at the bottom.

This works well for the small JSON rules files. For `dataset.xlsx` use the
**Upload files** button in the `data/` folder instead and let it overwrite.

### Let the app commit for you (recommended)

Since V1-0b the app can push the changed files itself, removing steps 3 to 6.

**Step 1 — create a fine-grained token**

1. GitHub → your avatar → **Settings** → **Developer settings**
2. **Personal access tokens** → **Fine-grained tokens** → **Generate new token**
3. **Token name**: `rmb-3t-intel app`
4. **Expiration**: 90 days (you will need to renew it; set a reminder)
5. **Repository access** → *Only select repositories* → pick `rmb-3t-intel`
6. **Permissions** → *Repository permissions* → **Contents** → **Read and write**
7. Generate, and copy the token. GitHub shows it once.

Do not use a classic token with full `repo` scope — it grants far more than this
app needs.

**Step 2 — give the token to the app**

*On Streamlit Cloud:* **Manage app** → **Settings** → **Secrets**, paste:

```toml
[github]
owner = "YOUR-GITHUB-USERNAME"
repo = "rmb-3t-intel"
branch = "main"
token = "github_pat_..."
```

*Locally:* create `.streamlit/secrets.toml` with the same block. That file is
git-ignored and must never be committed.

**Step 3 — use it**

**1 · Data Management → Save & Commit → Commit directly to GitHub**. Press
**Test connection** first: it confirms the token works *and* that it actually
has write permission. Then pick the files, edit the message, and
**🚀 COMMIT TO GITHUB**.

The GitHub Contents API commits one file at a time, so four files means four
commits. If one fails partway the earlier ones are already pushed — the result
table shows which succeeded.

**If the token leaks or you are unsure:** GitHub → Settings → Developer settings
→ Fine-grained tokens → **Revoke**. Generate a new one and update the secret.

### The other alternative

**Run locally instead.** `./run.sh` on your own machine, where the filesystem is
permanent and no token is needed. Use Community Cloud only for sharing with
colleagues.

---

## Part 4 — Keeping the app updated

When code changes:

```bash
git add .
git commit -m "Describe what changed"
git push
```

Streamlit redeploys automatically. No further action needed.

---

## Part 5 — Sharing access

### Private repository, public app URL

By default the deployed app is reachable by anyone with the link, even from a
private repo. If that is not what you want:

1. **Manage app** → **Settings** → **Sharing**
2. Set the app to private and invite specific email addresses.

Viewers need a Streamlit account matching the invited email.

### What viewers can do

Everyone reaching the app has full use of it — including upload and rule
editing. There is no read-only role and no login inside the app. Their changes
never touch your repository (they cannot commit), so the shared baseline is
safe, but treat the URL as sensitive if the committed dataset is real.

---

## Troubleshooting

**"Main module does not exist"**
The Main file path must be `app/Home.py` — not `Home.py`, not `app/home.py`.
Fix under **Manage app → Settings → Main file path**.

**"ModuleNotFoundError: No module named 'engine'"**
`engine/__init__.py` is missing or was not committed. Check it exists locally,
then `git add engine/__init__.py && git commit -m "Add engine package marker" && git push`.

**"ModuleNotFoundError: No module named 'xlrd'"**
`requirements.txt` did not get committed, or was edited. It must contain
`xlrd>=2.0` — legacy `.xls` files cannot be read without it.

**App boots but every page says "No data loaded yet"**
Expected on a fresh deployment — `data/dataset.json` ships empty. Upload an
extract, or press **LOAD DEMO DATA**.

**Changes disappeared after a redeploy**
They were never committed. See Part 3. This is the designed behaviour, not a bug.

**GitHub commit fails with 401 or 403**
401 means the token is expired, mistyped, or lacks Contents write permission.
403 usually means it has no write access to this repository. Press **Test
connection** — it reports the permission the token actually holds. Fine-grained
tokens also expire: regenerate and update the secret.

**GitHub commit fails with 409**
The file changed on GitHub since the app loaded it — someone else committed, or
you edited it directly. Reload the app and redo the change.

**Word or PDF download button missing**
`python-docx` or `reportlab` is not installed. Both are in `requirements.txt`;
if you edited it, restore those lines and redeploy.

**App is slow to wake**
Community Cloud sleeps apps after about a week of inactivity. The first visit
after that takes 30–60 seconds. Subsequent loads are fast.

**Upload rejected as "Not an MCIS 3T export extract"**
The file is missing one or more of the 13 expected columns. The rejection
message names them. Check you exported the right report from MCIS.

**Private repo not listed when creating the app**
Streamlit was not granted access to private repositories. GitHub → Settings →
Applications → Streamlit → Configure → grant access, then retry.

---

## Quick reference

| | |
|---|---|
| Main file path | `app/Home.py` |
| Python version | 3.10+ |
| Dependencies | `requirements.txt` |
| Theme | `.streamlit/config.toml` |
| Committed data | `data/` |
| Run locally | `./run.sh` or `run.bat` |
| Run tests | `python -m pytest tests/ -q` |
