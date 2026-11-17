# HAQQ — Operations Guide: Installation, Backup, Recovery and Demo Video

This guide is for the person who runs HAQQ on a Windows computer or server with Docker Desktop. Every task is a
script in the `haqq\ops` folder: double-click it, or run it from a Command Prompt.

## 1. One-time installation

1. Install **Docker Desktop** (https://www.docker.com/products/docker-desktop/) and **Git**
   (`winget install -e --id Git.Git`). Start Docker Desktop and wait until it says *running*.
2. Get the code: in PowerShell run `cd "$HOME\Downloads"` and then
   `git clone https://github.com/helfaramawi/paradise-AI-Project.git`.
   HAQQ is in the folder `paradise-AI-Project\haqq`.
3. Double-click **`haqq\ops\start.bat`**. The first run creates `.env` from `.env.example`, builds HAQQ
   (10–20 minutes the first time) and opens http://localhost:8090.
4. Before real use, edit `haqq\.env`: set `HAQQ_ENVIRONMENT=production`, a long random `HAQQ_SECRET_KEY`
   and a new `HAQQ_DB_PASSWORD`. Then run `start.bat` again.
   **Change the database password only before the first start** — after that it is stored in the database.
5. For presentations, load the fictional demo data: **`ops\seed-demo.bat`** (accounts `*@haqq.demo`,
   password `HaqqDemo!2026`). Do not load demo data on a customer's live system.

## 2. Everyday commands

| Task | Windows | macOS / Linux |
|---|---|---|
| Start and open HAQQ | `ops\start.bat` | `ops/start.sh` |
| Stop (data is kept) | `ops\stop.bat` | `ops/stop.sh` |
| Verified backup now | `ops\backup.bat` | `ops/backup.sh` |
| Daily automatic backup | `ops\schedule-backup.bat [HH:MM]` | cron: `ops/backup.sh` |
| Restore a backup | `ops\restore.bat [name]` | `ops/restore.sh [name]` |
| Update to the latest version | `ops\update.bat` | `ops/update.sh` |
| Load / reset demo data | `ops\seed-demo.bat [reset]` | `ops/seed-demo.sh [reset]` |
| Record the demo video | `ops\record-demo.bat` | `ops/record-demo.sh` |
| Add the Arabic voice-over | `ops\make-voiceover.bat [female]` | `ops/make-voiceover.sh [female]` |

## 3. Backups

### What a backup contains
Each backup is a folder `haqq\backups\haqq_YYYYMMDD_HHMMSS` with:

| File | Contents |
|---|---|
| `database.dump` | all data: organisations, users, projects, clauses, events, entitlements, valuations, claims, deadlines, audit trail |
| `documents.tar.gz` | every uploaded document and every generated claim file |
| `env.backup` | the `.env` settings, including passwords and API keys — **keep backups private** |
| `manifest.txt` | date, code version, both verification results, row counts per table, SHA-256 of every file |

### How a backup proves it is usable
A backup is only reported as complete after **two checks pass**:
1. **Database:** the dump is restored into a temporary scratch database and every table's row count is compared
   with the live database.
2. **Documents:** every stored file in the archive is checked against the SHA-256 fingerprint recorded in the
   database when the file was uploaded or generated. A missing or altered file fails the backup.

A backup that fails either check is renamed `failed_haqq_…` so it can never be mistaken for a good one.

### Daily automatic backups
Run **`ops\schedule-backup.bat`** once (default 23:30, or e.g. `schedule-backup.bat 02:00`). Windows Task Scheduler
then runs a verified backup every day; the result is in `haqq\backups\last-scheduled.log`. The computer must be
on and Docker Desktop running at that time. Remove it with `schedule-backup.bat remove`.

### Keeping copies elsewhere (strongly recommended)
Add to `haqq\.env`:
```
HAQQ_BACKUP_COPY_TO=E:\HAQQ-Backups
HAQQ_BACKUP_KEEP=30
```
Every backup is then also copied to that folder (an external disk, a NAS or a synced cloud folder), and the 30 newest
backups are kept locally. Recommended policy: daily automatic backup, 30 days kept, one copy off the machine, and a
**restore test every quarter** (section 4.3).

## 4. Recovery

### 4.1 Restore on the same computer
Run **`ops\restore.bat`**. It lists the backups, asks which one, shows its manifest and asks you to type `YES`. It then:
1. takes a **safety backup** of the current data (so a restore can itself be undone);
2. stops HAQQ, restores the database and all documents;
3. starts HAQQ, re-checks **every stored file against its fingerprint**, and prints the record counts.

### 4.2 Restore on a new computer (disaster recovery)
1. Install Docker Desktop and Git, clone the repository (section 1, steps 1–2). Do **not** create `.env` yourself.
2. Copy the backup folder (e.g. from the external disk) into `paradise-AI-Project\haqq\backups\`.
3. Put the backed-up settings in place **before the first start**, so the new database is created with the same
   password: `copy backups\haqq_YYYYMMDD_HHMMSS\env.backup .env` (run inside the `haqq` folder).
4. Run `ops\start.bat` once so the containers exist, then run `ops\restore.bat haqq_YYYYMMDD_HHMMSS`.
   (If a different `.env` already existed, the restore keeps it and saves the backed-up one as
   `.env.from-backup` — copy the passwords and keys from it if logins fail.)
5. Sign in and check a few projects. The restore already verified every document's fingerprint.

Target times: a typical tenant restores in minutes; plan for one hour including installation on a new machine.

### 4.3 Quarterly restore test
On a spare computer, follow 4.2 with the latest backup and confirm you can sign in and open a generated claim file.
Record the date and result. An untested backup is a hope, not a backup.

### 4.4 After an update goes wrong
`update.bat` always takes a verified backup first. If the new version misbehaves:
`git checkout <previous code version from manifest.txt>`, then `start.bat`, then `restore.bat` with that backup.

## 5. The Arabic demo video with voice-over

1. Start HAQQ (`ops\start.bat`). Install Node.js and FFmpeg once:
   `winget install -e --id OpenJS.NodeJS.LTS` and `winget install -e --id Gyan.FFmpeg`
   (close and reopen the window afterwards). For the voice you also need Python:
   `winget install -e --id Python.Python.3.12`.
2. Run **`ops\record-demo.bat`**. It resets the demo data, opens a hidden browser and records the 10-chapter
   Arabic walkthrough from the real app (about 10 minutes, in real time). Output:
   `haqq\docs\video\haqq-demo-ar.mp4` and `haqq-demo-ar.srt` (the narration).
3. Run **`ops\make-voiceover.bat`** (Egyptian male voice) or **`make-voiceover.bat female`**. It needs internet
   (Microsoft neural voices through Edge's free read-aloud service), speaks every caption at natural speed,
   holds the picture when a sentence needs longer, mixes in the calm background music low under the voice, and
   writes `haqq\docs\video\haqq-demo-ar-voice.mp4`.
   Options: `set HQ_MUSIC=none` (no music), `set HQ_MUSIC_VOLUME=-20` (louder music), `set HQ_VOICE_RATE=5`
   (speak 5 % faster).

Re-record whenever the screens change; record on the same day as the reset so "7 days to the notice deadline"
matches the narration.

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| "Docker is not running" | Start Docker Desktop and wait for *running*. |
| `start.bat` fails while building | Check internet access; behind a company proxy configure it in Docker Desktop → Settings → Resources → Proxies. Send the error to PAIS support. |
| Document stays *Queued* | `docker compose logs worker`; restart with `stop.bat` then `start.bat`. |
| Scanned PDF shows no text | Open `http://localhost:8090/api/health/ready` and confirm `"ocr": "available"`. |
| Backup fails at "Verifying" | Do not delete older backups. Run `docker compose logs db`, free disk space, retry. |
| Logins fail after a restore | Compare `.env` with `.env.from-backup` (database password, secret key). |
| No e-mail alerts | Set the `HAQQ_SMTP_*` values in `.env`; in-app alerts work without them. |
