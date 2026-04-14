#!/usr/bin/env python3
"""Standalone thermal-printer utility for short text messages.

Renders a message to a receipt-sized PNG and then either:
1. prints directly to the default Windows printer via GDI, or
2. sends the PNG to the local TerminalVG print server (`/print`).
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parent
DEFAULT_MESSAGE_PATH = ROOT / "message.txt"
DEFAULT_PREVIEW_PATH = ROOT / "preview.png"
RECEIPT_WIDTH = 576  # 80mm at 203 DPI, same width as the main project
SIDE_PADDING = 34
TOP_PADDING = 40
BOTTOM_PADDING = 44
BODY_FONT_SIZE = 36
LINE_SPACING = 14
PARAGRAPH_SPACING = 22
RULE_GAP = 24
SPECIAL_CLUSTERS = {"👀", "❤️", "❤"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print a custom message on the thermal printer used by TerminalVG."
    )
    parser.add_argument(
        "--message",
        help="Message text. If omitted, the script reads message.txt from this folder.",
    )
    parser.add_argument(
        "--message-file",
        type=Path,
        help="Path to a UTF-8 text file with the message to print.",
    )
    parser.add_argument(
        "--printer-name",
        help="Explicit printer name. By default, the system default printer is used.",
    )
    parser.add_argument(
        "--server-url",
        help="Optional print endpoint, for example http://localhost:9999/print.",
    )
    parser.add_argument(
        "--save-preview",
        type=Path,
        help="Save the rendered receipt PNG to this path before printing.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only render the PNG preview and do not send anything to the printer.",
    )
    parser.add_argument(
        "--no-rotate",
        action="store_true",
        help="Disable the 180-degree rotation used by the current terminal printer setup.",
    )
    parser.add_argument(
        "--list-printers",
        action="store_true",
        help="List visible Windows printers and exit.",
    )
    return parser.parse_args()


def read_message(args: argparse.Namespace) -> str:
    if args.message:
        return args.message.strip()
    if args.message_file:
        return args.message_file.read_text(encoding="utf-8").strip()
    return DEFAULT_MESSAGE_PATH.read_text(encoding="utf-8").strip()


def font_candidates() -> tuple[list[Path], list[Path]]:
    if sys.platform == "win32":
        win = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        regular = [
            win / "segoeui.ttf",
            win / "arial.ttf",
            win / "tahoma.ttf",
            win / "calibri.ttf",
        ]
        emoji = [
            win / "seguiemj.ttf",
            win / "seguisym.ttf",
            win / "segoeui.ttf",
        ]
        return regular, emoji
    if sys.platform == "darwin":
        regular = [
            Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
            Path("/System/Library/Fonts/Supplemental/Helvetica.ttc"),
        ]
        emoji = [
            Path("/System/Library/Fonts/Apple Color Emoji.ttc"),
            Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        ]
        return regular, emoji
    regular = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ]
    emoji = [
        Path("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    return regular, emoji


def load_first_font(candidates: list[Path], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in candidates:
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def load_fonts() -> tuple[ImageFont.ImageFont, ImageFont.ImageFont]:
    regular_candidates, emoji_candidates = font_candidates()
    regular = load_first_font(regular_candidates, BODY_FONT_SIZE)
    emoji = load_first_font(emoji_candidates, BODY_FONT_SIZE)
    return regular, emoji


def is_emoji_cluster(cluster: str) -> bool:
    return any(
        ord(ch) >= 0x1F300 or ch in {"\u2764", "\ufe0f", "\u200d"}
        for ch in cluster
    )


def split_clusters(text: str) -> list[str]:
    clusters: list[str] = []
    i = 0
    while i < len(text):
        cluster = text[i]
        i += 1
        while i < len(text) and text[i] in {"\ufe0f", "\u200d"}:
            cluster += text[i]
            i += 1
            if cluster.endswith("\u200d") and i < len(text):
                cluster += text[i]
                i += 1
        clusters.append(cluster)
    return clusters


def special_cluster_width(cluster: str) -> int:
    if cluster == "👀":
        return int(BODY_FONT_SIZE * 1.55)
    if cluster in {"❤️", "❤"}:
        return int(BODY_FONT_SIZE * 1.05)
    return 0


def measure_clusters(clusters: list[str], regular_font: ImageFont.ImageFont, emoji_font: ImageFont.ImageFont) -> int:
    width = 0
    for cluster in clusters:
        if cluster in SPECIAL_CLUSTERS:
            width += special_cluster_width(cluster)
            continue
        font = emoji_font if is_emoji_cluster(cluster) else regular_font
        bbox = font.getbbox(cluster)
        if bbox:
            width += bbox[2] - bbox[0]
    return width


def draw_special_cluster(draw: ImageDraw.ImageDraw, x: int, y: int, cluster: str) -> int:
    if cluster == "👀":
        width = special_cluster_width(cluster)
        eye_w = int(BODY_FONT_SIZE * 0.58)
        eye_h = int(BODY_FONT_SIZE * 0.42)
        top = y + int(BODY_FONT_SIZE * 0.28)
        left_eye = (x, top, x + eye_w, top + eye_h)
        right_x = x + eye_w + int(BODY_FONT_SIZE * 0.18)
        right_eye = (right_x, top, right_x + eye_w, top + eye_h)
        draw.ellipse(left_eye, outline=0, width=2)
        draw.ellipse(right_eye, outline=0, width=2)

        pupil_w = max(6, eye_w // 3)
        pupil_h = max(6, eye_h // 2)
        pupil_y = top + (eye_h - pupil_h) // 2
        draw.ellipse(
            (
                x + eye_w // 2 - pupil_w // 2,
                pupil_y,
                x + eye_w // 2 + pupil_w // 2,
                pupil_y + pupil_h,
            ),
            fill=0,
        )
        draw.ellipse(
            (
                right_x + eye_w // 2 - pupil_w // 2,
                pupil_y,
                right_x + eye_w // 2 + pupil_w // 2,
                pupil_y + pupil_h,
            ),
            fill=0,
        )
        return width

    if cluster in {"❤️", "❤"}:
        width = special_cluster_width(cluster)
        heart_w = int(BODY_FONT_SIZE * 0.82)
        heart_h = int(BODY_FONT_SIZE * 0.72)
        left = x + (width - heart_w) // 2
        top = y + int(BODY_FONT_SIZE * 0.18)
        radius = heart_w // 4
        draw.ellipse((left, top, left + radius * 2, top + radius * 2), fill=0)
        draw.ellipse(
            (left + radius * 2 - 2, top, left + radius * 4 - 2, top + radius * 2),
            fill=0,
        )
        draw.polygon(
            [
                (left - 1, top + radius),
                (left + radius * 2, top + heart_h),
                (left + radius * 4 - 2, top + radius),
            ],
            fill=0,
        )
        return width

    return 0


def wrap_paragraph(
    paragraph: str,
    max_width: int,
    regular_font: ImageFont.ImageFont,
    emoji_font: ImageFont.ImageFont,
) -> list[str]:
    if not paragraph:
        return [""]

    tokens = re.findall(r"\S+\s*", paragraph)
    lines: list[str] = []
    current = ""
    for token in tokens:
        candidate = current + token
        candidate_clusters = split_clusters(candidate.rstrip())
        if current and measure_clusters(candidate_clusters, regular_font, emoji_font) > max_width:
            lines.append(current.rstrip())
            current = token
        else:
            current = candidate
    if current:
        lines.append(current.rstrip())
    return lines or [""]


def draw_text_line(
    draw: ImageDraw.ImageDraw,
    y: int,
    line: str,
    regular_font: ImageFont.ImageFont,
    emoji_font: ImageFont.ImageFont,
    image_width: int,
) -> int:
    clusters = split_clusters(line)
    line_width = measure_clusters(clusters, regular_font, emoji_font)
    x = (image_width - line_width) // 2
    for cluster in clusters:
        if cluster in SPECIAL_CLUSTERS:
            x += draw_special_cluster(draw, x, y, cluster)
            continue
        font = emoji_font if is_emoji_cluster(cluster) else regular_font
        draw.text((x, y), cluster, fill=0, font=font)
        bbox = font.getbbox(cluster)
        if bbox:
            x += bbox[2] - bbox[0]
    return x


def render_message_image(message: str, rotate: bool = True) -> Image.Image:
    regular_font, emoji_font = load_fonts()
    line_height = BODY_FONT_SIZE + LINE_SPACING
    max_width = RECEIPT_WIDTH - SIDE_PADDING * 2

    paragraphs = message.splitlines()
    wrapped_blocks = [
        wrap_paragraph(paragraph, max_width, regular_font, emoji_font)
        for paragraph in paragraphs
    ]

    estimated_height = (
        TOP_PADDING
        + BOTTOM_PADDING
        + RULE_GAP * 2
        + sum(len(block) * line_height for block in wrapped_blocks)
        + max(0, len(wrapped_blocks) - 1) * PARAGRAPH_SPACING
    )

    image = Image.new("L", (RECEIPT_WIDTH, estimated_height), color=255)
    draw = ImageDraw.Draw(image)
    y = TOP_PADDING

    draw.line((SIDE_PADDING, y, RECEIPT_WIDTH - SIDE_PADDING, y), fill=0, width=2)
    y += RULE_GAP

    for block_index, lines in enumerate(wrapped_blocks):
        for line in lines:
            draw_text_line(draw, y, line, regular_font, emoji_font, RECEIPT_WIDTH)
            y += line_height
        if block_index != len(wrapped_blocks) - 1:
            y += PARAGRAPH_SPACING

    draw.line((SIDE_PADDING, y, RECEIPT_WIDTH - SIDE_PADDING, y), fill=0, width=2)
    y += RULE_GAP

    cropped = image.crop((0, 0, RECEIPT_WIDTH, y + BOTTOM_PADDING))
    cropped = ImageOps.expand(cropped, border=0, fill=255).convert("RGB")

    if rotate:
        return cropped.rotate(180, expand=True)
    return cropped


def save_preview(image: Image.Image, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")
    return path


def image_to_png_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def send_via_server(img_bytes: bytes, server_url: str) -> tuple[bool, str]:
    payload = json.dumps(
        {"image": "data:image/png;base64," + base64.b64encode(img_bytes).decode("ascii")}
    ).encode("utf-8")
    request = urllib.request.Request(
        server_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read()
        data = json.loads(body.decode("utf-8"))
        return bool(data.get("success")), str(data.get("message", ""))
    except urllib.error.URLError as exc:
        return False, f"Server print failed: {exc}"


def print_image_gdi(img_bytes: bytes, printer_name: str | None = None) -> tuple[bool, str]:
    if sys.platform != "win32":
        return False, "Direct GDI printing is supported only on Windows."

    try:
        import win32print
        import win32ui
        from PIL import ImageWin
    except ImportError as exc:
        return False, f"Missing library: {exc}. Run: pip install pywin32 Pillow"

    try:
        target_printer = printer_name or win32print.GetDefaultPrinter()
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(target_printer)
        hdc.StartDoc("TerminalVG_Custom_Message")
        hdc.StartPage()

        page_w = hdc.GetDeviceCaps(110)  # PHYSICALWIDTH
        page_h = hdc.GetDeviceCaps(111)  # PHYSICALHEIGHT
        width, height = image.size
        ratio = min(page_w / width, page_h / height)
        scaled_w = int(width * ratio)
        scaled_h = int(height * ratio)
        x = (page_w - scaled_w) // 2
        y = 0

        dib = ImageWin.Dib(image)
        dib.draw(hdc.GetHandleOutput(), (x, y, x + scaled_w, y + scaled_h))

        hdc.EndPage()
        hdc.EndDoc()
        hdc.DeleteDC()
        return True, f"Printed on '{target_printer}'"
    except Exception as exc:
        return False, f"GDI print error: {exc}"


def list_printers() -> int:
    if sys.platform != "win32":
        print("Printer enumeration is available only on Windows.")
        return 1
    try:
        import win32print
    except ImportError:
        print("pywin32 is not installed. Run: pip install pywin32")
        return 1

    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    printers = [info[2] for info in win32print.EnumPrinters(flags)]
    default = win32print.GetDefaultPrinter()
    for printer in printers:
        marker = "*" if printer == default else " "
        print(f"{marker} {printer}")
    return 0


def main() -> int:
    args = parse_args()

    if args.list_printers:
        return list_printers()

    message = read_message(args)
    if not message:
        print("Message is empty.")
        return 1

    image = render_message_image(message, rotate=not args.no_rotate)
    preview_target = args.save_preview or (DEFAULT_PREVIEW_PATH if args.dry_run else None)
    if preview_target:
        saved = save_preview(image, preview_target)
        print(f"Preview saved to: {saved}")

    if args.dry_run:
        print("Dry run complete. Nothing was sent to the printer.")
        return 0

    img_bytes = image_to_png_bytes(image)
    if args.server_url:
        success, message = send_via_server(img_bytes, args.server_url)
    else:
        success, message = print_image_gdi(img_bytes, printer_name=args.printer_name)

    print(message)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
