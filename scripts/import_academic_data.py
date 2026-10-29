"""Import a university's courses, prerequisites and staff directory from a JSON file.

Run from the project folder (after `alembic upgrade head`):
  .\\.venv\\Scripts\\python.exe -m scripts.import_academic_data data\\gju_data.json --domain gju.edu.jo

The file stays on your computer: `data/` is ignored by git. Rows are stored with
verified=False unless you pass --verified. The command prints counts only, never names, emails or phone numbers.
"""
import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from app.core.database import AsyncSessionLocal, async_engine
from app.models.academic import Course
from app.models.university import University
from app.services.academic import import_academic_data


async def main(path: Path, domain: str, name: str, source: str, verified: bool, overwrite: bool = False) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    async with AsyncSessionLocal() as db:
        uni = (await db.execute(select(University).where(University.domain == domain))).scalars().first()
        if uni is None:
            uni = University(name=name, domain=domain)
            db.add(uni)
            await db.commit()
            await db.refresh(uni)
            print(f"Created university '{name}' ({domain}) with id {uni.id}")
        else:
            print(f"Using existing university id {uni.id} ({domain})")
        try:
            result = await import_academic_data(db, uni.id, data, source=source, verified=verified,
                                            overwrite_conflicts=overwrite)
        except ProgrammingError as exc:
            if "does not exist" in str(exc):
                print("A database table is missing. Run this first, then try again:")
                print("  .\\.venv\\Scripts\\python.exe -m alembic upgrade head")
                await async_engine.dispose()
                return 1
            raise
        leftovers: list[str] = []
        if data.get("replace_prerequisites"):  # a complete study plan: show courses it does not contain
            in_file = {str(c["code"]).replace(" ", "").upper() for c in data.get("courses", [])}
            rows = await db.execute(select(Course.code, Course.verified).where(Course.university_id == uni.id))
            leftovers = sorted(code for code, verified_flag in rows.all() if code not in in_file)
    await async_engine.dispose()
    problems = result.pop("problems")
    conflicts = result.pop("conflicts")
    for key, value in result.items():
        print(f"  {key}: {value}")
    print(f"  rows skipped or flagged: {len(problems)}")
    if leftovers:
        print(f"  courses in the database that are NOT in this plan: {len(leftovers)}")
        print("    " + ", ".join(leftovers))
        print("    (nothing was deleted; ask before removing old data)")
    if conflicts:
        print(f"  DIFFERENCES from data already stored (kept, not overwritten; use --overwrite to replace): {result['conflicts_kept']}")
        for line in conflicts[:15]:
            print(f"    ~ {line}")
    for line in problems[:20]:
        print(f"    - {line}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file", type=Path)
    parser.add_argument("--domain", default="gju.edu.jo")
    parser.add_argument("--name", default="German Jordanian University")
    parser.add_argument(
        "--source",
        default="Provided by a GJU student from university material; not yet verified",
        help="Where the data came from (stored on every row)",
    )
    parser.add_argument(
        "--verified",
        action="store_true",
        help="Mark rows verified. Use only after you compared a sample with the official source.",
    )
    parser.add_argument("--overwrite", action="store_true",
                        help="Replace shared course data that came from another file (default: keep it and report)")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.file, args.domain, args.name, args.source, args.verified, args.overwrite)))
