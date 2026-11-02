#!/usr/bin/env python3.14
from __future__ import annotations

import argparse
import html
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from PIL import Image, ImageChops, ImageDraw, ImageFont


SECTION_TITLE = "板块资金扩散淘汰赛"
DEFAULT_OUTPUT_ROOT = Path("output/wechat-drafts")
WECHAT_API_BASE = "https://api.weixin.qq.com"
SCREENSHOT_WIDTH = 1400
SCREENSHOT_HEIGHT = 3200
CHROMIUM_TIMEOUT_SECONDS = 45


@dataclass(frozen=True)
class ReportContext:
    report_path: Path
    trade_date: str
    final_target: str
    final_position: str


@dataclass(frozen=True)
class HtmlCapture:
    html_path: Path
    capture_html: str


@dataclass(frozen=True)
class SectionCaptureSpec:
    key: str
    title: str
    filename_stem: str
    required_marker: str
    marker_label: str
    frame_width: int = 1220
    screenshot_width: int = SCREENSHOT_WIDTH


ACCOUNT_DAY_ORDER_SECTION = SectionCaptureSpec(
    key="account_day_order",
    title="账户日序表",
    filename_stem="account-day-order",
    required_marker="position-timeline-shell",
    marker_label="账户日序图",
    frame_width=1900,
    screenshot_width=2100,
)
SECTOR_TOURNAMENT_SECTION = SectionCaptureSpec(
    key="sector_fund_spread_tournament",
    title=SECTION_TITLE,
    filename_stem="sector-fund-spread-tournament",
    required_marker="reader-table",
    marker_label="日报表格区块",
)
CAPTURE_SECTIONS = (ACCOUNT_DAY_ORDER_SECTION, SECTOR_TOURNAMENT_SECTION)


def find_chromium() -> str:
    candidates = [
        os.environ.get("CHROMIUM_BIN", ""),
        "chromium",
        "google-chrome",
        "google-chrome-stable",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        resolved = shutil.which(candidate) if "/" not in candidate else candidate
        if resolved and Path(resolved).exists():
            return resolved
    raise RuntimeError("未找到 Chromium/Chrome，无法截图 HTML 区块")


def extract_trade_date(text: str, report_path: Path) -> str:
    filename_match = re.search(r"(\d{4}-\d{2}-\d{2})", report_path.name)
    if filename_match:
        return filename_match.group(1)
    heading_match = re.search(r"^#\s*(\d{4}-\d{2}-\d{2})", text, re.MULTILINE)
    if heading_match:
        return heading_match.group(1)
    raise ValueError(f"无法从文件名或标题识别报告日期：{report_path}")


def clean_report_value(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def markdown_table_field(text: str, labels: list[str]) -> str:
    for label in labels:
        match = re.search(rf"^\|\s*{re.escape(label)}\s*\|\s*([^|\n]+?)\s*\|", text, re.MULTILINE)
        if match:
            return clean_report_value(match.group(1))
    return ""


def html_table_field(text: str, labels: list[str]) -> str:
    soup = BeautifulSoup(text, "html.parser")
    for row in soup.find_all("tr"):
        cells = [clean_report_value(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
        if len(cells) >= 2 and cells[0] in labels:
            return cells[1]
    return ""


def report_field(text: str, report_path: Path, labels: list[str]) -> str:
    if report_path.suffix.lower() == ".html":
        value = html_table_field(text, labels)
        if value:
            return value
    return markdown_table_field(text, labels)


def is_empty_target(value: str) -> bool:
    normalized = clean_report_value(value)
    return not normalized or normalized in {"-", "无", "暂无"} or "无明日执行对象" in normalized


def display_target(report: ReportContext) -> str:
    return "待确认" if is_empty_target(report.final_target) else report.final_target


def report_context_from_input(report_path: Path) -> ReportContext:
    path = report_path.expanduser().resolve()
    text = path.read_text(encoding="utf-8")
    return ReportContext(
        report_path=path,
        trade_date=extract_trade_date(text, path),
        final_target=report_field(text, path, ["明日执行对象", "最终对象"]),
        final_position=report_field(text, path, ["明日仓位", "仓位姿态"]),
    )


def resolve_html_report(report_path: Path, trade_date: str, explicit_html: str = "") -> Path | None:
    if "完整版" not in report_path.stem or report_path.suffix.lower() not in {".md", ".html"}:
        raise ValueError("公众号草稿只接受显式选择的历史完整版，不读取当前板块日报")
    if explicit_html:
        path = Path(explicit_html).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"指定的 HTML 不存在：{path}")
    else:
        path = report_path.expanduser().resolve()
        if path.suffix.lower() != ".html":
            path = path.with_suffix(".html")
        if not path.is_file():
            return None
    if path.suffix.lower() != ".html" or "板块日报" in path.stem:
        raise ValueError(f"截图来源必须为历史完整版 HTML：{path}")
    html_date = extract_trade_date(path.read_text(encoding="utf-8"), path)
    if html_date != trade_date:
        raise ValueError(f"文案日期{trade_date}与截图日期{html_date}不一致：{path}")
    return path


def style_text_from_soup(soup: BeautifulSoup) -> str:
    styles: list[str] = []
    for style in soup.find_all("style"):
        styles.append(style.get_text("\n"))
    return "\n\n".join(styles)


def find_section_heading(soup: BeautifulSoup, title: str) -> Tag:
    heading = soup.find(id=title)
    if isinstance(heading, Tag):
        return heading
    for tag in soup.find_all(["h1", "h2", "h3"]):
        if tag.get_text(strip=True) == title:
            return tag
    raise ValueError(f"HTML 中未找到章节：{title}")


def find_sector_heading(soup: BeautifulSoup) -> Tag:
    return find_section_heading(soup, SECTION_TITLE)


def collect_section_nodes(heading: Tag) -> list[str]:
    nodes = [str(heading)]
    for sibling in heading.next_siblings:
        if isinstance(sibling, NavigableString):
            if sibling.strip():
                nodes.append(str(sibling))
            continue
        if not isinstance(sibling, Tag):
            continue
        if sibling.name in {"h1", "h2"}:
            break
        nodes.append(str(sibling))
    return nodes


def collect_sector_nodes(heading: Tag) -> list[str]:
    return collect_section_nodes(heading)


def extract_section_html_capture(html_path: Path, spec: SectionCaptureSpec) -> HtmlCapture:
    path = html_path.expanduser().resolve()
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    try:
        heading = find_section_heading(soup, spec.title)
    except ValueError as exc:
        raise ValueError(f"{exc}；文件：{path}") from None
    section_html = "\n".join(collect_section_nodes(heading))
    if spec.required_marker not in section_html:
        raise ValueError(f"HTML 章节存在，但未找到{spec.marker_label}；文件：{path}")
    styles = style_text_from_soup(soup)
    capture_html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(spec.title)}</title>
  <style>{styles}</style>
  <style>
    html, body {{
      margin: 0;
      padding: 0;
      width: max-content;
      min-width: 0;
      background: #ffffff !important;
    }}
    body::before,
    body::after,
    .outline-sidebar,
    .window-controls {{
      display: none !important;
    }}
    .capture-frame {{
      display: inline-block;
      width: {spec.frame_width}px;
      padding: 28px;
      background: var(--reader-bg, #fff9ef);
    }}
    .capture-frame,
    .capture-frame * {{
      animation: none !important;
      opacity: 1 !important;
      transform: none !important;
      transition: none !important;
    }}
    .markdown-body {{
      width: 100% !important;
      max-width: none !important;
      margin: 0 !important;
      padding: 0 !important;
    }}
    .markdown-body h2 {{
      margin-top: 0 !important;
    }}
    .reader-table {{
      width: 100% !important;
      max-width: none !important;
      overflow: visible !important;
    }}
    .reader-table table {{
      width: 100% !important;
    }}
    .position-timeline-shell {{
      width: 100% !important;
      max-width: none !important;
    }}
    .position-timeline-scroll {{
      overflow: visible !important;
    }}
    .position-timeline-table {{
      width: 100% !important;
    }}
  </style>
</head>
<body>
  <div class="capture-frame">
    <article class="markdown-body">
      {section_html}
    </article>
  </div>
</body>
</html>
"""
    return HtmlCapture(html_path=path, capture_html=capture_html)


def extract_sector_html_capture(html_path: Path) -> HtmlCapture:
    return extract_section_html_capture(html_path, SECTOR_TOURNAMENT_SECTION)


def crop_non_white(source_path: Path, output_path: Path, *, padding: int = 0) -> Path:
    image = Image.open(source_path).convert("RGB")
    white = Image.new("RGB", image.size, "#ffffff")
    diff = ImageChops.difference(image, white)
    bbox = diff.getbbox()
    if bbox is None:
        image.save(output_path, format="PNG", optimize=True)
        return output_path
    left = max(0, bbox[0] - padding)
    top = max(0, bbox[1] - padding)
    right = min(image.width, bbox[2] + padding)
    bottom = min(image.height, bbox[3] + padding)
    image.crop((left, top, right, bottom)).save(output_path, format="PNG", optimize=True)
    return output_path


def ensure_not_truncated(source_path: Path, source_html: Path) -> None:
    image = Image.open(source_path).convert("RGB")
    white = Image.new("RGB", image.size, "#ffffff")
    diff = ImageChops.difference(image, white)
    bbox = diff.getbbox()
    if bbox and (bbox[2] >= image.width - 2 or bbox[3] >= image.height - 2):
        raise RuntimeError(f"HTML 区块截图可能被截断，请缩短区块或提高 SCREENSHOT_HEIGHT；文件：{source_html}")


def render_html_section_png(
    html_path: Path,
    output_path: Path,
    capture_html_path: Path,
    spec: SectionCaptureSpec,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    capture = extract_section_html_capture(html_path, spec)
    write_text(capture_html_path, capture.capture_html)
    chromium = find_chromium()
    with tempfile.TemporaryDirectory(prefix="daily-report-wechat-draft-") as tmp_dir:
        raw_png = Path(tmp_dir) / "raw.png"
        command = [
            chromium,
            "--headless=new",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--disable-background-networking",
            "--disable-extensions",
            "--hide-scrollbars",
            "--no-first-run",
            "--no-default-browser-check",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=1000",
            f"--screenshot={raw_png}",
            f"--window-size={spec.screenshot_width},{SCREENSHOT_HEIGHT}",
            capture_html_path.resolve().as_uri(),
        ]
        detail = ""
        for _attempt in range(2):
            if raw_png.exists():
                raw_png.unlink()
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=CHROMIUM_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                detail = f"timeout={CHROMIUM_TIMEOUT_SECONDS}s"
                continue
            if completed.returncode == 0 and raw_png.exists():
                break
            detail = (completed.stderr or completed.stdout or "").strip()
            if not detail:
                detail = f"returncode={completed.returncode}"
        else:
            raise RuntimeError(f"Chromium 截图失败（{spec.title}）：{detail}")
        ensure_not_truncated(raw_png, capture.html_path)
        crop_non_white(raw_png, output_path)
    return output_path


def render_html_sector_png(html_path: Path, output_path: Path, capture_html_path: Path) -> Path:
    return render_html_section_png(html_path, output_path, capture_html_path, SECTOR_TOURNAMENT_SECTION)


def find_font() -> str | None:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def load_font(font_path: str | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if font_path:
        return ImageFont.truetype(font_path, size=size)
    return ImageFont.load_default()


def render_cover_jpeg(report: ReportContext, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    font_path = find_font()
    title_font = load_font(font_path, 42)
    sub_font = load_font(font_path, 24)
    image = Image.new("RGB", (900, 383), "#f8fafc")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 900, 383), fill="#f8fafc")
    draw.rectangle((0, 0, 900, 28), fill="#0f172a")
    draw.rounded_rectangle((54, 76, 846, 308), radius=24, fill="#ffffff", outline="#cbd5e1", width=2)
    draw.text((90, 122), SECTION_TITLE, fill="#0f172a", font=title_font)
    draw.text((90, 190), f"{report.trade_date} A股日报", fill="#475569", font=sub_font)
    draw.text((90, 236), "板块路径 / 资金载体 / 淘汰理由", fill="#64748b", font=sub_font)
    quality = 88
    image.save(output_path, format="JPEG", quality=quality, optimize=True)
    while output_path.stat().st_size > 64_000 and quality > 45:
        quality -= 8
        image.save(output_path, format="JPEG", quality=quality, optimize=True)
    return output_path


def build_article_html(image_sources: list[tuple[str, str]], report: ReportContext) -> str:
    image_blocks: list[str] = []
    for section_title, image_src in image_sources:
        escaped_image = html.escape(image_src, quote=True)
        escaped_alt = html.escape(f"{report.trade_date} {section_title}")
        image_blocks.append(
            f'<p style="margin:0 0 16px;"><img src="{escaped_image}" alt="{escaped_alt}" style="max-width:100%;height:auto;border-radius:8px;display:block;" /></p>'
        )
    escaped_target = html.escape(display_target(report))
    return "\n".join(
        image_blocks
        + [
            f'<p style="font-size:16px;line-height:1.8;color:#111827;margin:0 0 10px;">今日标的：{escaped_target}</p>',
            '<p style="font-size:14px;line-height:1.8;color:#64748b;margin:0;">模拟持仓，不作为投资买卖依据</p>',
        ]
    )


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_json(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_env_file(path: Path | None) -> None:
    if path is None or not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def first_env(names: list[str]) -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return ""


def resolve_wechat_credentials(slot: str | None) -> tuple[str, str]:
    appid_names = ["WECHAT_APP_ID", "WECHAT_APPID", "WECHAT_OFFICIAL_APP_ID"]
    secret_names = ["WECHAT_APP_SECRET", "WECHAT_APPSECRET", "WECHAT_OFFICIAL_APP_SECRET"]
    if slot:
        slot_text = str(slot)
        appid_names = [f"WECHAT_{slot_text}_APPID", f"WECHAT_{slot_text}_APP_ID"] + appid_names
        secret_names = [f"WECHAT_{slot_text}_APPSECRET", f"WECHAT_{slot_text}_APP_SECRET"] + secret_names
    appid = first_env(appid_names)
    secret = first_env(secret_names)
    if not appid or not secret:
        expected = ", ".join(appid_names[:2] + secret_names[:2])
        raise RuntimeError(f"微信草稿凭据不完整，请配置这些环境变量之一：{expected}")
    return appid, secret


class WeChatDraftClient:
    def __init__(self, appid: str, secret: str, api_base: str = WECHAT_API_BASE) -> None:
        self.appid = appid
        self.secret = secret
        self.api_base = api_base.rstrip("/")
        self._access_token = ""

    def _url(self, path: str) -> str:
        return f"{self.api_base}{path}"

    def _request_json(self, action: str, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = requests.request(method, self._url(path), **kwargs)
        except requests.RequestException as exc:
            raise RuntimeError(f"{action} 请求失败：{exc.__class__.__name__}") from None
        return self._json_response(response, action)

    def _json_response(self, response: requests.Response, action: str) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(f"{action} 返回的不是 JSON：HTTP {response.status_code}") from exc
        errcode = data.get("errcode")
        if errcode not in (None, 0):
            errmsg = data.get("errmsg", "未知错误")
            raise RuntimeError(f"{action} 失败：errcode={errcode}, errmsg={errmsg}")
        return data

    def access_token(self) -> str:
        if self._access_token:
            return self._access_token
        data = self._request_json(
            "获取微信 access_token",
            "GET",
            "/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": self.appid,
                "secret": self.secret,
            },
            timeout=20,
        )
        token = data.get("access_token")
        if not token:
            raise RuntimeError("获取微信 access_token 失败：返回缺少 access_token")
        self._access_token = str(token)
        return self._access_token

    def upload_article_image(self, image_path: Path) -> str:
        media_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
        with image_path.open("rb") as file_obj:
            data = self._request_json(
                "上传正文图片",
                "POST",
                "/cgi-bin/media/uploadimg",
                params={"access_token": self.access_token()},
                files={"media": (image_path.name, file_obj, media_type)},
                timeout=60,
            )
        url = data.get("url")
        if not url:
            raise RuntimeError("上传正文图片失败：返回缺少 url")
        return str(url)

    def upload_thumb(self, image_path: Path) -> str:
        with image_path.open("rb") as file_obj:
            data = self._request_json(
                "上传封面图",
                "POST",
                "/cgi-bin/material/add_material",
                params={"access_token": self.access_token(), "type": "thumb"},
                files={"media": (image_path.name, file_obj, "image/jpeg")},
                timeout=60,
            )
        media_id = data.get("media_id")
        if not media_id:
            raise RuntimeError("上传封面图失败：返回缺少 media_id")
        return str(media_id)

    def create_draft(self, payload: dict[str, Any]) -> str:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        data = self._request_json(
            "创建公众号草稿",
            "POST",
            "/cgi-bin/draft/add",
            params={"access_token": self.access_token()},
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=60,
        )
        media_id = data.get("media_id")
        if not media_id:
            raise RuntimeError("创建公众号草稿失败：返回缺少 media_id")
        return str(media_id)


def build_draft_payload(
    *,
    title: str,
    author: str,
    digest: str,
    content_html: str,
    thumb_media_id: str,
) -> dict[str, Any]:
    return {
        "articles": [
            {
                "title": title[:64],
                "author": author[:8] if author else "",
                "digest": digest[:120],
                "content": content_html,
                "thumb_media_id": thumb_media_id,
                "need_open_comment": 0,
                "only_fans_can_comment": 0,
            }
        ]
    }


def default_title(report: ReportContext) -> str:
    if is_empty_target(report.final_target):
        return "日报目标待确认"
    return "今日策略"


def default_digest(report: ReportContext) -> str:
    return default_title(report)


def build_outputs(args: argparse.Namespace) -> dict[str, Any]:
    if not args.report:
        raise ValueError(
            "公众号草稿仅支持显式传入历史完整版路径；不自动选择最新报告，也不读取当前板块日报"
        )
    report_path = Path(args.report).expanduser()
    if "完整版" not in report_path.stem or report_path.suffix.lower() not in {".md", ".html"}:
        raise ValueError("公众号草稿只接受显式选择的历史完整版，不读取当前板块日报")
    report = report_context_from_input(report_path)
    out_dir = Path(args.out_dir).expanduser() / report.trade_date
    title = args.title or default_title(report)
    digest = args.digest or default_digest(report)
    author = args.author or ""

    html_source_path = resolve_html_report(report.report_path, report.trade_date, args.html_report)
    if html_source_path is None:
        raise FileNotFoundError(f"未找到可截图的日报 HTML：{report.report_path}")
    image_results: list[dict[str, str]] = []
    local_image_sources: list[tuple[str, str]] = []
    for spec in CAPTURE_SECTIONS:
        capture_html_path = out_dir / f"{spec.filename_stem}.capture.html"
        png_path = out_dir / f"{spec.filename_stem}.png"
        png_path = render_html_section_png(html_source_path, png_path, capture_html_path, spec)
        image_results.append(
            {
                "key": spec.key,
                "title": spec.title,
                "png_path": str(png_path.resolve()),
                "capture_html_path": str(capture_html_path.resolve()),
            }
        )
        local_image_sources.append((spec.title, png_path.resolve().as_uri()))
    cover_path = render_cover_jpeg(report, out_dir / "cover.jpg")
    local_html = build_article_html(local_image_sources, report)
    preview_path = write_text(out_dir / "article_preview.html", local_html)
    image_by_key = {item["key"]: item for item in image_results}

    payload_path = out_dir / "draft_payload.json"
    result: dict[str, Any] = {
        "report_path": str(report.report_path),
        "trade_date": report.trade_date,
        "title": title,
        "digest": digest,
        "png_path": image_by_key[SECTOR_TOURNAMENT_SECTION.key]["png_path"],
        "account_day_order_png_path": image_by_key[ACCOUNT_DAY_ORDER_SECTION.key]["png_path"],
        "sector_png_path": image_by_key[SECTOR_TOURNAMENT_SECTION.key]["png_path"],
        "image_paths": image_results,
        "html_source_path": str(html_source_path) if html_source_path else "",
        "capture_html_path": image_by_key[SECTOR_TOURNAMENT_SECTION.key]["capture_html_path"],
        "screenshot_source": "html",
        "cover_path": str(cover_path.resolve()),
        "preview_path": str(preview_path.resolve()),
        "draft_created": False,
        "draft_media_id": "",
    }

    if args.create_draft:
        env_file = Path(args.env_file).expanduser() if args.env_file else None
        load_env_file(env_file)
        appid, secret = resolve_wechat_credentials(args.account_slot)
        client = WeChatDraftClient(appid, secret, api_base=WECHAT_API_BASE)
        remote_image_sources: list[tuple[str, str]] = []
        remote_image_urls: dict[str, str] = {}
        for item in image_results:
            image_url = client.upload_article_image(Path(item["png_path"]))
            remote_image_sources.append((item["title"], image_url))
            remote_image_urls[item["key"]] = image_url
        thumb_media_id = args.cover_media_id or client.upload_thumb(cover_path)
        remote_html = build_article_html(remote_image_sources, report)
        payload = build_draft_payload(
            title=title,
            author=author,
            digest=digest,
            content_html=remote_html,
            thumb_media_id=thumb_media_id,
        )
        media_id = client.create_draft(payload)
        write_json(payload_path, {"articles": [{"title": title, "digest": digest, "content": remote_html}]})
        result.update(
            {
                "draft_created": True,
                "draft_media_id": media_id,
                "wechat_image_urls": remote_image_urls,
                "payload_path": str(payload_path.resolve()),
            }
        )
    else:
        payload = build_draft_payload(
            title=title,
            author=author,
            digest=digest,
            content_html=local_html,
            thumb_media_id=args.cover_media_id or "DRY_RUN_THUMB_MEDIA_ID",
        )
        write_json(payload_path, payload)
        result["payload_path"] = str(payload_path.resolve())

    result_path = write_json(out_dir / "result.json", result)
    result["result_path"] = str(result_path.resolve())
    return result


def print_result(result: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    for item in result.get("image_paths", []):
        print(f"已生成截图：{item['title']} -> {item['png_path']}")
    print(f"已生成本地预览：{result['preview_path']}")
    print(f"已生成草稿载荷：{result['payload_path']}")
    if result.get("draft_created"):
        print(f"已创建公众号草稿：media_id={result['draft_media_id']}")
    else:
        print("未调用微信接口；如需写入公众号草稿，请加 --create-draft。")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="把日报 HTML 固定区块截图成 PNG，并可写入微信公众号草稿。"
    )
    parser.add_argument("report", help="显式传入历史完整版 Markdown 或 HTML 路径")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUTPUT_ROOT), help="输出目录，默认 output/wechat-drafts")
    parser.add_argument("--html-report", default="", help="指定用于截图的日报 HTML；默认找同名 HTML")
    parser.add_argument("--title", default="", help="草稿标题；默认按报告日期生成")
    parser.add_argument("--author", default="", help="作者名，可留空")
    parser.add_argument("--digest", default="", help="草稿摘要；默认按报告日期生成")
    parser.add_argument("--create-draft", action="store_true", help="调用微信接口创建草稿")
    parser.add_argument("--cover-media-id", default="", help="已有微信封面素材 media_id；提供后不上传 cover.jpg")
    parser.add_argument("--env-file", default=".env", help="凭据文件，默认 .env；可传空字符串禁用")
    parser.add_argument("--account-slot", default=os.environ.get("DAILY_REPORT_WECHAT_SLOT", "1"), help="多账号槽位，默认 1")
    parser.add_argument("--json", action="store_true", help="用 JSON 输出结果")
    args = parser.parse_args(argv)
    if args.env_file == "":
        args.env_file = None
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    try:
        result = build_outputs(args)
    except Exception as exc:
        print(f"生成公众号草稿失败：{exc}", file=sys.stderr)
        return 1
    print_result(result, as_json=args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
