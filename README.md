# Mobile Media Saver — public test version for Render

A mobile-friendly YouTube downloader for MP4 and MP3. This version has **no password or login**. Anyone who discovers the URL can use it, see the shared job list including video links, and download completed files while they exist. A public GitHub repository does not restrict access to the deployed app. This is an experimental public test, not a secure private deployment. No YouTube login is configured. Never upload credentials or personal cookies. Do not use it for private or sensitive data.

## Free-tier limitations
Render Free spins down after 15 minutes without traffic, may take a minute to wake, and loses jobs and downloaded files on sleep, restart, or redeploy. Download results to your phone promptly. Service may restart at any time. Free tiers have quotas and can change. Render says that if you have a payment method, exceeding some bandwidth/build allowances can incur charges; if you haven't added one, services or builds may instead be suspended. See https://render.com/docs/free and https://dashboard.render.com/billing#included-usage. Keeping the webpage open polls the server and can keep it awake and use free hours.

Cloud servers can be blocked by YouTube or face bot checks. Success is not guaranteed, and the app does not bypass these checks. Up to 3 links per batch; jobs run sequentially. Downloads are stopped after 15 minutes. yt-dlp's 200 MB maximum is best effort when the source size is known, not a hard disk-use limit; conversions can temporarily use more. Free CPU, memory, storage and bandwidth are limited. MP3 uses FFmpeg. Long and high-resolution jobs can fail. Pause stops the process; resume requeues it and might have to start over. Only download content you have permission to save.

Because this URL is public, other people can use your resources, fill the queue, view jobs and cause quota exhaustion. The app limits active jobs but does not provide full rate limiting, user isolation, or an audited security boundary. The URL cannot be made private simply by not sharing it. Stop or delete the service if unknown jobs appear, or deploy a properly protected version instead.

## Update your existing public GitHub repository
1. Download and extract this ZIP into a NEW folder. Open the extracted folder. If Windows hides extensions, the file shown as `Dockerfile` is the file named exactly `Dockerfile` (no extension).
2. In your existing GitHub repo, open the **root** folder. Select **Add file → Upload files**.
3. Drag or select the new `app.py`, `index.html`, `requirements.txt`, `Dockerfile`, and `README.md` from the extracted folder. Confirm you are replacing existing files, not placing them in a subfolder. You may also upload `.dockerignore` and `.gitignore` if shown; they aren't required for this test. Do not upload `.venv`, downloads, passwords, or cookies. Scroll down and click **Commit changes**. On the repository's main page, open `app.py` and verify it is the new version.
4. In Render, open your existing web service and check Settings: repository is the right one, branch matches the branch you updated (normally `main`), runtime/language is **Docker**, the Dockerfile is at the repo root, and instance type is **Free**. If auto-deploy is on, committing triggers a deployment. Otherwise use **Manual Deploy → Deploy latest commit**. Wait for the latest deploy to finish.
5. If you added `APP_PASSWORD` previously, remove it under **Environment** and save changes/redeploy if prompted. The new version does not read or need it. Keep other environment variables as they are; Render sets PORT automatically.
6. Open your `https://...onrender.com` URL on your phone. No login should appear. If the service was idle it may take about a minute to wake. Paste an authorized YouTube video or Shorts link, select MP4 or MP3, and start the download. Keep the page open while it runs and tap **Save a copy** once done.

## If creating a new service instead
1. Sign up at https://dashboard.render.com/register and connect your public GitHub repo.
2. Choose **New → Web Service**, connect the repo, set Language/Runtime to **Docker**, and select the **Free** compute plan. Leave root directory empty (assuming the files are at repo root). No APP_PASSWORD, build command, start command, or custom PORT is required. Create the service.
3. Wait for deploy and open the supplied HTTPS URL on your phone.

## Troubleshooting
- Failed deploy: open Render's **Deploys** or **Logs**, locate the FIRST error (Docker build, dependency install, or Python startup), and share the relevant lines without secrets. Check you deployed the latest commit on the correct branch. There is no guarantee that removing password fixes an unrelated error.
- Website still requests login: wait for the new successful deploy, ensure the right URL/service and latest commit, and check whether a separate proxy or browser-saved login is involved.
- A deployment reports a missing Dockerfile: check filename, case, and root path. Docker should be the runtime.
- YouTube shows bot check, 403 or sign-in required: the cloud host may be blocked. Try the laptop version instead; do not upload private cookies.
- A prior download disappeared: Render Free uses ephemeral storage. Save copies to your phone promptly.
