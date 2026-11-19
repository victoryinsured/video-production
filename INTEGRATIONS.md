# Integrations

Every external credential lives in `server/.env` (see `/.env.example`) and is read once in
`server/src/env.ts` — nothing is ever accepted from a request body or stored unencrypted in the
database. This document covers where each credential comes from, what permissions it needs, and
how to verify it actually works before trusting it with a real course (the Diagnostics page's
Test Connection button, backed by `server/src/integrations/*.ts`'s `test*Connection` functions).

## ElevenLabs (narration)

1. Sign in at elevenlabs.io, open **Settings -> API Keys**, create a key.
2. Set `ELEVENLABS_API_KEY`.
3. Add voices to the Voice Library page in the app — either pick from "Available in your
   ElevenLabs account" (populated via `GET /v1/voices`) or paste a voice ID manually if you'd
   rather not expose the full account list.

**Test Connection** calls `GET /v1/voices` — a green result means the key is valid and can list
voices; it does not burn any credits (synthesis is a separate, billed call).

Scripts are sent to ElevenLabs **verbatim** — see `engine/victory_engine/narration.py`. Nothing
rewrites or summarizes your narration text.

## AWS S3 (video + resource storage)

1. Create an IAM user (or role, if running on EC2/ECS) with a policy scoped to the bucket(s)
   you'll use:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:ListBucket"],
         "Resource": ["arn:aws:s3:::your-bucket-name", "arn:aws:s3:::your-bucket-name/*"]
       }
     ]
   }
   ```

2. Set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`. Set `AWS_DEFAULT_BUCKET` as a
   fallback, or set a bucket per-course in Course Defaults (per-course wins).
3. Uploaded keys look like `<awsKeyPrefix-or-course-slug>/<module-number>/<lesson-number>/video.mp4`
   for lesson videos, and the same path plus `/resources/<filename>` for lesson resources.

**Test Connection** does more than confirm the bucket exists: `HeadBucket` alone can pass even
with a read-only policy, so it also writes and deletes a small marker object
(`.victory-connection-test/<timestamp>.txt`) to prove the credentials can really upload. If it
fails, the message now distinguishes a missing bucket (404) from an access problem (403) instead
of the AWS SDK's generic error for either (HeadBucket returns an empty body on both, which the
SDK's XML parser otherwise collapses into an unhelpful "UnknownError" — see
`server/src/integrations/aws.ts`'s `describeS3Error`).

## Bunny Stream (video hosting/CDN)

1. Create a Video Library at dash.bunny.net/stream.
2. Open the library -> **API** tab for its API key and library ID.
3. Set `BUNNY_STREAM_API_KEY` and `BUNNY_STREAM_LIBRARY_ID` (or set a library ID per course in
   Course Defaults — per-course wins). Only set `BUNNY_CDN_HOSTNAME` if your pull zone doesn't
   follow the default `vz-<library-id>.b-cdn.net` pattern.

**Test Connection** fetches the library's own info (`GET /library/<id>`) with your key — this
specifically proves the key is valid *for that library*, not just valid in general (an API key
scoped to a different library in the same account would still fail here).

## Moodle (publishing)

Victory Video Studio publishes each lesson as a Moodle **URL activity** (pointing at the Bunny
Stream playback URL) inside a section matching the lesson's module, using Moodle's web services
REST API.

1. As a Moodle admin: **Site administration -> Plugins -> Web services -> External services**,
   create (or reuse) a service, and enable these functions on it:
   - `core_webservice_get_site_info`
   - `core_course_edit_section`
   - `core_course_edit_module`
2. **Site administration -> Plugins -> Web services -> Manage tokens**, create a token for a user
   with editing rights on the course(s) you'll publish into.
3. Set `MOODLE_BASE_URL` (no trailing slash) and `MOODLE_TOKEN`.
4. Set the course's **Moodle course ID** in Course Defaults (the numeric ID from the course's URL,
   e.g. `course/view.php?id=42` -> `42`).

**Test Connection** calls `core_webservice_get_site_info` and additionally checks the token's
function list for `core_course_edit_module` — a token can be valid (site info succeeds) while
its assigned role still lacks the specific permission this app needs to publish, and that would
otherwise only surface as a confusing failure the first time a real lesson tries to publish.

## Optional: AI-assisted descriptions

`AI_PROVIDER=anthropic` + `AI_API_KEY` enables a "Suggest description" convenience in the lesson
editor that drafts a one-sentence video description from the script. Entirely optional — every
other feature, including the full generate-and-publish pipeline, works with this unset.

## What's never sent anywhere automatically

- Your curriculum documents and narration scripts are only sent to ElevenLabs (as narration text)
  and used locally for slide rendering. They are never sent to AWS, Bunny, or Moodle except as the
  finished video/resource files those services host.
- No integration credential is ever returned by any API response — `server/src/env.ts` is the only
  place they're read, and routes only expose booleans ("is this configured") plus Test Connection
  results.
