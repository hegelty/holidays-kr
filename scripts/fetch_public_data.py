"""Collect KASI special-day XML directly; never log credentials or raw responses."""

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
ENDPOINT = "https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService"
SOURCE = {
    "provider": "한국천문연구원",
    "service": "SpcdeInfoService",
    "url": "https://www.data.go.kr/data/15012690/openapi.do",
}
OPERATIONS = {"holidays": "getRestDeInfo", "anniversaries": "getAnniversaryInfo"}
MAX_BYTES = 2 * 1024 * 1024
MAX_RECORDS = 2000


class CollectionError(Exception):
    """A diagnostic safe to print: no URL, key, response body or chained error."""


def service_key(raw):
    key = raw.strip()
    # Accept either the portal's Encoding or Decoding key, without double encoding.
    if "%" in key:
        try:
            key = urllib.parse.unquote(key, errors="strict")
        except (UnicodeError, ValueError):
            raise CollectionError("Invalid DATA_GO_KR_SERVICE_KEY encoding") from None
    if not key or re.search(r"\s", key):
        raise CollectionError("Set DATA_GO_KR_SERVICE_KEY as a repository Actions secret")
    return key


class NoRedirect(urllib.request.HTTPRedirectHandler):
    # Never forward a URL containing the key to another origin or to HTTP.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_xml(operation, year, page, key, opener=None, sleep=time.sleep):
    opener = opener or urllib.request.build_opener(NoRedirect())
    query = urllib.parse.urlencode({
        "ServiceKey": key, "solYear": str(year), "pageNo": page, "numOfRows": 100,
    })
    request = urllib.request.Request(
        f"{ENDPOINT}/{operation}?{query}",
        headers={"Accept": "application/xml", "User-Agent": "holidays-kr-public-data/1"},
    )
    for attempt in range(3):
        try:
            with opener.open(request, timeout=30) as response:
                if response.status != 200:
                    raise CollectionError(f"{operation}/{year}: unexpected HTTP status")
                payload = response.read(MAX_BYTES + 1)
            if len(payload) > MAX_BYTES:
                raise CollectionError(f"{operation}/{year}: oversized response")
            return payload
        except urllib.error.HTTPError as error:
            status = error.code
            error.close()
            if status not in (429, 500, 502, 503, 504) or attempt == 2:
                raise CollectionError(f"{operation}/{year}: HTTP {status}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == 2:
                raise CollectionError(f"{operation}/{year}: connection failed after 3 attempts") from None
        sleep(2 ** attempt)
    raise CollectionError("Request failed")


def parse_page(payload, page):
    # ElementTree does not fetch external entities; also reject DTD declarations.
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeError:
        raise CollectionError("Expected UTF-8 XML response") from None
    if "\x00" in text or "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise CollectionError("DTD/entity declarations are not accepted")
    try:
        root = ET.fromstring(text)
    except (ET.ParseError, ValueError):
        raise CollectionError("Invalid XML response") from None
    # Gateway authentication/quota errors may be XML with HTTP 200 and another root.
    if root.tag != "response" or root.findtext("header/resultCode") != "00":
        raise CollectionError("API error: check service approval, key, quota and provider status")
    body = root.find("body")
    if body is None:
        raise CollectionError("Missing response body")
    try:
        total = int(body.findtext("totalCount", ""))
        number = int(body.findtext("pageNo", ""))
        size = int(body.findtext("numOfRows", ""))
    except ValueError:
        raise CollectionError("Invalid pagination metadata") from None
    if number != page or not 0 <= total <= MAX_RECORDS or not 1 <= size <= MAX_RECORDS:
        raise CollectionError("Unexpected pagination metadata")
    items = []
    for item in body.findall("items/item"):
        record = {}
        for field in ("locdate", "dateName", "isHoliday", "seq"):
            values = item.findall(field)
            if len(values) != 1 or values[0].text is None:
                raise CollectionError("Missing or repeated item field")
            record[field] = values[0].text
        items.append(record)
    return total, size, items


def fetch_year(kind, year, key, transport=request_xml):
    operation = OPERATIONS[kind]
    page, expected_total, expected_size = 1, None, None
    records = []
    while True:
        total, size, items = parse_page(transport(operation, year, page, key), page)
        if expected_total is None:
            expected_total, expected_size = total, size
        if (total, size) != (expected_total, expected_size):
            raise CollectionError(f"{operation}/{year}: pagination changed during collection")
        remaining = total - len(records)
        if len(items) != min(size, remaining):
            raise CollectionError(f"{operation}/{year}: incomplete page")
        records.extend(items)
        if len(records) == total:
            break
        page += 1
    preset = {}
    seen = set()
    for item in records:
        date = item["locdate"]
        name = item["dateName"].strip()
        flag = item["isHoliday"]
        sequence = item["seq"]
        if not re.fullmatch(r"\d{8}", date) or not re.fullmatch(r"\d+", sequence):
            raise CollectionError(f"{operation}/{year}: invalid date/sequence")
        try:
            date = dt.date(int(date[:4]), int(date[4:6]), int(date[6:])).isoformat()
        except ValueError:
            raise CollectionError(f"{operation}/{year}: invalid calendar date") from None
        if not date.startswith(f"{year}-") or flag not in ("Y", "N"):
            raise CollectionError(f"{operation}/{year}: wrong year or holiday flag")
        if not name or len(name) > 200 or any(ord(c) < 32 or ord(c) == 127 for c in name):
            raise CollectionError(f"{operation}/{year}: invalid name")
        identity = (date, int(sequence))
        if identity in seen:
            raise CollectionError(f"{operation}/{year}: duplicate record across pages")
        seen.add(identity)
        if kind == "holidays" and flag != "Y":
            continue
        names = preset.setdefault(date, [])
        if name in names:
            raise CollectionError(f"{operation}/{year}: duplicate date/name")
        names.append(name)
    if records and not preset:
        raise CollectionError(f"{operation}/{year}: no usable holiday records")
    return {date: sorted(names) for date, names in sorted(preset.items())}


def collect(current, key, current_year, transport=request_xml):
    datasets = {}
    # Re-fetch every supported year, rather than perpetually copying upstream history.
    for kind in OPERATIONS:
        existing = current[kind]
        years = sorted(set(existing) | {str(year) for year in range(current_year, current_year + 4)})
        datasets[kind] = {}
        for year in years:
            if not re.fullmatch(r"2\d{3}", year):
                raise CollectionError("Invalid local snapshot year")
            preset = fetch_year(kind, int(year), key, transport)
            if not preset:
                # Only an entirely new, unpublished future year may be skipped.
                if year not in existing and int(year) > current_year:
                    continue
                raise CollectionError(f"{kind}/{year}: empty response; keeping published snapshot")
            datasets[kind][year] = preset
    return datasets


def run(repository, output, key, current_year=None, transport=request_xml):
    key = service_key(key)
    current = {
        kind: json.loads((repository / "public" / path).read_text(encoding="utf-8"))
        for kind, path in (
            ("holidays", "basic.json"), ("anniversaries", "anniversaries/basic.json")
        )
    }
    if current_year is None:
        current_year = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).year
    datasets = collect(current, key, current_year, transport)
    # No writes, including staging files, until every required request has succeeded.
    for kind, data in datasets.items():
        directory = output if kind == "holidays" else output / "anniversaries"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "basic.json").write_text(
            json.dumps(data, ensure_ascii=False, indent="\t") + "\n", encoding="utf-8"
        )
    metadata = {**SOURCE, "years": {kind: list(data) for kind, data in datasets.items()}}
    (output / "source.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent="\t") + "\n", encoding="utf-8"
    )
    return datasets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".data-update")
    args = parser.parse_args()
    try:
        datasets = run(ROOT, args.output, os.environ.get("DATA_GO_KR_SERVICE_KEY", ""))
    except CollectionError as error:
        print(f"Collection failed: {error}", file=sys.stderr)
        return 1
    except Exception:
        # Exception repr/tracebacks can contain a request URL and its credential.
        print("Collection failed: unexpected local or response error", file=sys.stderr)
        return 1
    for kind, data in datasets.items():
        print(f"Collected {kind}: {len(data)} years")
    return 0


if __name__ == "__main__":
    sys.exit(main())
