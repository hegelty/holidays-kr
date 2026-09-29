import io
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse
from xml.sax.saxutils import escape

from fetch_public_data import (
    CollectionError, NoRedirect, collect, fetch_year, main, request_xml, run, service_key,
)


def item(date="20260101", name="1월 1일", holiday="Y", seq="1"):
    return {"locdate": date, "dateName": name, "isHoliday": holiday, "seq": seq}


def response(items=(), page=1, total=None, size=100, code="00"):
    records = "".join(
        "<item>" + "".join(f"<{key}>{escape(value)}</{key}>" for key, value in row.items()) + "</item>"
        for row in items
    )
    return (
        f"<response><header><resultCode>{code}</resultCode></header><body>"
        f"<items>{records}</items><numOfRows>{size}</numOfRows><pageNo>{page}</pageNo>"
        f"<totalCount>{len(items) if total is None else total}</totalCount></body></response>"
    ).encode()


class PublicDataTests(unittest.TestCase):
    def test_encoded_and_decoded_keys(self):
        self.assertEqual(service_key(" a%2Bb%2Fc%3D "), "a+b/c=")
        self.assertEqual(service_key("a+b/c="), "a+b/c=")
        for key in ("", " ", "a\nb"):
            with self.assertRaises(CollectionError):
                service_key(key)

    def test_https_request_encodes_key_once_and_retries(self):
        urls, delays = [], []

        class Reply(io.BytesIO):
            status = 200

        class Opener:
            def open(self, request, timeout):
                urls.append(request.full_url)
                if len(urls) < 3:
                    raise urllib.error.HTTPError(request.full_url, 503, "secret", {}, None)
                return Reply(response([item()]))

        result = request_xml("getRestDeInfo", 2026, 1, "a+b/c=", Opener(), delays.append)
        self.assertEqual(result, response([item()]))
        self.assertEqual(delays, [1, 2])
        url = urllib.parse.urlparse(urls[-1])
        self.assertEqual(url.scheme, "https")
        self.assertEqual(url.hostname, "apis.data.go.kr")
        self.assertEqual(urllib.parse.parse_qs(url.query)["ServiceKey"], ["a+b/c="])
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.invalid"))

    def test_request_errors_do_not_expose_key(self):
        for status in (401, 429, 503):
            class Opener:
                def open(self, request, timeout):
                    raise urllib.error.HTTPError(request.full_url, status, "private-key", {}, None)
            with self.assertRaises(CollectionError) as caught:
                request_xml("getRestDeInfo", 2026, 1, "private-key", Opener(), lambda _: None)
            self.assertNotIn("private-key", str(caught.exception))
            self.assertNotIn("ServiceKey", str(caught.exception))

    def test_pagination_merges_overlapping_holidays_and_filters_nonholidays(self):
        pages = [
            response([item(), item(name="겹친 공휴일", seq="2")], total=3, size=2),
            response([item(date="20260102", name="평일", holiday="N")], page=2, total=3, size=2),
        ]
        calls = []
        def transport(operation, year, page, key):
            calls.append((operation, year, page))
            return pages[page - 1]
        result = fetch_year("holidays", 2026, "key", transport)
        self.assertEqual(result, {"2026-01-01": ["1월 1일", "겹친 공휴일"]})
        self.assertEqual(calls[-1], ("getRestDeInfo", 2026, 2))

    def test_anniversaries_include_nonholidays_and_decode_xml_entities(self):
        result = fetch_year("anniversaries", 2026, "key", lambda *_: response([
            item(name="기념일 & 행사", holiday="N"),
        ]))
        self.assertEqual(result, {"2026-01-01": ["기념일 & 행사"]})

    def test_rejects_errors_and_incomplete_pages(self):
        for payload in (
            b"<OpenAPI_ServiceResponse>private-key</OpenAPI_ServiceResponse>",
            response(code="30"), b"not XML",
            b'<!DOCTYPE response [<!ENTITY a "secret">]><response>&a;</response>',
            '<!DOCTYPE response [<!ENTITY a "secret">]><response>&a;</response>'.encode("utf-16"),
            response([item()], total=2), response([item()], page=2),
            response([item()], total=50000),
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(CollectionError) as caught:
                    fetch_year("holidays", 2026, "key", lambda *_: payload)
                self.assertNotIn("private-key", str(caught.exception))

    def test_rejects_invalid_dates_names_flags_and_duplicate_records(self):
        for rows in (
            [item(date="20260230")], [item(date="20270101")], [item(name=" ")],
            [item(holiday="maybe")], [item(seq="bad")], [item(), item()],
            [item(), item(seq="2")], [item(holiday="N")],
            [{"locdate": "20260101"}],
        ):
            with self.subTest(rows=rows):
                with self.assertRaises(CollectionError):
                    fetch_year("holidays", 2026, "key", lambda *_: response(rows))

    def test_rejects_changed_totals_and_repeated_pages(self):
        first = response([item()], total=2, size=1)
        for second in (
            response([item(date="20260102")], page=2, total=3, size=1),
            response([item()], page=2, total=2, size=1),
        ):
            with self.assertRaises(CollectionError):
                fetch_year("holidays", 2026, "key", lambda op, y, page, key: first if page == 1 else second)

    def test_new_future_year_can_be_absent_but_existing_year_cannot(self):
        current = {"holidays": {"2026": {}}, "anniversaries": {"2026": {}}}
        queried = []
        def transport(op, year, page, key):
            queried.append((op, year))
            return response([item()]) if year == 2026 else response()
        data = collect(current, "key", 2026, transport)
        self.assertEqual(list(data["holidays"]), ["2026"])
        self.assertEqual(
            queried,
            [(operation, year) for operation in ("getRestDeInfo", "getAnniversaryInfo")
             for year in (2026, 2027, 2028, 2029)],
        )
        current["holidays"]["2027"] = {}
        with self.assertRaises(CollectionError):
            collect(current, "key", 2026, transport)
        with self.assertRaises(CollectionError):
            collect({"holidays": {}, "anniversaries": {}}, "key", 2026, lambda *_: response())

    def test_new_published_year_is_added(self):
        transport = lambda op, year, page, key: response([item(date=f"{year}0101")])
        data = collect({"holidays": {"2026": {}}, "anniversaries": {"2026": {}}}, "key", 2026, transport)
        self.assertEqual(list(data["holidays"]), ["2026", "2027", "2028", "2029"])
        self.assertEqual(list(data["anniversaries"]), ["2026", "2027", "2028", "2029"])

    def test_failed_collection_does_not_write_and_success_has_no_key(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            for path in ("public/basic.json", "public/anniversaries/basic.json"):
                target = repo / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('{"2026":{"2026-01-01":["기존"]}}')
            output = repo / ".data-update"
            with self.assertRaises(CollectionError):
                run(repo, output, "private-key", 2026, lambda *_: response(code="30"))
            self.assertFalse(output.exists())
            run(repo, output, "private-key", 2026,
                lambda op, year, page, key: response([item(date=f"{year}0101")]))
            for path in output.rglob("*.json"):
                self.assertNotIn("private-key", path.read_text())
            self.assertEqual(
                json.loads((output / "source.json").read_text())["years"]["holidays"],
                ["2026", "2027", "2028", "2029"],
            )
            self.assertIn("기존", (repo / "public/basic.json").read_text())

    def test_python_collection_and_node_import_work_together(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            for path in ("public/basic.json", "public/anniversaries/basic.json"):
                target = repo / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('{"2026":{"2026-01-01":["기존"]}}', encoding="utf-8")
            output = repo / ".data-update"
            run(repo, output, "private-key", 2026,
                lambda op, year, page, key: response([item(date=f"{year}0101")]))
            module = Path(__file__).resolve().with_name("pages.mjs").as_uri()
            command = [
                "node", "--input-type=module", "-e",
                f"import {{ importSnapshot }} from {json.dumps(module)};"
                "console.log(await importSnapshot(process.argv[1], process.argv[2]));",
                str(output), str(repo),
            ]
            first = subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertEqual(first.stdout.strip(), "true")
            second = subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertEqual(second.stdout.strip(), "false")
            self.assertTrue((repo / "src/holidays/2029.ts").is_file())
            source = json.loads((repo / "public/source.json").read_text(encoding="utf-8"))
            self.assertEqual(source["provider"], "한국천문연구원")
            self.assertNotIn("private-key", (repo / "public/source.json").read_text())

    def test_cli_hides_unexpected_error_details(self):
        with patch("sys.argv", ["fetch_public_data.py"]), patch("sys.stderr", new_callable=io.StringIO) as err:
            with patch("fetch_public_data.run", side_effect=RuntimeError("private-key")):
                self.assertEqual(main(), 1)
            self.assertNotIn("private-key", err.getvalue())


if __name__ == "__main__":
    unittest.main()
