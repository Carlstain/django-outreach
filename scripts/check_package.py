import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

PACKAGE_ROOT = REPOSITORY_ROOT / "src" / "outreach"
REQUIRED_WHEEL_SUFFIXES = ["LICENSE"]
FORBIDDEN_WHEEL_PREFIXES = ["tests/", ".github/"]


def source_files() -> list[str]:
    return sorted(
        f"outreach/{path.relative_to(PACKAGE_ROOT).as_posix()}"
        for path in PACKAGE_ROOT.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )


def build_wheel() -> Path:
    distribution_directory = REPOSITORY_ROOT / "dist"
    shutil.rmtree(distribution_directory, ignore_errors=True)
    subprocess.run(["uv", "build", "--wheel"], cwd=REPOSITORY_ROOT, check=True)
    wheels = distribution_directory.glob("django_outreach-*.whl")
    return max(wheels, key=lambda wheel: wheel.stat().st_mtime)


def check_wheel_contents(wheel_path: Path) -> list[str]:
    errors = []
    with zipfile.ZipFile(wheel_path) as wheel:
        member_names = set(wheel.namelist())
    for name in sorted(member_names):
        print(name)
    expected_files = source_files()
    for expected in expected_files:
        if expected not in member_names:
            errors.append(f"missing from wheel: {expected}")
    if not any(name.endswith(".mo") for name in expected_files):
        errors.append("the source tree has no compiled translation (.mo)")
    if "outreach/THIRD_PARTY_NOTICES.md" not in expected_files:
        errors.append("the source tree has no THIRD_PARTY_NOTICES.md")
    for suffix in REQUIRED_WHEEL_SUFFIXES:
        if not any(name.endswith(f"/{suffix}") or name == suffix for name in member_names):
            errors.append(f"missing from wheel: {suffix}")
    for prefix in FORBIDDEN_WHEEL_PREFIXES:
        leaked = [name for name in member_names if name.startswith(prefix)]
        if leaked:
            errors.append(f"must not be in the wheel: {leaked}")
    return errors


def main() -> int:
    errors = check_wheel_contents(build_wheel())
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
