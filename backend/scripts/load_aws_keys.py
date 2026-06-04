"""Reads the most recent AWS access-key CSV from ~/Downloads and writes the S3
settings into backend/.env. The secret key is NEVER printed — only written to
.env (which is gitignored).

Usage:  python -m scripts.load_aws_keys [BUCKET] [REGION]
"""

import csv
import re
import sys
from pathlib import Path

BUCKET = sys.argv[1] if len(sys.argv) > 1 else "smartplace-img-jane-0604"
REGION = sys.argv[2] if len(sys.argv) > 2 else "ap-northeast-2"


def parse_csv(path: Path):
    # utf-8-sig strips the BOM that the AWS console prepends to the header.
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None
    row = {k.lower().strip(): (v or "").strip() for k, v in rows[0].items()}
    akid = row.get("access key id")
    secret = row.get("secret access key")
    if akid and secret and akid.startswith("AKIA"):
        return akid, secret
    return None


def main() -> None:
    downloads = Path.home() / "Downloads"
    csvs = sorted(downloads.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)

    found = None
    chosen = None
    for p in csvs:
        try:
            found = parse_csv(p)
        except Exception:
            found = None
        if found:
            chosen = p
            break

    if not found:
        print("❌ Downloads 폴더에서 AWS 액세스 키 CSV를 찾지 못했습니다.")
        sys.exit(1)

    akid, secret = found
    base = Path(__file__).resolve().parents[1]
    env_path = base / ".env"
    example = base / ".env.example"
    text = env_path.read_text() if env_path.exists() else (
        example.read_text() if example.exists() else ""
    )

    values = {
        "SMARTPLACE_S3_BUCKET": BUCKET,
        "SMARTPLACE_S3_REGION": REGION,
        "SMARTPLACE_AWS_ACCESS_KEY_ID": akid,
        "SMARTPLACE_AWS_SECRET_ACCESS_KEY": secret,
    }

    lines = text.splitlines()
    for key, value in values.items():
        pat = re.compile(rf"^\s*{re.escape(key)}=")
        for i, line in enumerate(lines):
            if pat.match(line):
                lines[i] = f"{key}={value}"
                break
        else:
            lines.append(f"{key}={value}")

    env_path.write_text("\n".join(lines) + "\n")

    print("✅ .env 업데이트 완료 (비밀 키는 출력하지 않음)")
    print(f"   사용한 CSV : {chosen.name}")
    print(f"   액세스 키 ID: {akid[:8]}…{akid[-3:]}")
    print(f"   비밀 키     : {len(secret)}자 기록됨")
    print(f"   버킷/리전   : {BUCKET} / {REGION}")


if __name__ == "__main__":
    main()
