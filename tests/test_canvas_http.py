#!/usr/bin/env python3
"""Integration tests for canvas.py's HTTP layer, against a local mock server.

`run_tests.py` covers the pure grading logic. This covers the other half: the
transport that every script in the skill funnels through -- pagination, rate
limit backoff, retry-on-5xx, error mapping, auth headers, and `:course`
substitution. Those behaviors are what make the helper worth using instead of
curl, and none of them were exercised by anything but real Canvas traffic.

A `http.server` instance on an ephemeral localhost port plays Canvas and serves
scripted responses. No network, no credentials, no Canvas account:

    python3 tests/test_canvas_http.py

`time.sleep` is patched out for the whole module, so the retry/backoff paths
run instantly rather than actually waiting out exponential backoff.
"""

import contextlib
import importlib.util
import io
import json
import os
import sys
import threading
import unittest
from argparse import Namespace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")

spec = importlib.util.spec_from_file_location("canvas", os.path.join(SCRIPTS, "canvas.py"))
canvas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(canvas)

# Backoff is real wall-clock time in production; here it just slows the suite.
canvas.time.sleep = lambda _s: None


# --------------------------------------------------------------------------- #
# mock Canvas
# --------------------------------------------------------------------------- #

class MockCanvas:
    """A scripted stand-in for Canvas.

    `routes` maps a path (ignoring query string) to a list of responses to
    hand out in order; the last one repeats once exhausted. Each response is
    (status, body_obj_or_str, extra_headers).
    """

    def __init__(self):
        self.routes = {}
        self.requests = []       # (method, path_with_query, headers, body)
        self._server = None
        self._thread = None

    def route(self, path, responses):
        self.routes[path] = list(responses)

    def reset(self):
        self.routes.clear()
        self.requests.clear()

    @property
    def base(self):
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def _next(self, path):
        queue = self.routes.get(path)
        if not queue:
            return 404, {"errors": [{"message": "no route"}]}, {}
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def start(self):
        mock = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_a):
                pass  # keep test output clean

            def _handle(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                mock.requests.append(
                    (self.command, self.path, dict(self.headers), body))
                path = self.path.split("?")[0]
                status, payload, extra = mock._next(path)
                if isinstance(payload, (dict, list)):
                    raw = json.dumps(payload).encode()
                else:
                    raw = str(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(raw)

            do_GET = do_POST = do_PUT = do_DELETE = _handle

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        # Small poll interval: shutdown() waits for serve_forever to notice, and
        # the 0.5s default dominated the suite's runtime.
        self._thread = threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.01},
            daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


# One server for the whole module: starting and shutting one down per test was
# ~0.5s of pure overhead each, which is how a fast suite turns slow enough that
# people stop running it.
_MOCK = None


def setUpModule():
    global _MOCK
    _MOCK = MockCanvas().start()


def tearDownModule():
    _MOCK.stop()


class MockServerTest(unittest.TestCase):
    def setUp(self):
        self.mock = _MOCK
        self.mock.reset()
        self.config = {"base": self.mock.base, "token": "test-token", "course": "999"}

    def get(self, path, **kwargs):
        """Run cmd_get and return the parsed JSON it printed."""
        args = Namespace(path=path, param=kwargs.get("param", []),
                         all=kwargs.get("all", False), page_size=kwargs.get("page_size", 100),
                         dry_run=kwargs.get("dry_run", False))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            canvas.cmd_get(args, self.config)
        return json.loads(buf.getvalue())


# --------------------------------------------------------------------------- #
# pagination -- the single most load-bearing behavior in the helper
# --------------------------------------------------------------------------- #

class TestPagination(MockServerTest):
    def test_all_follows_link_next_to_exhaustion(self):
        base = self.mock.base
        self.mock.route("/api/v1/courses/999/users", [
            (200, [{"id": 1}, {"id": 2}],
             {"Link": f'<{base}/api/v1/page2>; rel="next"'}),
        ])
        self.mock.route("/api/v1/page2", [
            (200, [{"id": 3}], {"Link": f'<{base}/api/v1/page3>; rel="next"'}),
        ])
        self.mock.route("/api/v1/page3", [(200, [{"id": 4}], {})])

        rows = self.get("/api/v1/courses/:course/users", all=True)
        self.assertEqual([r["id"] for r in rows], [1, 2, 3, 4])

    def test_without_all_only_first_page_is_read(self):
        base = self.mock.base
        self.mock.route("/api/v1/courses/999/users", [
            (200, [{"id": 1}], {"Link": f'<{base}/api/v1/page2>; rel="next"'}),
        ])
        self.mock.route("/api/v1/page2", [(200, [{"id": 2}], {})])

        rows = self.get("/api/v1/courses/:course/users")
        self.assertEqual([r["id"] for r in rows], [1])

    def test_all_requests_a_large_page_size(self):
        self.mock.route("/api/v1/courses/999/assignments", [(200, [], {})])
        self.get("/api/v1/courses/:course/assignments", all=True)
        _, path, _, _ = self.mock.requests[0]
        self.assertIn("per_page=100", path)

    def test_explicit_per_page_is_not_overridden(self):
        self.mock.route("/api/v1/courses/999/assignments", [(200, [], {})])
        self.get("/api/v1/courses/:course/assignments", all=True,
                 param=["per_page=10"])
        _, path, _, _ = self.mock.requests[0]
        self.assertIn("per_page=10", path)
        self.assertNotIn("per_page=100", path)

    def test_single_object_never_paginates(self):
        """A dict response must not be treated as a page of a list."""
        base = self.mock.base
        self.mock.route("/api/v1/courses/999", [
            (200, {"id": 999, "name": "A Course"},
             {"Link": f'<{base}/api/v1/should-not-be-fetched>; rel="next"'}),
        ])
        obj = self.get("/api/v1/courses/:course", all=True)
        self.assertEqual(obj["name"], "A Course")
        self.assertEqual(len(self.mock.requests), 1)

    def test_link_header_without_next_stops(self):
        base = self.mock.base
        self.mock.route("/api/v1/courses/999/users", [
            (200, [{"id": 1}],
             {"Link": f'<{base}/api/v1/first>; rel="first", <{base}/api/v1/last>; rel="last"'}),
        ])
        rows = self.get("/api/v1/courses/:course/users", all=True)
        self.assertEqual(len(rows), 1)


class TestLinkHeaderParsing(unittest.TestCase):
    def test_multiple_rels(self):
        header = ('<https://x/api/v1/a?page=2>; rel="next", '
                  '<https://x/api/v1/a?page=1>; rel="current", '
                  '<https://x/api/v1/a?page=9>; rel="last"')
        links = canvas.parse_link_header(header)
        self.assertEqual(links["next"], "https://x/api/v1/a?page=2")
        self.assertEqual(links["last"], "https://x/api/v1/a?page=9")

    def test_empty_and_none(self):
        self.assertEqual(canvas.parse_link_header(""), {})
        self.assertEqual(canvas.parse_link_header(None), {})

    def test_garbage_is_ignored_not_fatal(self):
        self.assertEqual(canvas.parse_link_header("not a link header"), {})


# --------------------------------------------------------------------------- #
# retries and rate limiting
# --------------------------------------------------------------------------- #

class TestRetries(MockServerTest):
    def test_503_is_retried_then_succeeds(self):
        self.mock.route("/api/v1/flaky", [
            (503, {"errors": "unavailable"}, {}),
            (503, {"errors": "unavailable"}, {}),
            (200, [{"id": 7}], {}),
        ])
        rows = self.get("/api/v1/flaky", all=False)
        self.assertEqual(rows, [{"id": 7}])
        self.assertEqual(len(self.mock.requests), 3)

    def test_502_is_retried(self):
        self.mock.route("/api/v1/flaky", [
            (502, "bad gateway", {}),
            (200, [{"id": 1}], {}),
        ])
        self.assertEqual(self.get("/api/v1/flaky"), [{"id": 1}])

    def test_403_rate_limit_is_retried(self):
        """Canvas signals throttling as 403 with a Rate Limit body, not just 429."""
        self.mock.route("/api/v1/throttled", [
            (403, "403 Forbidden (Rate Limit Exceeded)", {}),
            (200, [{"id": 1}], {}),
        ])
        self.assertEqual(self.get("/api/v1/throttled"), [{"id": 1}])
        self.assertEqual(len(self.mock.requests), 2)

    def test_429_rate_limit_is_retried(self):
        self.mock.route("/api/v1/throttled", [
            (429, "Rate Limit Exceeded", {}),
            (200, [{"id": 1}], {}),
        ])
        self.assertEqual(self.get("/api/v1/throttled"), [{"id": 1}])

    def test_plain_403_is_not_retried(self):
        """A permission 403 is terminal -- retrying it just wastes time."""
        self.mock.route("/api/v1/forbidden", [
            (403, {"errors": [{"message": "user not authorized"}]}, {}),
        ])
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stderr(io.StringIO()):
                self.get("/api/v1/forbidden")
        self.assertEqual(cm.exception.code, 2)
        self.assertEqual(len(self.mock.requests), 1)

    def test_low_rate_limit_remaining_triggers_a_pause(self):
        calls = []
        real_sleep = canvas.time.sleep
        canvas.time.sleep = lambda s: calls.append(s)
        try:
            self.mock.route("/api/v1/nearly-out", [
                (200, [{"id": 1}], {"X-Rate-Limit-Remaining": "3"}),
            ])
            self.get("/api/v1/nearly-out")
        finally:
            canvas.time.sleep = real_sleep
        self.assertTrue(calls, "expected a backoff pause when the bucket runs low")

    def test_healthy_rate_limit_does_not_pause(self):
        calls = []
        real_sleep = canvas.time.sleep
        canvas.time.sleep = lambda s: calls.append(s)
        try:
            self.mock.route("/api/v1/fine", [
                (200, [{"id": 1}], {"X-Rate-Limit-Remaining": "500"}),
            ])
            self.get("/api/v1/fine")
        finally:
            canvas.time.sleep = real_sleep
        self.assertEqual(calls, [])


# --------------------------------------------------------------------------- #
# errors, auth, paths
# --------------------------------------------------------------------------- #

class TestErrorMapping(MockServerTest):
    def _expect_exit(self, path, code):
        err = io.StringIO()
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stderr(err):
                self.get(path)
        self.assertEqual(cm.exception.code, code)
        return err.getvalue()

    def test_404_exits_2_with_json_on_stderr(self):
        self.mock.route("/api/v1/missing", [
            (404, {"errors": [{"message": "The specified resource does not exist."}]}, {}),
        ])
        payload = json.loads(self._expect_exit("/api/v1/missing", 2))
        self.assertIn("HTTP 404", payload["error"])

    def test_401_exits_2(self):
        self.mock.route("/api/v1/unauthorized", [
            (401, {"errors": [{"message": "Invalid access token."}]}, {}),
        ])
        payload = json.loads(self._expect_exit("/api/v1/unauthorized", 2))
        self.assertIn("HTTP 401", payload["error"])

    def test_non_json_error_body_is_still_reported(self):
        self.mock.route("/api/v1/htmlerror", [(500, "<html>Server Error</html>", {})])
        payload = json.loads(self._expect_exit("/api/v1/htmlerror", 2))
        self.assertIn("Server Error", str(payload["detail"]))


class TestAuthAndPaths(MockServerTest):
    def test_bearer_token_is_sent(self):
        self.mock.route("/api/v1/users/self", [(200, {"id": 1}, {})])
        self.get("/api/v1/users/self")
        _, _, headers, _ = self.mock.requests[0]
        self.assertEqual(headers["Authorization"], "Bearer test-token")

    def test_course_substitution_in_path(self):
        self.mock.route("/api/v1/courses/999/assignments", [(200, [], {})])
        self.get("/api/v1/courses/:course/assignments")
        _, path, _, _ = self.mock.requests[0]
        self.assertTrue(path.startswith("/api/v1/courses/999/assignments"))

    def test_course_substitution_without_course_id_is_fatal(self):
        config = dict(self.config, course="")
        args = Namespace(path="/api/v1/courses/:course/users", param=[],
                         all=False, page_size=100, dry_run=False)
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                canvas.cmd_get(args, config)

    def test_dry_run_sends_nothing(self):
        self.mock.route("/api/v1/courses/999/users", [(200, [], {})])
        out = self.get("/api/v1/courses/:course/users", dry_run=True)
        self.assertTrue(out["dry_run"])
        self.assertEqual(self.mock.requests, [])

    def test_repeated_array_params_are_preserved(self):
        self.mock.route("/api/v1/courses/999/users", [(200, [], {})])
        self.get("/api/v1/courses/:course/users",
                 param=["enrollment_type[]=student", "enrollment_type[]=ta"])
        _, path, _, _ = self.mock.requests[0]
        self.assertIn("enrollment_type%5B%5D=student", path)
        self.assertIn("enrollment_type%5B%5D=ta", path)


class TestFormEncoding(unittest.TestCase):
    """--form flattening is what makes the awkward endpoints work."""

    def test_nested_dict(self):
        pairs = canvas.flatten_form({"assignment": {"name": "HW7", "points_possible": 50}})
        self.assertIn(("assignment[name]", "HW7"), pairs)
        self.assertIn(("assignment[points_possible]", "50"), pairs)

    def test_list_becomes_bracket_pairs(self):
        pairs = canvas.flatten_form({"assignment": {"submission_types": ["online_upload"]}})
        self.assertIn(("assignment[submission_types][]", "online_upload"), pairs)

    def test_booleans_are_lowercase_strings(self):
        pairs = canvas.flatten_form({"assignment": {"published": True, "muted": False}})
        self.assertIn(("assignment[published]", "true"), pairs)
        self.assertIn(("assignment[muted]", "false"), pairs)

    def test_none_is_dropped(self):
        pairs = canvas.flatten_form({"assignment": {"due_at": None, "name": "x"}})
        self.assertEqual(pairs, [("assignment[name]", "x")])


if __name__ == "__main__":
    unittest.main(verbosity=2)
