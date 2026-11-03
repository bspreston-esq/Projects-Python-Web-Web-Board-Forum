#!/usr/bin/env python3
"""A small SQLite-backed forum with topics and replies."""
import argparse
import datetime as dt
import html
import http.server
import os
import sqlite3
import tempfile
import threading
import urllib.parse
import urllib.request

SCHEMA = """
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    author TEXT NOT NULL,
    body TEXT NOT NULL,
    created TEXT NOT NULL
);"""

LAYOUT = """<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:50rem;margin:2rem auto;padding:0 1rem}}
.post{{border-bottom:1px solid #ddd;padding:.8rem 0}} .meta{{color:#777;font-size:.85rem}}
form{{display:grid;gap:.5rem;max-width:32rem;margin-top:1rem}} input,textarea{{font:inherit;padding:.4rem}}</style>
</head><body><h1><a href="/">Web Board</a></h1>{content}</body></html>"""

def connect(path):
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA)
    connection.commit()
    return connection

def make_handler(db_path: str):
    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, body: str, status=200):
            payload = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers(); self.wfile.write(payload)

        def do_GET(self):
            connection = connect(db_path)
            try:
                if self.path == "/":
                    rows = connection.execute(
                        "SELECT t.id,t.title,t.author,t.created,COUNT(p.id) FROM topics t "
                        "LEFT JOIN posts p ON p.topic_id=t.id GROUP BY t.id ORDER BY t.id DESC").fetchall()
                    items = "".join(
                        f'<li><a href="/topic/{tid}">{html.escape(title)}</a> by {html.escape(author)} '
                        f'<span class="meta">{created} · {count} replies</span></li>'
                        for tid, title, author, created, count in rows)
                    form = ('<h2>New topic</h2><form method="post" action="/new">'
                            '<input name="title" placeholder="Title" required>'
                            '<input name="author" placeholder="Your name" required>'
                            '<button>Post topic</button></form>')
                    self._send(LAYOUT.format(title="Web Board", content=f"<ul>{items or '<li>No topics yet.</li>'}</ul>{form}"))
                elif self.path.startswith("/topic/"):
                    topic_id = int(self.path.split("/")[2])
                    topic = connection.execute("SELECT title,author,created FROM topics WHERE id=?", (topic_id,)).fetchone()
                    if not topic:
                        self._send(LAYOUT.format(title="Not found", content="<h1>404</h1>"), 404); return
                    posts = connection.execute("SELECT author,body,created FROM posts WHERE topic_id=? ORDER BY id", (topic_id,)).fetchall()
                    rendered = "".join(f'<div class="post"><div class="meta">{html.escape(author)} · {created}</div>'
                                       f'<p>{html.escape(body)}</p></div>' for author, body, created in posts)
                    form = (f'<form method="post" action="/topic/{topic_id}/reply">'
                            '<input name="author" placeholder="Your name" required>'
                            '<textarea name="body" placeholder="Reply" required></textarea>'
                            '<button>Reply</button></form>')
                    content = (f"<h2>{html.escape(topic[0])}</h2><div class='meta'>by {html.escape(topic[1])} · {topic[2]}</div>"
                               f"{rendered or '<p>No replies yet.</p>'}{form}")
                    self._send(LAYOUT.format(title=topic[0], content=content))
                else:
                    self._send(LAYOUT.format(title="Not found", content="<h1>404</h1>"), 404)
            finally:
                connection.close()

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            fields = urllib.parse.parse_qs(self.rfile.read(length).decode())
            connection = connect(db_path)
            try:
                if self.path == "/new":
                    title = fields.get("title", [""])[0].strip()
                    author = fields.get("author", [""])[0].strip() or "anonymous"
                    if not title:
                        self._send(LAYOUT.format(title="Bad request", content="<h1>title required</h1>"), 400); return
                    cursor = connection.execute("INSERT INTO topics (title,author,created) VALUES (?,?,?)",
                                                (title, author, dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")))
                    connection.commit()
                    self.send_response(303); self.send_header("Location", f"/topic/{cursor.lastrowid}"); self.end_headers()
                elif self.path.startswith("/topic/") and self.path.endswith("/reply"):
                    topic_id = int(self.path.split("/")[2])
                    author = fields.get("author", [""])[0].strip() or "anonymous"
                    body = fields.get("body", [""])[0].strip()
                    if not body:
                        self._send(LAYOUT.format(title="Bad request", content="<h1>reply required</h1>"), 400); return
                    connection.execute("INSERT INTO posts (topic_id,author,body,created) VALUES (?,?,?,?)",
                                       (topic_id, author, body, dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")))
                    connection.commit()
                    self.send_response(303); self.send_header("Location", f"/topic/{topic_id}"); self.end_headers()
                else:
                    self._send(LAYOUT.format(title="Not found", content="<h1>404</h1>"), 404)
            finally:
                connection.close()

        def log_message(self, *args):
            pass

    return Handler

def demo() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "forum.db")
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), make_handler(db_path))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            def post(path, fields):
                data = urllib.parse.urlencode(fields).encode()
                return urllib.request.urlopen(urllib.request.Request(base + path, data=data))
            post("/new", {"title": "Welcome to the board", "author": "Ada"})
            post("/topic/1/reply", {"author": "Grace", "body": "Glad to be here."})
            with urllib.request.urlopen(base + "/topic/1") as response:
                body = response.read().decode()
            print("topic title present:", "Welcome to the board" in body)
            print("reply present:", "Glad to be here." in body)
            with urllib.request.urlopen(base + "/") as response:
                listing = response.read().decode()
            print("listing shows 1 reply:", "1 replies" in listing)
        finally:
            server.shutdown(); server.server_close()

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument("--db", default="forum.db")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    if args.demo:
        demo(); return
    server = http.server.ThreadingHTTPServer((args.host, args.port), make_handler(args.db))
    print(f"forum on http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
