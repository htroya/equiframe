"""Read-only public index observations; a missing listing never reserves a name."""

import argparse
import concurrent.futures
import datetime
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def observe(index: str, name: str) -> dict:
    url = f"https://{index}/pypi/{name}/json"
    result = {
        "index": index,
        "name": name,
        "url": url,
        "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ownership_verified": False,
        "availability_reserved": False,
    }
    try:
        request = Request(
            url, headers={"User-Agent": "EquiFrame-preparation-read-only/1.0"}
        )
        with urlopen(request, timeout=15) as response:
            if response.url != url:
                raise ValueError("Unexpected public index redirect")
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError("Public index response exceeds limit")
            document = json.loads(raw)
            result.update(
                {
                    "status": "VISIBLE",
                    "http_status": response.status,
                    "listed_name": document["info"]["name"],
                    "listed_version": document["info"]["version"],
                }
            )
    except HTTPError as error:
        result.update(
            {
                "status": "NOT_VISIBLE" if error.code == 404 else "UNKNOWN",
                "http_status": error.code,
            }
        )
    except (OSError, URLError, ValueError, KeyError, TypeError) as error:
        result.update({"status": "UNKNOWN", "reason": str(error)})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.exit(2, "A new observation path is required\n")
    pairs = [
        (index, name)
        for index in ("pypi.org", "test.pypi.org")
        for name in ("equiframe", "equiframe-benchmark")
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        observations = list(pool.map(lambda pair: observe(*pair), pairs))
    result = {
        "observations": observations,
        "authenticated": False,
        "limitation": "Public JSON listings only; 404 does not establish availability, account control or reservation.",
    }
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    for item in observations:
        print(item["index"], item["name"], item["status"])
    return 3 if any(item["status"] == "UNKNOWN" for item in observations) else 0


if __name__ == "__main__":
    raise SystemExit(main())
