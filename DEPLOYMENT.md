# Hosting TerraGuard for free

TerraGuard needs a small Python server (the API) and a website. The setup below runs both in **one container on Render's free plan**, so judges
and users get one public address with no login.

> **What "free" means here.** Render's free web service has 512 MB of memory and a small share of one CPU, and it **goes to sleep after 15 minutes
> without visitors**; the next visitor waits about a minute while it wakes. TerraGuard has been measured to fit (peak about 250 MB), but expect
> some requests to take a few seconds. Render's plans and limits can change, so check https://render.com/docs/free before you start.

## What you need
- A GitHub account with this repository (**public**, so judges can open it).
- A free Render account (https://render.com, sign in with GitHub).
- The processed data on your computer (you have already run the pipeline; see the README).

## Step 1. Pack the data (on your computer)

```bash
python deploy/make_bundle.py
```

This writes `deploy/terraguard-data.tar.gz` (about 300 MB): everything the website reads, repacked into small sorted blocks so a request reads only what it
needs. It leaves out the raw NASA files and West Africa's individual hotspots (about 1 GB), so **individual-hotspot downloads work for Ghana only** on the
hosted copy; for other countries the site says so.

## Step 2. Put the data on GitHub

1. Open your repository on GitHub, then **Releases**, then **Draft a new release**.
2. Tag: `data-v1`. Title: `TerraGuard data`.
3. Drag `deploy/terraguard-data.tar.gz` into the release files, then **Publish release**.
4. Copy the file's address (right-click the file, copy link). It looks like
   `https://github.com/<you>/terraguard/releases/download/data-v1/terraguard-data.tar.gz`.

## Step 3. Create the service on Render

1. In Render choose **New**, then **Blueprint**, and select your repository (it reads `render.yaml`).
   Or **New**, then **Web Service**, pick the repo, set **Runtime: Docker**, **Instance type: Free**, and **Health check path: `/api/health`**.
2. Add the environment variable **`DATA_URL`** with the release address from step 2. (If it is missing or wrong, the container falls back to the `data-v1` release of this repository, so a mistyped setting no longer leaves the site empty.)
3. Create. The first build takes about 10 to 15 minutes (it builds the website and installs the Python packages).
4. When it says **Live**, open the address Render gives you (something like `https://terraguard.onrender.com`).

## Step 4. Check it

- The page opens on **Start here**. Open the **Burning calendar**, choose **Nigeria** in Area, and click a month.
- Search a town, for example *Kumasi*.
- Download the hotspots for a Ghana month.
- Open `<your address>/api/health`: it should say `"status": "ok"`.

## Keeping it awake (optional)
A free service sleeps when idle. Free uptime monitors (for example UptimeRobot) can request `/api/health` every 5 minutes so judges do not meet the
one-minute wake-up. A service that never sleeps uses about 744 of Render's 750 free hours a month, so use it for one service only.

## If something goes wrong
| Symptom | Cause and fix |
|---|---|
| Build log says `not a gzip file`, or "The address did not return the data archive" | `DATA_URL` is not the file's own address. It must contain `/releases/download/` and end in `terraguard-data.tar.gz`; the release page address (`/releases/tag/...`) will not work. The repository must also be public. Test the address in a private window: it should start a 300 MB download immediately. |
| The page says no processed data is available | `DATA_URL` is missing or wrong. Open the service's **Logs**: look for "downloading the data bundle". Fix the variable and redeploy. |
| The service restarts or says "out of memory" | The free instance has 512 MB. Avoid many people running very large custom boxes at once, or move to a larger instance. |
| First visit takes about a minute | The free service was asleep (see above). |
| Hotspot download says "not included in this copy" | Expected outside Ghana on the hosted copy. Run TerraGuard locally for those. |
| Build fails at `npm ci` | Make sure `frontend/package-lock.json` is committed. |

## Updating the data later
Re-run the pipeline, run `python deploy/make_bundle.py`, upload the new archive to a new release (for example `data-v2`), update `DATA_URL`, and redeploy.

## Run the same container on your own computer
```bash
docker build -t terraguard --build-arg DATA_URL=<release address> .
docker run -p 10000:10000 --memory 512m terraguard      # then open http://localhost:10000
```

## What is in the container
`Dockerfile` (a two-stage build: Node builds the website, Python serves it and the API), `deploy/start.sh` (starts the server, fetching the data first if it
is not in the image), `deploy/fetch_data.py`, `render.yaml`, and `backend/requirements.txt` (only what the server needs: no machine-learning packages).
