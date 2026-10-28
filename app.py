import http.server
import json
import os
import pathlib
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
import collections
import signal

from urllib.parse import urlparse, parse_qs


ROOT = pathlib.Path(__file__).resolve().parent
DOWNLOADS = ROOT / "downloads"
DOWNLOADS.mkdir(exist_ok=True)

TOKEN = secrets.token_urlsafe(24)

JOBS = {}
LOCK = threading.RLock()
COND = threading.Condition(LOCK)
QUEUE = collections.deque()
PROCESSES = {}

HOST = "0.0.0.0"


def normalize_url(url):
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().rstrip(".")

        if (
            parsed.scheme != "https"
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            return None

        if host in ("youtu.be", "www.youtu.be"):
            video_id = parsed.path.strip("/").split("/")[0]

        elif host in (
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "music.youtube.com",
        ):
            parts = parsed.path.strip("/").split("/")

            if parts[0] in ("shorts", "embed", "live") and len(parts) > 1:
                video_id = parts[1]
            elif parsed.path == "/watch":
                video_id = parse_qs(parsed.query).get("v", [""])[0]
            else:
                return None
        else:
            return None

        if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            return "https://www.youtube.com/watch?v=" + video_id

        return None

    except (ValueError, TypeError):
        return None


def valid_url(url):
    return bool(normalize_url(url))


def ytdlp():
    return [sys.executable, "-m", "yt_dlp"]


def binary_exists(name):
    return shutil.which(name) is not None


def update(job_id, **values):
    with LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(values)


def kill_process(proc):
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
        else:
            os.killpg(proc.pid, signal.SIGKILL)

    except (OSError, subprocess.SubprocessError):
        try:
            proc.kill()
        except OSError:
            pass


def run_job(job_id, url, kind, quality):
    folder = DOWNLOADS / job_id
    folder.mkdir(exist_ok=True)

    # Do not use a shell: the URL is passed as a single argument.
    args = ytdlp() + [
        "--no-playlist",
        "--no-config",
        "--no-cache-dir",
        "--newline",
        "--restrict-filenames",
        "--windows-filenames",
        "--socket-timeout",
        "30",
        "--retries",
        "2",
        "--max-filesize",
        "200M",
        "--js-runtimes",
        "node",
        "--output",
        str(folder / "%(title).120B [%(id)s].%(ext)s"),
    ]

    if kind == "mp3":
        args += [
            "--extract-audio",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "0",
        ]
    else:
        height = "" if quality == "best" else "[height<=" + quality + "]"

        # Prefer MP4-compatible streams, then remux or transcode if needed.
        format_selector = (
            "bestvideo[ext=mp4][vcodec^=avc1]"
            + height
            + "+bestaudio[ext=m4a]/"
            + "bestvideo[ext=mp4]"
            + height
            + "+bestaudio[ext=m4a]/"
            + "best[ext=mp4]"
            + height
            + "/bestvideo"
            + height
            + "+bestaudio/best"
            + height
        )

        args += [
            "--format",
            format_selector,
            "--merge-output-format",
            "mp4",
            "--recode-video",
            "mp4",
        ]

    args += ["--", url]

    try:
        with LOCK:
            if JOBS[job_id]["status"] != "running":
                return

            if os.name == "nt":
                options = {
                    "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP
                }
            else:
                options = {"start_new_session": True}

            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                **options,
            )

            PROCESSES[job_id] = proc

            timer = threading.Timer(
                900,
                lambda: kill_process(proc) if proc.poll() is None else None,
            )
            timer.daemon = True
            timer.start()

        lines = []

        for line in proc.stdout:
            line = line.strip()

            if not line:
                continue

            lines.append(line)
            lines = lines[-25:]

            if (
                "[download]" in line
                or "[ExtractAudio]" in line
                or "[Merger]" in line
                or "[VideoConvertor]" in line
            ):
                with LOCK:
                    if JOBS[job_id]["status"] == "running":
                        update(job_id, message=line[:350])

        code = proc.wait()
        timer.cancel()

        with LOCK:
            PROCESSES.pop(job_id, None)

            if JOBS[job_id]["status"] == "pausing":
                update(
                    job_id,
                    status="paused",
                    message=(
                        "Paused. Resume to put this item "
                        "at the end of the queue."
                    ),
                )
                return

        wanted_suffix = ".mp3" if kind == "mp3" else ".mp4"

        files = [
            path
            for path in folder.iterdir()
            if path.is_file() and path.suffix.lower() == wanted_suffix
        ]

        if code == 0 and files:
            result_file = max(files, key=lambda path: path.stat().st_mtime)

            update(
                job_id,
                status="done",
                message="Ready",
                filename=result_file.name,
                size=result_file.stat().st_size,
            )

        else:
            error = (
                "\n".join(lines[-8:])
                or "Download failed without an error message."
            )

            if (
                "confirm you" in error.lower()
                and "not a bot" in error.lower()
            ):
                error = (
                    "YouTube asked the server to verify it is not a bot. "
                    "This can happen on shared cloud IP addresses; "
                    "changing MP3/MP4 will not fix it. "
                    "The app cannot complete this verification. "
                    "Try updating yt-dlp and, if it still fails, "
                    "use the laptop app. Do not upload account cookies "
                    "to this public app.\n\n"
                    "Original error:\n"
                    + error
                )

            update(job_id, status="error", message=error[-3000:])

    except Exception as exc:
        with LOCK:
            PROCESSES.pop(job_id, None)

            if JOBS[job_id]["status"] == "pausing":
                update(
                    job_id,
                    status="paused",
                    message="Paused. Resume to queue again.",
                )
            else:
                update(job_id, status="error", message=str(exc))


def cleanup_worker():
    while True:
        time.sleep(60)
        cutoff = time.time() - 3600

        with LOCK:
            for job_id, job in list(JOBS.items()):
                folder = DOWNLOADS / job_id

                if (
                    job["status"] in ("done", "error", "paused")
                    and folder.exists()
                    and folder.stat().st_mtime < cutoff
                ):
                    shutil.rmtree(folder, ignore_errors=True)
                    JOBS.pop(job_id, None)


def queue_worker():
    while True:
        with COND:
            while not QUEUE:
                COND.wait()

            job_id = QUEUE.popleft()

            if JOBS[job_id]["status"] != "queued":
                continue

            JOBS[job_id].update(
                status="running",
                message="Starting download…",
            )

            job = JOBS[job_id].copy()

        run_job(
            job_id,
            job["url"],
            job["kind"],
            job["quality"],
        )


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send(self, status, body, ctype="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = body.encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def js(self, status, obj):
        self.send(status, json.dumps(obj))

    def handle_one_request(self):
        self.connection.settimeout(30)
        return super().handle_one_request()

    def authorized(self):
        return secrets.compare_digest(
            self.headers.get("X-App-Token", ""),
            TOKEN,
        )

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/":
            html = (
                (ROOT / "index.html")
                .read_text(encoding="utf-8")
                .replace("__TOKEN__", TOKEN)
            )

            return self.send(
                200,
                html,
                "text/html; charset=utf-8",
            )

        if path == "/api/status":
            if not self.authorized():
                return self.js(403, {"error": "Unauthorized"})

            with LOCK:
                data = list(JOBS.values())

            return self.js(
                200,
                {
                    "jobs": data,
                    "ffmpeg": binary_exists("ffmpeg"),
                    "ffprobe": binary_exists("ffprobe"),
                },
            )

        if path.startswith("/file/"):
            pieces = path.split("/")

            if (
                len(pieces) != 3
                or not re.fullmatch(r"[a-f0-9]{32}", pieces[2])
            ):
                return self.send(404, "Not found", "text/plain")

            with LOCK:
                job = JOBS.get(pieces[2], {}).copy()

            if job.get("status") != "done":
                return self.send(404, "Not found", "text/plain")

            file_path = DOWNLOADS / pieces[2] / job["filename"]

            if not file_path.is_file():
                return self.send(404, "Not found", "text/plain")

            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header(
                "Content-Disposition",
                'attachment; filename="'
                + file_path.name.replace('"', "")
                + '"',
            )
            self.send_header(
                "Content-Length",
                str(file_path.stat().st_size),
            )
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()

            try:
                with file_path.open("rb") as file:
                    shutil.copyfileobj(file, self.wfile)
            except (BrokenPipeError, ConnectionResetError):
                pass

            return

        return self.send(404, "Not found", "text/plain")

    def do_POST(self):
        path = urlparse(self.path).path

        if not self.authorized():
            return self.js(403, {"error": "Unauthorized"})

        if path in ("/api/pause", "/api/resume"):
            try:
                length = int(self.headers.get("Content-Length", "0"))

                if not 0 < length <= 1024:
                    raise ValueError("Invalid request")

                job_id = json.loads(self.rfile.read(length)).get("id")

                with COND:
                    job = JOBS.get(job_id)

                    if not job:
                        raise ValueError("Job not found")

                    if path == "/api/resume":
                        if job["status"] != "paused":
                            raise ValueError("Job is not paused")

                        active = sum(
                            item["status"] in (
                                "queued",
                                "running",
                                "pausing",
                            )
                            for item in JOBS.values()
                        )

                        if active >= 20:
                            raise ValueError("Queue is full")

                        job.update(
                            status="queued",
                            message="Waiting…",
                        )
                        QUEUE.append(job_id)
                        COND.notify()

                    elif job["status"] == "queued":
                        job.update(
                            status="paused",
                            message="Paused. Resume to queue again.",
                        )

                        try:
                            QUEUE.remove(job_id)
                        except ValueError:
                            pass

                    elif job["status"] == "running":
                        job.update(
                            status="pausing",
                            message="Stopping the current download…",
                        )

                        proc = PROCESSES.get(job_id)

                        if proc:
                            threading.Thread(
                                target=kill_process,
                                args=(proc,),
                                daemon=True,
                            ).start()
                        else:
                            job.update(
                                status="paused",
                                message="Paused. Resume to queue again.",
                            )
                    else:
                        raise ValueError("Job cannot be paused")

                return self.js(200, {"ok": True})

            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                return self.js(400, {"error": str(exc)})

        if path != "/api/jobs":
            return self.js(404, {"error": "Not found"})

        try:
            length = int(self.headers.get("Content-Length", "0"))

            if not 0 < length <= 16384:
                raise ValueError("Request too large")

            obj = json.loads(self.rfile.read(length))
            urls = obj.get("urls", [])
            kind = obj.get("kind")
            quality = obj.get("quality")

            if (
                not isinstance(urls, list)
                or not 1 <= len(urls) <= 20
                or any(
                    not isinstance(url, str)
                    or len(url) > 2048
                    or not valid_url(url)
                    for url in urls
                )
            ):
                raise ValueError(
                    "Provide valid YouTube video or Shorts links "
                    "(up to 3 per batch)."
                )

            urls = [normalize_url(url) for url in urls]

            if len(urls) > 3:
                raise ValueError(
                    "Online version accepts at most 3 links at a time."
                )

            if kind not in ("mp4", "mp3"):
                raise ValueError("Invalid format.")

            if quality not in (
                "best",
                "4320",
                "2160",
                "1440",
                "1080",
                "720",
                "480",
                "360",
            ):
                raise ValueError("Invalid quality.")

            if not binary_exists("ffmpeg") or not binary_exists("ffprobe"):
                raise ValueError(
                    "FFmpeg and ffprobe are required. "
                    "Install them and restart the app."
                )

            with LOCK:
                active = sum(
                    job["status"] in ("queued", "running")
                    for job in JOBS.values()
                )

                if active + len(urls) > 20:
                    raise ValueError(
                        "At most 20 jobs can be active at a time."
                    )

                ids = []

                for url in urls:
                    job_id = uuid.uuid4().hex
                    ids.append(job_id)

                    JOBS[job_id] = {
                        "id": job_id,
                        "url": url,
                        "kind": kind,
                        "quality": quality,
                        "status": "queued",
                        "message": "Waiting…",
                    }

            with COND:
                QUEUE.extend(ids)
                COND.notify()

            return self.js(200, {"ids": ids})

        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return self.js(400, {"error": str(exc)})


threading.Thread(target=cleanup_worker, daemon=True).start()
threading.Thread(target=queue_worker, daemon=True).start()


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    try:
        import yt_dlp
    except ImportError:
        print(
            "yt-dlp is missing. Install requirements first: "
            "python -m pip install -r requirements.txt"
        )
        sys.exit(1)

    from importlib.metadata import version

    print("yt-dlp version:", version("yt-dlp"), flush=True)

    port = int(os.environ.get("PORT", "8765"))

    try:
        server = Server((HOST, port), Handler)
    except OSError as exc:
        print("Could not start server:", exc)
        sys.exit(1)

    print(
        f"Server listening on {HOST}:{port}. Press Ctrl+C to stop.",
        flush=True,
    )

    if not binary_exists("ffmpeg") or not binary_exists("ffprobe"):
        print(
            "WARNING: ffmpeg and ffprobe must be installed "
            "and available on PATH.",
            flush=True,
        )

    if os.environ.get("NO_BROWSER") != "1":
        threading.Timer(
            1,
            lambda: webbrowser.open(f"http://127.0.0.1:{port}/"),
        ).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
