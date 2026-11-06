#!/usr/bin/env bash
set -euo pipefail

# The one deploy command (`npm run deploy:local`): the gated build, checked on a preview channel, then promoted to live.
# Each step's limit is about three times its usual run.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT/app"
source "$REPO_ROOT/app/scripts/limits.sh"

echo "=== [1/8] Firebase sign-in ==="
accounts=$(timed 60 "signed-in accounts" npx --no-install firebase login:list --json | node -e 'let s = "";
  process.stdin.on("data", (d) => (s += d))
    .on("end", () => process.stdout.write(String(JSON.parse(s).result?.length ?? 0)));')
if [[ "$accounts" == "0" ]]; then
  echo "Not signed in to Firebase: run npx firebase login --no-localhost" >&2
  exit 1
fi
# vite copies app/public/ whole into the build: a stray file there would ship.
if [[ -n "$(git status --porcelain)" ]]; then
  echo "The tree is not clean: commit or remove what git status lists before deploying" >&2
  exit 1
fi

echo "=== [2/8] Gates ==="
if bash "$REPO_ROOT/app/scripts/gates/passed.sh"; then
  echo "The gate passed here for this tree with Node $(node -v): not run again"
else
  bash "$REPO_ROOT/app/scripts/gates/check.sh"
fi

PROJECT="$(cd "$REPO_ROOT" && python3 -c 'from radar import paths; print(paths.firebase_project())')"

# The Firebase CLI reads the function from a Python 3.12 venv beside it, kept between deploys. The indexes go before
# the build: its queries need them.
echo "=== [3/8] Rules, indexes and the ask function ==="
FUNCTIONS="$REPO_ROOT/dist/functions"
mkdir -p "$FUNCTIONS"
rsync -a --delete --exclude venv --exclude tests --exclude __pycache__ \
  "$REPO_ROOT/radar" "$REPO_ROOT/contracts" "$REPO_ROOT/data" "$REPO_ROOT/.firebaserc" "$FUNCTIONS/"
{ cat "$REPO_ROOT/radar/requirements.txt"; echo "firebase-functions>=0.6.0"; } > "$FUNCTIONS/requirements.txt"
cp "$REPO_ROOT/radar/adapters/web/function.py" "$FUNCTIONS/main.py"
[[ -d "$FUNCTIONS/venv" ]] || timed 120 "the function's venv" uv venv --quiet --python 3.12 "$FUNCTIONS/venv"
timed 300 "the function's packages" uv pip install --quiet --python "$FUNCTIONS/venv/bin/python" \
  -r "$FUNCTIONS/requirements.txt"
timed 600 "firebase deploy" npx --no-install firebase deploy \
  --only firestore:rules,firestore:indexes,storage,functions \
  --project "$PROJECT" --force

# A short-lived token for the steps that read the project's store, in the environment: never on a command line
# another process could read.
export MVR_ACCESS_TOKEN="$(timed 60 "access token" gcloud auth application-default print-access-token)"
echo "=== [4/8] The public read model, up to date with the views ==="
(cd "$REPO_ROOT" && timed 300 "reproject" python3 -m radar --project "$PROJECT" --yes store reproject)

# Nothing the emulators or the fixtures use may reach this build.
echo "=== [5/8] Production build from the project's Firestore ==="
# The admin is in the build, lazily, with the project's public web config (the only key the browser reads).
WEB_APP="$(timed 60 "web app" npx --no-install firebase apps:list WEB --project "$PROJECT" --json | node -e 'let s = "";
  process.stdin.on("data", (d) => (s += d)).on("end", () => process.stdout.write(JSON.parse(s).result[0].appId));')"
WEB_CONFIG="$(timed 60 "web config" npx --no-install firebase apps:sdkconfig WEB "$WEB_APP" --project "$PROJECT" \
  --json)"
web() {
  node -e 'process.stdout.write(JSON.parse(process.argv[1]).result.sdkConfig[process.argv[2]])' "$WEB_CONFIG" "$1"
}
# App Check on a reader's report: the reCAPTCHA Enterprise key the web app is registered with.
SITE_KEY="$(timed 60 "App Check site key" node -e '
const headers = { Authorization: `Bearer ${process.env.MVR_ACCESS_TOKEN}`, "x-goog-user-project": process.argv[2] };
fetch(process.argv[1], { headers }).then(async (res) => {
  if (!res.ok) throw new Error(`App Check config: HTTP ${res.status}`);
  process.stdout.write((await res.json()).siteKey);
});' \
  "https://firebaseappcheck.googleapis.com/v1/projects/$PROJECT/apps/$WEB_APP/recaptchaEnterpriseConfig" "$PROJECT")"
timed 300 "production build" env -u MVR_FIRESTORE_DOCS -u MVR_READ_MODEL_DIR -u MVR_MEDIA_BASE -u MVR_STORAGE_BUCKET \
  -u MVR_DATA -u FIRESTORE_EMULATOR_HOST -u FIREBASE_STORAGE_EMULATOR_HOST -u FIREBASE_AUTH_EMULATOR_HOST \
  -u VITE_FIREBASE_AUTH_EMULATOR \
  VITE_ENABLE_ADMIN=true VITE_FIREBASE_API_KEY="$(web apiKey)" VITE_FIREBASE_AUTH_DOMAIN="$(web authDomain)" \
  VITE_FIREBASE_PROJECT_ID="$(web projectId)" VITE_FIREBASE_APP_ID="$(web appId)" VITE_APPCHECK_SITE_KEY="$SITE_KEY" \
  MVR_PROJECT="$PROJECT" npm run build

echo "=== [6/8] The search index, up to date with the project's read model ==="
(cd "$REPO_ROOT" && timed 300 "index update" python3 -m radar --project "$PROJECT" --yes index update)

echo "=== [7/8] Preview channel and smoke ==="
CHANNEL="$(timed 300 "preview channel" npx --no-install firebase hosting:channel:deploy preview-deploy \
  --project "$PROJECT" --expires 7d --json)"
PREVIEW="$(node -e 'process.stdout.write(Object.values(JSON.parse(process.argv[1]).result)[0].url)' "$CHANNEL")"
echo "Preview: $PREVIEW"
timed 180 "smoke on the preview" env SMOKE_BASE_URL="$PREVIEW" npx playwright test

echo "=== [8/8] Promoting the previewed build to live ==="
timed 120 "promote" npx --no-install firebase hosting:clone "$PROJECT:preview-deploy" "$PROJECT:live"
