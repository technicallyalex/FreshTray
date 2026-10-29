"""FreshBooks OAuth and API. No request bodies, URLs or tokens are logged."""
from datetime import datetime, timedelta, timezone
import hmac
import json
import secrets
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, parse_qs, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .model import matching_entry
from . import __version__

API = "https://api.freshbooks.com"
SCOPES = "user:profile:read user:clients:read user:projects:read user:billable_items:read user:time_entries:read user:time_entries:write"
DEFAULT_REDIRECT = "https://localhost:8765/callback"


class ApiError(Exception):
    def __init__(self, message, status=None, uncertain=False):
        super().__init__(message)
        self.status, self.uncertain = status, uncertain


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward Authorization or OAuth bodies to a redirect target.


class Transport:
    def __init__(self):
        self.opener = build_opener(NoRedirect())

    def __call__(self, method, path, body=None, token=None):
        headers = {"Accept": "application/json", "User-Agent": "FreshTray/" + __version__}
        if token:
            headers["Authorization"] = "Bearer " + token
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        try:
            request = Request(API + path, data=data, headers=headers, method=method)
            with self.opener.open(request, timeout=25) as response:
                raw = response.read(8 * 1024 * 1024)
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            exc.close()
            messages = {400: "FreshBooks rejected the fields or authorization code.",
                        401: "FreshBooks authorization expired. Reconnect in Settings.",
                        403: "FreshBooks denied access. Check your role and app scopes.",
                        404: "This FreshBooks item is no longer available. Reload the lists.",
                        409: "FreshBooks reported a conflict. Review your entries.",
                        422: "FreshBooks could not accept this client/project/service or time entry.",
                        429: "FreshBooks is rate limiting requests. Wait a minute, then try again."}
            if exc.code == 422 and method == "GET":
                messages[422] = "FreshBooks rejected this view's filters or date range."
            raise ApiError(messages.get(exc.code, "FreshBooks returned an unexpected response."),
                           exc.code, exc.code >= 500 or 300 <= exc.code < 400 or exc.code == 408) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise ApiError("Connection interrupted or response unreadable. Check your network.", uncertain=True) from None


class OAuthAttempt:
    def __init__(self, credentials):
        redirect = urlsplit(credentials["redirect_uri"])
        if (redirect.scheme != "https" or not redirect.hostname or redirect.query or redirect.fragment
                or redirect.username or redirect.password):
            raise ValueError("Redirect URI must be HTTPS with no query, fragment or user info.")
        if not credentials["client_id"].strip() or not credentials["client_secret"].strip():
            raise ValueError("Enter your FreshBooks app's client ID and client secret.")
        self.credentials = dict(credentials)
        self.state = secrets.token_urlsafe(32)
        self.created = time.monotonic()
        self.consumed = False

    def url(self):
        return "https://auth.freshbooks.com/oauth/authorize/?" + urlencode({
            "response_type": "code", "client_id": self.credentials["client_id"],
            "redirect_uri": self.credentials["redirect_uri"], "state": self.state, "scope": SCOPES})

    def consume(self, returned_url):
        if self.consumed or time.monotonic() - self.created > 300:
            raise ValueError("This connection attempt expired. Start a new browser sign-in.")
        given, wanted = urlsplit(returned_url.strip()), urlsplit(self.credentials["redirect_uri"])
        if (given.scheme, given.netloc, given.path) != (wanted.scheme, wanted.netloc, wanted.path) or given.fragment:
            raise ValueError("Paste the complete redirect URL from this sign-in's browser address bar.")
        query = parse_qs(given.query, keep_blank_values=True)
        states = query.get("state", [])
        if len(states) != 1 or not hmac.compare_digest(states[0], self.state):
            raise ValueError("Sign-in state did not match. Start a new connection from this app.")
        if "error" in query:
            self.consumed = True
            raise ValueError("FreshBooks authorization was declined. Start again when ready.")
        codes = query.get("code", [])
        if len(codes) != 1 or not codes[0]:
            raise ValueError("The return URL has no single authorization code.")
        self.consumed = True
        return codes[0]


class FreshBooks:
    def __init__(self, vault, transport=None):
        self.vault = vault
        self.transport = transport or Transport()
        self.lock = threading.RLock()

    @property
    def connected(self):
        return bool(self.vault.get("tokens"))

    def _save_tokens(self, result):
        if not result.get("access_token") or not result.get("refresh_token"):
            raise ApiError("FreshBooks returned an incomplete token pair. Reconnect.", uncertain=True)
        pair = {"access_token": result["access_token"], "refresh_token": result["refresh_token"],
                "expires_at": time.time() + int(result.get("expires_in", 0))}
        try:
            self.vault.update(tokens=pair, refresh_inflight=False)
        except OSError:
            raise ApiError("Windows could not save the rotated tokens. Fix local storage and reconnect.") from None

    def connect(self, attempt, returned_url):
        with self.lock:
            code = attempt.consume(returned_url)
            credentials = attempt.credentials
            # Persist the user-provided app secret only in the DPAPI vault.
            self.vault.update(credentials=credentials, tokens=None, refresh_inflight=True)
            result = self.transport("POST", "/auth/oauth/token", dict(credentials, code=code, grant_type="authorization_code"))
            self._save_tokens(result)

    def _token(self):
        pair = self.vault.get("tokens")
        if not pair or self.vault.get("refresh_inflight"):
            raise ApiError("Connect to FreshBooks in Settings. An interrupted sign-in/refresh needs reconnecting.")
        if pair["expires_at"] > time.time() + 90:
            return pair["access_token"]
        # Refresh is one-use. A crash/timeout must not reuse the previous token.
        self.vault.update(refresh_inflight=True)
        credentials = self.vault.get("credentials")
        result = self.transport("POST", "/auth/oauth/token", dict(credentials, grant_type="refresh_token", refresh_token=pair["refresh_token"]))
        self._save_tokens(result)
        return self.vault.get("tokens")["access_token"]

    def request(self, method, path, body=None):
        with self.lock:
            token = self._token()
            # No automatic retries, including for time-entry POSTs.
            return self.transport(method, path, body, token)

    def profile(self):
        return self.request("GET", "/auth/api/v1/users/me")["response"]

    def pages(self, path, key, accounting=False):
        result, seen = [], set()
        for page in range(1, 1001):
            separator = "&" if "?" in path else "?"
            response = self.request("GET", path + separator + urlencode({"page": page, "per_page": 100}))
            root = response["response"]["result"] if accounting else response
            items = root[key]
            meta = root if accounting else root.get("meta", {})
            for item in items:
                ident = item.get("id", item.get("userid"))
                if ident not in seen:
                    result.append(item)
                    seen.add(ident)
            if page >= int(meta.get("pages", 1)):
                return result
            if not items:
                raise ApiError("FreshBooks pagination ended early. Reload before continuing.")
        raise ApiError("Too many FreshBooks pages. Narrow the query before continuing.")

    def catalog(self, business):
        bid = int(business["id"])
        account = quote(str(business["account_id"]), safe="")
        clients = self.pages(f"/accounting/account/{account}/users/clients", "clients", True)
        warnings = []
        try:
            projects = self.pages(f"/projects/business/{bid}/projects", "projects")
        except ApiError as exc:
            projects = []
            warnings.append("Projects unavailable: " + str(exc))
        try:
            services = self.pages(f"/comments/business/{bid}/services", "services")
        except ApiError as exc:
            services = []
            warnings.append("Services unavailable: " + str(exc))
        return ([c for c in clients if c.get("vis_state", 0) == 0],
                [p for p in projects if p.get("active", True) and not p.get("complete")],
                [s for s in services if s.get("vis_state", 0) == 0], warnings)

    def submit(self, business_id, payload):
        with self.lock:
            if self.vault.get("pending"):
                raise ApiError("A previous submission needs checking. Use Check pending first.")
            token = self._token()  # Refresh failures happen before journaling a new entry.
            self.vault.update(pending={"business_id": int(business_id), "payload": payload})
            try:
                response = self.transport("POST", f"/timetracking/business/{int(business_id)}/time_entries", payload, token)
            except ApiError as exc:
                if not exc.uncertain:
                    self.vault.update(pending=None)
                raise
            entry = response.get("time_entry", {})
            if not entry.get("id"):
                raise ApiError("FreshBooks did not confirm an entry ID. Use Check pending.", uncertain=True)
            self.vault.update(pending=None, last_success={"business_id": int(business_id), "payload": payload, "id": entry["id"]})
            return entry

    def entries_for_month(self, business_id, month, identity_id):
        from .history_model import month_bounds, month_entries
        start, end = month_bounds(month)
        # The default feed is the signed-in user's time. Explicit identity_id is
        # rejected on this list API; still enforce identity locally on every row.
        params = urlencode({"started_from": start, "started_to": end,
                            "include_deleted": "false", "include_unlogged": "false"})
        entries = self.pages(f"/timetracking/business/{int(business_id)}/time_entries?{params}", "time_entries")
        # Enforce local-date boundaries even if the API's end filter is inclusive.
        return month_entries(entries, month, identity_id)

    def get_entry(self, business_id, entry_id):
        return self.request("GET", f"/timetracking/business/{int(business_id)}/time_entries/{int(entry_id)}")["time_entry"]

    def update_entry(self, business_id, entry_id, payload, original):
        from .history_model import entry_signature, edit_restriction
        with self.lock:
            if self.vault.get("pending"):
                raise ApiError("A previous save needs checking. Use Check pending first.")
            current = self.get_entry(business_id, entry_id)
            if entry_signature(current) != entry_signature(original):
                raise ApiError("This entry changed in FreshBooks. Reload it from the calendar before editing.")
            if str(current.get("identity_id", payload["time_entry"]["identity_id"])) != str(payload["time_entry"]["identity_id"]):
                raise ApiError("Only your own time entries can be edited here.")
            restriction = edit_restriction(current)
            if restriction:
                raise ApiError(restriction)
            token = self._token()
            pending = {"operation": "update", "business_id": int(business_id),
                       "entry_id": int(entry_id), "payload": payload}
            self.vault.update(pending=pending)
            try:
                response = self.transport("PUT", f"/timetracking/business/{int(business_id)}/time_entries/{int(entry_id)}", payload, token)
            except ApiError as exc:
                if not exc.uncertain:
                    self.vault.update(pending=None)
                raise
            entry = response.get("time_entry", {})
            if str(entry.get("id")) != str(entry_id):
                raise ApiError("FreshBooks did not confirm the updated entry. Use Check pending.", uncertain=True)
            self.vault.update(pending=None, last_success={**pending, "id": entry["id"]})
            return entry


    def check_pending(self):
        with self.lock:
            pending = self.vault.get("pending")
            if not pending:
                return None
            expected = pending["payload"]["time_entry"]
            if pending.get("operation") == "update":
                entry = self.get_entry(pending["business_id"], pending["entry_id"])
                if matching_entry(expected, entry):
                    self.vault.update(pending=None, last_success={**pending, "id": entry["id"]})
                    return entry
                return {"unresolved": True, "matches": 0}
            start = datetime.fromisoformat(expected["started_at"].replace("Z", "+00:00"))
            params = urlencode({"started_from": (start - timedelta(seconds=1)).isoformat(),
                                "started_to": (start + timedelta(seconds=1)).isoformat()})
            entries = self.pages(f'/timetracking/business/{int(pending["business_id"])}/time_entries?{params}', "time_entries")
            matches = [e for e in entries if matching_entry(expected, e)]
            if len(matches) == 1:
                self.vault.update(pending=None, last_success={**pending, "id": matches[0]["id"]})
                return matches[0]
            return {"unresolved": True, "matches": len(matches)}

    def disconnect(self):
        with self.lock:
            if self.vault.get("pending"):
                raise ValueError("Resolve the pending entry before disconnecting.")
            tokens, credentials = self.vault.get("tokens"), self.vault.get("credentials")
            if tokens and credentials:
                # Keep local credentials on failure so the user can retry revocation.
                self.transport("POST", "/auth/oauth/revoke", dict(
                    client_id=credentials["client_id"], client_secret=credentials["client_secret"],
                    token=tokens["refresh_token"]))
            self.vault.update(tokens=None, credentials=None, refresh_inflight=False)
