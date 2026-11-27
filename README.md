# That's The Trick: video hosting + YouTube upload

One folder per day: `shorts/<YYYY>/<MonthName>/<DD>/`. For each Short:

- `<slug>.mp4`: the video
- `<slug>-cover.png`: the cover / thumbnail
- `<slug>.json`: YouTube metadata (title, description, tags, optional `publish_at`)
- `<slug>.youtube.json`: written by the uploader after the upload (video id, link, privacy)

The workflow `.github/workflows/youtube-upload.yml` runs on every push to main (and every 6 hours
as a retry). It uploads each Short that has a `.json` and an `.mp4` but no `.youtube.json` yet,
straight to YouTube through the YouTube Data API. No Metricool, no monthly post limit.
(The API quota is 10,000 units a day; one upload uses 1,600, so up to 6 a day.)

## One-time setup (about 15 minutes)

You can reuse the Google Cloud project you already use for the Dadi Ke Kisse uploader.

1. **OAuth client.** Go to https://console.cloud.google.com/ and open that project (or create one and
   enable "YouTube Data API v3"). Under *APIs & Services → Credentials → Create credentials →
   OAuth client ID*, pick **Web application** and add this authorised redirect URI:
   `https://developers.google.com/oauthplayground`. Copy the **Client ID** and **Client secret**.
2. **Consent screen.** Under *OAuth consent screen*, the publishing status must be **In production**.
   In "Testing", the token expires after 7 days and the uploads stop.
3. **Refresh token for the That's The Trick channel.**
   - Open https://developers.google.com/oauthplayground and click the gear icon (top right).
   - Tick "Use your own OAuth credentials" and paste the Client ID and secret.
   - In "Step 1", type `https://www.googleapis.com/auth/youtube.upload` and click *Authorize APIs*.
   - Sign in, and when Google asks which channel, **pick That's The Trick**, not Dadi Ke Kisse.
   - In "Step 2", click *Exchange authorization code for tokens* and copy the **Refresh token**.
4. **GitHub secrets.** In this repo, go to *Settings → Secrets and variables → Actions → New
   repository secret* and add three secrets: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
5. **Run it.** Go to *Actions → Upload Shorts to YouTube → Run workflow*. Pending Shorts upload, and the
   link appears in each `<slug>.youtube.json`.

**If a video comes out "private (locked)":** YouTube keeps API uploads from unaudited Google Cloud
projects private. Use the same project as Dadi Ke Kisse if its uploads go public. Otherwise request
the free audit at https://support.google.com/youtube/contact/yt_api_form.
