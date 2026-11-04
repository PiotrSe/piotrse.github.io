#!/usr/bin/env python3
"""
Universal multilingual SEO helper.

Modes:
    --init-config  Create sample configuration.
    --dry-run      Audit and show planned changes.
    --apply        Write configured files with backup.

Supports:
    url_mode = "path"  -> /pl/
    url_mode = "query" -> ?lang=pl
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET

from pathlib import Path
from urllib.parse import urlencode, urlparse
from xml.dom import minidom


CONFIG_NAME = "seo-config.json"

DEFAULT_CONFIG = {
    "site_url": "https://example.com/",
    "site_name": "My Website",
    "url_mode": "path",
    "language_query_param": "lang",
    "languages": [
        {"code": "en", "path": ""},
        {"code": "pl", "path": "pl/"}
    ],
    "pages": [
        {
            "path": "index.html",
            "url_path": "",
            "languages": ["en", "pl"],
            "change_frequency": "weekly",
            "priority": "1.0"
        }
    ],
    "generate_sitemap": True,
    "generate_robots": True,
    "update_html_head": False,
    "html_files": [],
    "robots_extra": [],
    "change_frequency": "weekly",
    "priority": "1.0"
}


def die(message: str, code: int = 1):
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def normalize_base_url(value: str) -> str:
    parsed = urlparse(value.strip())

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        die("site_url must be an absolute HTTP(S) URL.")

    if parsed.query or parsed.fragment:
        die("site_url must not contain query parameters or fragment.")

    return value.strip().rstrip("/") + "/"


def load_config(root: Path) -> dict:
    config_path = root / CONFIG_NAME

    if not config_path.exists():
        die(f"Missing {CONFIG_NAME}. Run --init-config first.")

    try:
        config = json.loads(
            config_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        die(f"Cannot read configuration: {exc}")

    return validate_config(config)


def validate_config(config: dict) -> dict:

    if not isinstance(config, dict):
        die("Config must be a JSON object.")

    config["site_url"] = normalize_base_url(
        str(config.get("site_url", ""))
    )

    languages = config.get("languages")
    pages = config.get("pages")

    if not isinstance(languages, list) or not languages:
        die("languages must be a non-empty array.")

    if not isinstance(pages, list) or not pages:
        die("pages must be a non-empty array.")

    url_mode = str(config.get("url_mode", "path"))

    if url_mode not in ("path", "query"):
        die("url_mode must be 'path' or 'query'.")

    config["url_mode"] = url_mode

    query_param = str(
        config.get("language_query_param", "lang")
    )

    if url_mode == "query":
        if not re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_.~-]*",
            query_param
        ):
            die("Invalid language_query_param.")

    seen_codes = set()
    seen_paths = set()
    seen_values = set()

    for item in languages:

        if not isinstance(item, dict) or not item.get("code"):
            die("Each language needs a code.")

        code = str(item["code"])
        path = str(item.get("path", ""))

        if code in seen_codes:
            die("Language codes must be unique.")

        if path.startswith("/") or ".." in Path(path).parts or "\\" in path:
            die(f"Unsafe language path: {path!r}")

        if path and not path.endswith("/"):
            die(f"Language path should end in '/': {path!r}")

        if url_mode == "path":

            if path in seen_paths:
                die(
                    "Language paths must be unique "
                    "when url_mode is 'path'."
                )

            seen_paths.add(path)

        else:

            value = str(item.get("query_value", code))

            if value in seen_values:
                die(
                    "Language query_value values must be unique. "
                    "Use an empty value for the default language."
                )

            seen_values.add(value)

        seen_codes.add(code)

    if url_mode == "query" and config.get("update_html_head", False):
        die(
            "update_html_head is not supported in query mode. "
            "Manage dynamic canonical and hreflang in JavaScript."
        )

    known_codes = {str(item["code"]) for item in languages}

    for page in pages:

        if not isinstance(page, dict) or not page.get("path"):
            die("Each page needs a local path.")

        local = Path(str(page["path"]))

        if local.is_absolute() or ".." in local.parts:
            die(f"Unsafe page path: {local}")

        url_path = str(page.get("url_path", ""))

        if url_path.startswith("/") or ".." in Path(url_path).parts:
            die(f"Unsafe url_path: {url_path!r}")

        # Jeśli languages nie podano, strona używa wszystkich języków.
        page_languages = page.get(
            "languages",
            [x["code"] for x in languages]
        )

        if not isinstance(page_languages, list) or not page_languages:
            die(
                f"Page {page['path']} must have a non-empty languages array."
            )

        unknown = set(str(code) for code in page_languages) - known_codes

        if unknown:
            die(
                f"Page {page['path']} references unknown languages: "
                + ", ".join(sorted(unknown))
            )

        if len(set(page_languages)) != len(page_languages):
            die(f"Page {page['path']} contains duplicate language codes.")

        page["languages"] = [str(code) for code in page_languages]

        frequency = str(
            page.get(
                "change_frequency",
                config.get("change_frequency", "weekly")
            )
        )

        allowed_frequencies = {
            "always", "hourly", "daily", "weekly",
            "monthly", "yearly", "never"
        }

        if frequency not in allowed_frequencies:
            die(
                f"Invalid change_frequency for {page['path']}: {frequency}"
            )

        page["change_frequency"] = frequency

        try:
            priority = float(
                page.get("priority", config.get("priority", "1.0"))
            )
        except (TypeError, ValueError):
            die(
                f"Invalid priority for {page['path']}: "
                f"{page.get('priority')!r}"
            )

        if not 0.0 <= priority <= 1.0:
            die(
                f"Priority for {page['path']} must be between 0.0 and 1.0."
            )

        page["priority"] = f"{priority:.1f}"

    if config.get("update_html_head"):

        files = config.get("html_files")

        if not isinstance(files, list) or not files:
            die("update_html_head requires html_files.")

        for filename in files:

            p = Path(str(filename))

            if p.is_absolute() or ".." in p.parts:
                die(f"Unsafe html_files entry: {filename!r}")

    return config


def language_url(
    base: str,
    lang: dict,
    page_path: str,
    config: dict
) -> str:

    url = (
        base
        + str(lang.get("path", ""))
        + page_path.lstrip("/")
    )

    if config.get("url_mode", "path") == "query":

        param = str(
            config.get("language_query_param", "lang")
        )

        value = str(
            lang.get("query_value", lang["code"])
        )

        if value:
            separator = "&" if "?" in url else "?"

            url += separator + urlencode({
                param: value
            })

    return url


def build_sitemap(config: dict) -> str:

    ns = "http://www.sitemaps.org/schemas/sitemap/0.9"
    xns = "http://www.w3.org/1999/xhtml"

    ET.register_namespace("", ns)
    ET.register_namespace("xhtml", xns)

    root = ET.Element(f"{{{ns}}}urlset")

    languages_by_code = {
        str(lang["code"]): lang
        for lang in config["languages"]
    }

    for page in config["pages"]:

        page_url_path = str(page.get("url_path", ""))

        page_languages = [
            languages_by_code[code]
            for code in page["languages"]
        ]

        for lang in page_languages:

            url = ET.SubElement(
                root,
                f"{{{ns}}}url"
            )

            ET.SubElement(
                url,
                f"{{{ns}}}loc"
            ).text = language_url(
                config["site_url"],
                lang,
                page_url_path,
                config
            )

            # hreflang tylko dla stron posiadających wiele wersji językowych.
            if len(page_languages) > 1:

                for alt in page_languages:

                    href = language_url(
                        config["site_url"],
                        alt,
                        page_url_path,
                        config
                    )

                    ET.SubElement(
                        url,
                        f"{{{xns}}}link",
                        {
                            "rel": "alternate",
                            "hreflang": str(alt["code"]),
                            "href": href
                        }
                    )

                default_for_page = next(
                    (
                        x for x in page_languages
                        if x["code"].lower() == "en"
                    ),
                    page_languages[0]
                )

                ET.SubElement(
                    url,
                    f"{{{xns}}}link",
                    {
                        "rel": "alternate",
                        "hreflang": "x-default",
                        "href": language_url(
                            config["site_url"],
                            default_for_page,
                            page_url_path,
                            config
                        )
                    }
                )

            ET.SubElement(
                url,
                f"{{{ns}}}changefreq"
            ).text = page["change_frequency"]

            ET.SubElement(
                url,
                f"{{{ns}}}priority"
            ).text = page["priority"]

    raw = ET.tostring(
        root,
        encoding="utf-8",
        xml_declaration=True
    )

    return minidom.parseString(raw).toprettyxml(
        indent="  ",
        encoding="UTF-8"
    ).decode("utf-8")


def build_robots(config: dict) -> str:

    lines = [
        "User-agent: *",
        "Allow: /"
    ]

    lines.extend(
        str(x) for x in config.get("robots_extra", [])
    )

    if config.get("generate_sitemap", True):

        lines.extend([
            "",
            f"Sitemap: {config['site_url']}sitemap.xml"
        ])

    return "\n".join(lines) + "\n"


def audit(root: Path, config: dict) -> list[str]:

    findings = []

    for page in config["pages"]:

        p = root / str(page["path"])

        if not p.is_file():
            findings.append(
                f"MISSING page file: {page['path']}"
            )
            continue

        html = p.read_text(
            encoding="utf-8",
            errors="replace"
        )

        if "<html" not in html.lower():
            findings.append(
                f"WARNING: {page['path']} does not look like HTML."
            )

        if not re.search(
            r'<link\b(?=[^>]*\brel=["\']canonical["\'])',
            html,
            re.I
        ):
            findings.append(
                f"INFO: no canonical tag detected in {page['path']}."
            )

        if len(page["languages"]) > 1:

            if config.get("url_mode") == "query":
                findings.append(
                    f"INFO: hreflang for {page['path']} must be managed "
                    "dynamically because language versions use query URLs."
                )

            elif "hreflang" not in html.lower():
                findings.append(
                    f"INFO: no hreflang tags detected in {page['path']}."
                )

        if not re.search(
            r'<meta\b(?=[^>]*\bname=["\']description["\'])',
            html,
            re.I
        ):
            findings.append(
                f"INFO: no meta description detected in {page['path']}."
            )

    for name in ("robots.txt", "sitemap.xml"):

        if (root / name).exists():
            findings.append(
                f"EXISTS: {name} (will be backed up before replacement)."
            )
        else:
            findings.append(
                f"NOT FOUND: {name}"
            )

    return findings


def backup_files(root: Path, files: list[Path]) -> Path:

    stamp = dt.datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )

    backup_dir = root / (
        f".multilingual-seo-backup-{stamp}"
    )

    backup_dir.mkdir()

    for path in files:

        if path.exists():

            target = backup_dir / path.relative_to(root)

            target.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            shutil.copy2(path, target)

    return backup_dir


def update_html_head_tags(
    html: str,
    canonical: str,
    alternates: list[tuple[str, str]]
) -> str:

    if not re.search(r"</head\s*>", html, re.I):
        raise ValueError("No </head> found.")

    canonical_tag = (
        f'<link rel="canonical" href="{canonical}">'
    )

    html, count = re.subn(
        r'<link\b(?=[^>]*\brel=["\']canonical["\'])[^>]*>',
        canonical_tag,
        html,
        count=1,
        flags=re.I
    )

    if count == 0:

        html = re.sub(
            r"</head\s*>",
            f"  {canonical_tag}\n</head>",
            html,
            count=1,
            flags=re.I
        )

    html = re.sub(
        r'\s*<link\b(?=[^>]*\brel=["\']alternate["\'])(?=[^>]*\bhreflang=)[^>]*>',
        "",
        html,
        flags=re.I
    )

    tags = [
        f'<link rel="alternate" hreflang="{code}" href="{href}">'
        for code, href in alternates
    ]

    html = re.sub(
        r"</head\s*>",
        "  " + "\n  ".join(tags) + "\n</head>",
        html,
        count=1,
        flags=re.I
    )

    return html


def main():

    parser = argparse.ArgumentParser(
        description="Conservative multilingual SEO helper."
    )

    mode = parser.add_mutually_exclusive_group()

    mode.add_argument(
        "--init-config",
        action="store_true"
    )

    mode.add_argument(
        "--dry-run",
        action="store_true"
    )

    mode.add_argument(
        "--apply",
        action="store_true"
    )

    args = parser.parse_args()

    root = Path.cwd()

    if args.init_config:

        target = root / CONFIG_NAME

        if target.exists():
            die(
                f"{CONFIG_NAME} already exists; refusing to overwrite."
            )

        target.write_text(
            json.dumps(
                DEFAULT_CONFIG,
                indent=2,
                ensure_ascii=False
            ) + "\n",
            encoding="utf-8"
        )

        print(f"Created {CONFIG_NAME}.")
        print("No website files were modified.")
        return

    config = load_config(root)

    print(f"Project directory: {root}")
    print(f"Website URL:       {config['site_url']}")
    print(f"URL mode:          {config['url_mode']}")

    print(
        "Languages:         "
        + ", ".join(x["code"] for x in config["languages"])
    )

    print("\nAudit:")

    for line in audit(root, config):
        print(" - " + line)

    planned = []

    if config.get("generate_sitemap", True):
        planned.append(root / "sitemap.xml")

    if config.get("generate_robots", True):
        planned.append(root / "robots.txt")

    if config.get("update_html_head", False):
        planned.extend(
            root / str(x)
            for x in config["html_files"]
        )

    if not args.apply:

        print("\nDRY RUN: no files were changed.")
        print("Planned writes:")

        for p in planned:
            print(" - " + str(p.relative_to(root)))

        print(
            "\nReview configuration before running --apply."
        )
        return

    if not planned:
        print("\nNothing selected for writing.")
        return

    outputs = {}

    if config.get("generate_sitemap", True):
        outputs[root / "sitemap.xml"] = build_sitemap(config)

    if config.get("generate_robots", True):
        outputs[root / "robots.txt"] = build_robots(config)

    if config.get("update_html_head", False):

        for filename in config["html_files"]:

            path = root / str(filename)

            if not path.is_file():
                die(f"HTML file not found: {filename}")

            html = path.read_text(
                encoding="utf-8"
            )

            mapping = config.get(
                "html_head_mapping", {}
            ).get(str(filename))

            if not mapping:
                die(
                    f"Missing html_head_mapping for {filename}."
                )

            lang_code = mapping.get("language")
            page_path = mapping.get("url_path", "")

            lang = next(
                (
                    x for x in config["languages"]
                    if x["code"] == lang_code
                ),
                None
            )

            if lang is None:
                die(f"Unknown language: {lang_code}")

            canonical = language_url(
                config["site_url"],
                lang,
                page_path,
                config
            )

            alternates = [
                (
                    x["code"],
                    language_url(
                        config["site_url"],
                        x,
                        page_path,
                        config
                    )
                )
                for x in config["languages"]
            ]

            outputs[path] = update_html_head_tags(
                html,
                canonical,
                alternates
            )

    backup_dir = backup_files(
        root,
        list(outputs)
    )

    print(
        f"\nBackup created: {backup_dir.relative_to(root)}"
    )

    for path, content in outputs.items():

        path.write_text(
            content,
            encoding="utf-8"
        )

        print(
            f"Wrote: {path.relative_to(root)}"
        )

    print("\nDone.")
    print("Review git diff before committing.")
    print("No files were published to the internet.")


if __name__ == "__main__":
    main()
