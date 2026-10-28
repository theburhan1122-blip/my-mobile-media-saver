# Private mobile media saver — experimental Render free deployment

A mobile-friendly, YouTube-only web application for your own authorized downloads. MP4 and MP3, up to 3 links per batch, sequential queue, pause/resume. It runs on a free Render Docker web service, not GitHub Pages, Vercel, or Netlify. It is a prototype, not independently security-audited. Never put passwords or YouTube login cookies in the repository. Use a strong unique password and keep the URL private.

## Important limitations before starting
- Render free services go to sleep after 15 minutes without inbound traffic, can take about a minute to wake, may restart and have ephemeral storage. Jobs and files vanish on restart, redeploy or sleep. Open the page and save your downloaded file to your phone promptly. They are not a backup. Monthly free compute and bandwidth are limited; check https://render.com/docs/free and Render pricing before deployment. Free tier availability and limits can change. Keeping the page open causes polling, counts as traffic, and can consume free hours. Long downloads may be interrupted when the phone closes/sleeps, or when the service restarts.
- Cloud datacenter IP addresses are often blocked by YouTube or require bot verification. This app doesn't bypass such checks or use your account cookies. A link that works on your laptop might fail online; free hosting cannot guarantee YouTube success. Python/ytdlp updates may help but do not guarantee a fix. No paid APIs are used.
- Files capped at 200 MB by yt-dlp where size is known; extraction and conversion can still temporarily use more storage. A job is force-stopped after 15 minutes. Free CPU/memory and bandwidth are constrained; large videos, transcoding, 4K and long jobs may fail. Three links per batch. No promised precise quality. MP3 is converted, not magically improved. Best may prefer a compatible MP4 stream over the highest resolution.
- Basic HTTP authentication is protected in transit by Render HTTPS. Credentials are controlled by your host, not stored in this repo. It is a public Internet service, so strong password and private URL matter. A simple per-IP login throttle is included but proxy behavior can make it ineffective or group users; this is not a comprehensive protection against brute force or abuse. Do not deploy if this risk is unacceptable. Don't use a valuable/reused password. The service runs as an unprivileged user, accepts only canonical YouTube video IDs, and does not accept arbitrary URLs, but yt-dlp contacts upstream sites and redirects; this is not a formally audited network isolation boundary. Never configure personal service credentials in the environment beyond this app's password.
- Download only content you have permission to save and respect platform terms. No DRM bypass.

## Deploy on Render's free tier
1. Sign up for GitHub and Render. Extract this ZIP on your PC. Create a **private GitHub repository** and upload all extracted files, including `Dockerfile`, `app.py`, `index.html`, `requirements.txt`, `.dockerignore` and `.gitignore`. GitHub's browser upload might hide dotfiles: the app still runs without them, but NEVER upload .venv, downloads, passwords, or .env files. No password belongs in code or GitHub.
2. At dashboard.render.com choose **New → Web Service**, connect GitHub and select this repository. Choose Docker as the runtime if not auto-detected. Select **Free** instance (not a paid plan). Check the provider's current pricing and quotas.
3. Under Environment, add key `APP_PASSWORD` with a long, random secret of at least 32 ASCII letters/digits. Generate one on your PC using PowerShell: `py -c "import secrets; print(secrets.token_urlsafe(36))"`. Copy it into Render, not the repository. Keep it in a password manager; don't share it. Use exactly one env var and do not add quotation marks.
4. Deploy. The Docker build can take several minutes. Render supplies PORT and HTTPS. On completion, open the supplied `https://...onrender.com` URL on your phone. If the service slept, wait for it to wake. The browser asks for credentials: username `owner` and your APP_PASSWORD.
5. Paste a YouTube link, choose MP4 or MP3, and add it. Keep the page open while it works; when ready tap **Save a copy** and choose a location on your phone. Do not expect the browser to save automatically. Pause stops the running subprocess; resume puts it at the queue's end and partial data may or may not be reused.
6. Optionally add the site to your phone's home screen from the browser menu. On a shared device, close the browser or clear site data to remove cached login credentials.

A custom subdomain is optional. Render offers its own HTTPS subdomain; using a domain you already own requires adding it in Render settings and configuring DNS there. Owning a custom domain may cost money.

## Update or remove
Changes to the GitHub repo trigger redeployment according to your Render configuration, erasing temporary data. Rotate `APP_PASSWORD` in Render environment settings and redeploy if exposed. Delete the Render service to stop it. Free hosting terms may change and a free service may be unavailable or suspended when allowances are exhausted.

## Trouble
- 401: username is `owner`, password must match Render environment. Browser may cache old credentials.
- Link rejected: use a standard youtube.com/watch?v=ID, youtube.com/shorts/ID, or youtu.be/ID URL.
- YouTube bot check, sign-in or 403: provider/network limitation. Try the local version; don't upload cookies to the public server.
- Nothing happens: inspect Render build/runtime logs, verify a Free Docker web service, APP_PASSWORD length, and wait for wake-up. Do not post your password or complete credential-bearing logs.
- A new deploy/sleep resets jobs. Save copies promptly. Do not use this for long-term storage or valuable data.
