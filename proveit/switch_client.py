"""A small client for the Switch agent protocol, standard library only.

Down: one server-sent event stream per connection. Up: HTTP operations.
See https://docs.switchagents.ai/switch-rooms/internals/agent-protocol.md

Prove It's Intake agent holds one connection per room it works in, so a
reply can be posted into the right room and thread with `post_message`.
"""

import json
import logging
import threading
import time
import urllib.error
import urllib.request
import uuid

log = logging.getLogger("proveit.switch")


class SwitchError(RuntimeError):
    def __init__(self, status, detail):
        super().__init__("HTTP %s: %s" % (status, detail))
        self.status = status
        self.detail = detail


def _request(method, url, body=None, headers=None, timeout=30, opener=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, data=data, headers=dict(headers or {}))
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with (opener.open if opener else urllib.request.urlopen)(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raise SwitchError(exc.code, exc.read().decode(errors="replace")[:500]) from None


def register_agent(api_url, registration_token, name, description, display_name=None, overwrite=False):
    """Register a protocol agent. Returns {id, api_key}; the key is shown once."""
    profile = {
        "connection_model": "always_on",
        "message_exchange": True,
        "pre_invocation_mediation": [],
        "post_invocation_mediation": [],
        "event_reporting": [],
    }
    return _request("POST", api_url.rstrip("/") + "/agents", {
        "name": name,
        "description": description,
        "display_name": display_name,
        "connector_type": "custom",
        "integration_profile": profile,
        "overwrite": overwrite,
    }, {"Authorization": "Bearer " + registration_token})


def open_to_everyone(api_url, admin_email, admin_password, agent_id):
    """Clear the agent's addressing policy so reporters may talk to it.

    New agents answer only their owner. Intake must answer anyone who posts
    in the intake room; the room's membership is the wall, and Intake can
    run nothing. Uses the Gateway API, as an admin.
    """
    import http.cookiejar
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    base = api_url.rstrip("/") + "/gateway"
    _request("POST", base + "/auth/login", {"email": admin_email, "password": admin_password}, opener=opener)
    return _request("PUT", base + "/agents/%s/addressing-policy" % agent_id, {"policy": None}, opener=opener)


class Agent:
    def __init__(self, api_url, agent_id, api_key, client_name="proveit-intake"):
        self.api = api_url.rstrip("/")
        self.id = agent_id
        self.key = api_key
        self.client_name = client_name
        self._stop = threading.Event()

    # --- operations -------------------------------------------------------
    def _headers(self, connection_id=None):
        headers = {"Authorization": "Bearer " + self.key}
        if connection_id:
            headers["X-Switch-Connection-Id"] = connection_id
        return headers

    def op(self, name, args=None, connection_id=None, timeout=30):
        result = _request("POST", "%s/agents/%s/ops/%s" % (self.api, self.id, name), args or {},
                          self._headers(connection_id), timeout=timeout)
        return (result or {}).get("result")

    def rooms(self):
        return self.op("list_rooms") or []

    def room_id(self, name):
        for room in self.rooms():
            if room["name"] == name or room["room_id"] == name:
                return room["room_id"]
        return None

    def create_room(self, name, description, agent_names, user_names=None):
        return self.op("create_room", {"name": name, "description": description,
                                       "agent_names": agent_names, "user_names": user_names or None})

    def link_rooms(self, source_room_id, target_room_id, label):
        return self.op("link_rooms", {"source_room_id": source_room_id,
                                      "target_room_id": target_room_id, "label": label})

    # --- connections ------------------------------------------------------
    def connect(self, room_id, on_event):
        conn = Connection(self, room_id, on_event)
        conn.start()
        return conn

    def stop(self):
        self._stop.set()


class Connection:
    """One SSE stream bound to one room, with its heartbeat."""

    def __init__(self, agent, room_id, on_event):
        self.agent = agent
        self.room_id = room_id
        self.on_event = on_event
        self.id = str(uuid.uuid4())  # kept across reconnects, per the protocol
        self.last_sequence = None
        self.ready = threading.Event()

    def start(self):
        threading.Thread(target=self._stream_forever, name="sse-%s" % self.room_id[:8], daemon=True).start()
        threading.Thread(target=self._beat_forever, name="beat-%s" % self.room_id[:8], daemon=True).start()

    def post(self, body, thread_id=None):
        """Post into this connection's room, optionally inside a thread."""
        args = {"body": body}
        if thread_id:
            args["thread_id"] = thread_id
        return self.agent.op("post_message", args, connection_id=self.id)

    def _url(self):
        a = self.agent
        url = ("%s/agents/%s/events?connection_id=%s&scope=single&filter=all&rooms=%s&client=%s&client_version=1.0.0"
               % (a.api, a.id, self.id, self.room_id, a.client_name))
        if self.last_sequence is None:
            url += "&start_from=head"
        return url

    def _stream_forever(self):
        backoff = 1
        while not self.agent._stop.is_set():
            headers = self.agent._headers()
            headers["Accept"] = "text/event-stream"
            if self.last_sequence is not None:
                headers["Last-Event-ID"] = str(self.last_sequence)
            try:
                req = urllib.request.Request(self._url(), headers=headers)
                with urllib.request.urlopen(req, timeout=90) as stream:
                    backoff = 1
                    self._read(stream)
            except Exception as exc:  # reconnect on anything; the connection id survives
                log.warning("stream for room %s dropped (%s); reconnecting", self.room_id[:8], exc)
                self.ready.clear()
            time.sleep(backoff)
            backoff = min(backoff * 2, 15)

    def _read(self, stream):
        event_type, data_lines, event_id = None, [], None
        for raw in stream:
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                if data_lines:
                    self._dispatch(event_type, "\n".join(data_lines), event_id)
                event_type, data_lines, event_id = None, [], None
                continue
            if line.startswith(":"):
                continue  # keepalive comment
            field, _, value = line.partition(":")
            value = value[1:] if value.startswith(" ") else value
            if field == "event":
                event_type = value
            elif field == "data":
                data_lines.append(value)
            elif field == "id":
                event_id = value

    def _dispatch(self, event_type, data, event_id):
        try:
            frame = json.loads(data)
        except ValueError:
            return
        if event_id is not None:
            self.last_sequence = int(event_id)
        if event_type == "connection_state":
            self.ready.set()
            return
        if event_type == "evicted":
            log.warning("connection for room %s evicted: %s", self.room_id[:8], frame.get("reason"))
            return
        if event_type in ("gap", "subscription_changed", "room_released"):
            log.info("%s on room %s: %s", event_type, self.room_id[:8], frame)
            return
        try:
            self.on_event(self, event_type, frame)
        except Exception:
            log.exception("handler failed for %s", event_type)

    def _beat_forever(self):
        url = "%s/agents/%s/connection/beat" % (self.agent.api, self.agent.id)
        while not self.agent._stop.is_set():
            if self.ready.is_set():
                try:
                    _request("POST", url, {"connection_id": self.id, "cursor": self.last_sequence or 0},
                             self.agent._headers(), timeout=5)
                except SwitchError as exc:
                    if exc.status in (404, 409):
                        self.ready.clear()  # the stream loop will reopen
                except Exception:
                    pass
            time.sleep(2)
