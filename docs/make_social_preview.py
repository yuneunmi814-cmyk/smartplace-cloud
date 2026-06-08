"""Generate the GitHub social-preview image (1280x640) for the repo.

    backend/.venv/bin/python docs/make_social_preview.py

Output: docs/social-preview.png. Upload it via GitHub → Settings → General →
Social preview (there is no API/CLI for that upload)."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
W, H = 1280, 640
BG = (18, 24, 43)          # dark navy
GREEN = (45, 180, 0)       # Naver green
WHITE = (255, 255, 255)
GRAY = (183, 190, 207)
MUTED = (120, 128, 148)

KO = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"
ARIAL_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def rounded(img: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, *img.size], radius, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def main() -> None:
    canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)

    # Left accent bar.
    d.rectangle([0, 0, 10, H], fill=GREEN)

    x = 70
    # Kicker.
    d.text((x, 86), "NAVER SMARTPLACE · BULK MANAGER", font=font(ARIAL_BOLD, 22), fill=GREEN)
    # Title.
    d.text((x, 120), "SmartPlace Bulk", font=font(ARIAL_BOLD, 70), fill=WHITE)

    # English tagline (wrapped).
    en = "Push a main photo & menu to every franchise branch — at once."
    y = 220
    for line in wrap(d, en, font(ARIAL, 30), 600):
        d.text((x, y), line, font=font(ARIAL, 30), fill=GRAY)
        y += 40

    # Korean tagline.
    y += 14
    ko_font = font(KO, 27)
    for line in ["네이버 스마트플레이스 대표사진·메뉴", "전 지점 일괄 등록 데스크톱 앱"]:
        d.text((x, y), line, font=ko_font, fill=GRAY)
        y += 38

    # Footer chips.
    d.text((x, H - 80), "Desktop app  ·  Windows / Mac  ·  MIT  ·  Open source",
           font=font(ARIAL, 22), fill=MUTED)

    # Right: screenshot in a rounded card with a thin border.
    shot = Image.open(ROOT / "screenshot-main.png").convert("RGB")
    box_w, box_h = 470, 470
    scale = min(box_w / shot.width, box_h / shot.height)
    shot = shot.resize((int(shot.width * scale), int(shot.height * scale)))
    card = rounded(shot.convert("RGBA"), 18)
    px = W - card.width - 70
    py = (H - card.height) // 2
    # Border frame.
    d.rounded_rectangle([px - 3, py - 3, px + card.width + 3, py + card.height + 3],
                        radius=20, outline=(60, 70, 95), width=3)
    canvas.paste(card, (px, py), card)

    out = ROOT / "social-preview.png"
    canvas.save(out)
    print(f"wrote {out} ({W}x{H})")


if __name__ == "__main__":
    main()
