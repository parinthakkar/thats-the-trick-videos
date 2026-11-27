#!/usr/bin/env python3
"""Upload pending Shorts to YouTube with the YouTube Data API v3.

A Short is pending when shorts/<YYYY>/<Month>/<DD>/ holds <slug>.json (metadata) and <slug>.mp4,
but no <slug>.youtube.json yet. After each upload the result is written to <slug>.youtube.json
(committed by the workflow), so a Short is never uploaded twice.

<slug>.json fields:
  title (required, max 100 chars), description, tags [..], category_id (default "27" Education),
  made_for_kids (default false), privacy (default "public"),
  publish_at (optional ISO time with offset; if it is still in the future the video is uploaded
  private and YouTube makes it public at that time; if it has passed, it goes public now),
  cover (optional file name of a thumbnail in the same folder, default <slug>-cover.png)

Secrets (env): YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN (authorised for the That's The
Trick channel, scope https://www.googleapis.com/auth/youtube.upload or .../auth/youtube).
"""
import datetime as dt, glob, json, os, sys, time
import requests

MAX_PER_RUN = int(os.environ.get("MAX_PER_RUN", "5"))   # 1 upload = 1,600 of the 10,000 daily quota units


def token():
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"}, timeout=60)
    if r.status_code != 200:
        sys.exit(f"Could not get an access token ({r.status_code}): {r.text}")
    return r.json()["access_token"]


def pending():
    out = []
    for meta in sorted(glob.glob("shorts/*/*/*/*.json")):
        if meta.endswith(".youtube.json"):
            continue
        base = meta[:-5]
        if os.path.exists(base + ".mp4") and not os.path.exists(base + ".youtube.json"):
            out.append(base)
    return out


def upload(base, tok):
    m = json.load(open(base + ".json", encoding="utf-8"))
    slug = os.path.basename(base)
    status = {"privacyStatus": m.get("privacy", "public"),
              "selfDeclaredMadeForKids": bool(m.get("made_for_kids", False)),
              "containsSyntheticMedia": False}
    pa = m.get("publish_at")
    if pa:
        when = dt.datetime.fromisoformat(pa)
        if when > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=15):
            status["privacyStatus"] = "private"
            status["publishAt"] = when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = {"snippet": {"title": m["title"][:100], "description": m.get("description", "")[:5000],
                        "tags": m.get("tags", []), "categoryId": str(m.get("category_id", "27")),
                        "defaultLanguage": "en", "defaultAudioLanguage": "en"},
            "status": status}
    size = os.path.getsize(base + ".mp4")
    h = {"Authorization": f"Bearer {tok}"}
    r = requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                      headers={**h, "Content-Type": "application/json; charset=UTF-8",
                               "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
                      data=json.dumps(body), timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"start upload {r.status_code}: {r.text}")
    loc = r.headers["Location"]
    for attempt in range(4):
        with open(base + ".mp4", "rb") as f:
            r = requests.put(loc, headers={**h, "Content-Type": "video/mp4"}, data=f, timeout=900)
        if r.status_code in (200, 201):
            break
        if r.status_code < 500:
            raise RuntimeError(f"upload {r.status_code}: {r.text}")
        time.sleep(10 * (attempt + 1))
    else:
        raise RuntimeError(f"upload failed after retries: {r.status_code} {r.text}")
    vid = r.json()["id"]
    res = {"slug": slug, "video_id": vid, "url": f"https://www.youtube.com/shorts/{vid}",
           "uploaded_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "requested_privacy": m.get("privacy", "public"), "publish_at": status.get("publishAt")}
    # custom thumbnail (needs a verified channel; Shorts may not show it)
    cover = os.path.join(os.path.dirname(base), m.get("cover", slug + "-cover.png"))
    if os.path.exists(cover):
        with open(cover, "rb") as f:
            t = requests.post(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}",
                              headers={**h, "Content-Type": "image/png"}, data=f, timeout=120)
        res["thumbnail"] = "ok" if t.status_code == 200 else f"skipped ({t.status_code}): {t.text[:300]}"
    # what YouTube actually did with it
    time.sleep(5)
    s = requests.get(f"https://www.googleapis.com/youtube/v3/videos?part=status&id={vid}", headers=h, timeout=60)
    if s.status_code == 200 and s.json().get("items"):
        st = s.json()["items"][0]["status"]
        res["privacy"] = st.get("privacyStatus"); res["upload_status"] = st.get("uploadStatus")
        if st.get("rejectionReason"): res["rejection_reason"] = st["rejectionReason"]
        if st.get("failureReason"): res["failure_reason"] = st["failureReason"]
    json.dump(res, open(base + ".youtube.json", "w", encoding="utf-8"), indent=1)
    print(json.dumps(res))
    return res


def main():
    todo = pending()
    print(f"{len(todo)} pending:", *todo, sep="\n  ")
    if not todo:
        return
    if not all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")):
        print("::warning::YouTube secrets are not set yet (YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN). Nothing uploaded.")
        return
    tok = token(); failed = 0
    for base in todo[:MAX_PER_RUN]:
        try:
            upload(base, tok)
        except Exception as e:
            failed += 1
            print(f"::error::{base}: {e}")
            if "quotaExceeded" in str(e) or "uploadLimitExceeded" in str(e):
                break
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
