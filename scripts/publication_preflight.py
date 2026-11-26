"""Fail-closed preflight for an index, candidate manifest and distribution archives."""

import argparse
import io
import subprocess
import tarfile
import zlib
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

from check_public_tree import blocked_path, index_entries
from private_exclusion_policy import (
    POLICY_NAMES,
    SEAL_FILE,
    PolicyError,
    PrivatePolicy,
    load_policy,
    safe_path,
)

MAX_MEMBER = 32 * 1024 * 1024
MAX_ASSET = 128 * 1024 * 1024
MAX_MEMBERS = 4096


def inspect_path(name: str, policy: PrivatePolicy, *, index: bool = False) -> None:
    if not safe_path(name):
        raise PolicyError("Unsafe publication path detected.")
    path = PurePosixPath(name.casefold())
    if (
        POLICY_NAMES.intersection(path.parts)
        or policy.protects(path)
        or policy.discloses(name.encode("utf-8"))
        or (index and blocked_path(path))
    ):
        raise PolicyError("Protected publication path detected.")


def inspect_content(data: bytes, policy: PrivatePolicy) -> None:
    if len(data) > MAX_MEMBER:
        raise PolicyError("Publication file exceeds inspection limits.")
    if policy.discloses(data):
        raise PolicyError("Protected content detected.")


def examine_archive(path: Path, policy: PrivatePolicy) -> None:
    inspect_path(path.name, policy)
    if path.is_symlink() or path.stat().st_size > MAX_ASSET:
        raise PolicyError("Publication archive exceeds inspection limits or is unsafe.")
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            total = 0
            for count, member in enumerate(archive, 1):
                inspect_path(member.name.rstrip("/"), policy)
                if count > MAX_MEMBERS or not (member.isfile() or member.isdir()):
                    raise PolicyError("Unsafe source archive member detected.")
                if not member.isfile():
                    continue
                total += member.size
                if member.size > MAX_MEMBER or total > MAX_ASSET:
                    raise PolicyError("Source archive exceeds inspection limits.")
                stream = archive.extractfile(member)
                if stream is None:
                    raise PolicyError("Source archive member could not be inspected.")
                with stream:
                    inspect_content(stream.read(MAX_MEMBER + 1), policy)
    elif path.suffix in {".vsix", ".whl"}:
        with ZipFile(path) as archive:
            examine_zip(archive, policy)
    else:
        raise PolicyError("Unsupported publication archive.")


def examine_zip(archive: ZipFile, policy: PrivatePolicy, *, nested: bool = False) -> None:
    entries = archive.infolist()
    if len(entries) > MAX_MEMBERS or sum(entry.file_size for entry in entries) > MAX_ASSET:
        raise PolicyError("Publication archive exceeds inspection limits.")
    if len({entry.filename for entry in entries}) != len(entries):
        raise PolicyError("Duplicate publication archive paths detected.")
    for entry in entries:
        inspect_path(entry.filename.rstrip("/"), policy)
        if (entry.external_attr >> 16) & 0o170000 == 0o120000 or entry.file_size > MAX_MEMBER:
            raise PolicyError("Unsafe publication archive member detected.")
        if entry.is_dir():
            continue
        data = archive.read(entry)
        if entry.filename.endswith(".whl") and not nested:
            with ZipFile(io.BytesIO(data)) as wheel:
                examine_zip(wheel, policy, nested=True)
        else:
            inspect_content(data, policy)


def scan_candidates(root: Path, policy: PrivatePolicy, manifest: Path | None) -> None:
    if manifest is None:
        entries = list(index_entries(root))
        if not entries:
            raise PolicyError("Publication Git index is empty.")
        remaining_controls = {".gitignore", SEAL_FILE}
        for mode, digest, stage, name in entries:
            inspect_path(name, policy, index=True)
            if mode not in {"100644", "100755"} or stage != "0":
                raise PolicyError("Unsafe or unmerged Git index entry detected.")
            if (
                int(
                    subprocess.check_output(
                        ["git", "cat-file", "-s", digest], cwd=root, stderr=subprocess.DEVNULL
                    )
                )
                > MAX_MEMBER
            ):
                raise PolicyError("Publication file exceeds inspection limits.")
            content = subprocess.check_output(
                ["git", "cat-file", "blob", digest], cwd=root, stderr=subprocess.DEVNULL
            )
            inspect_content(content, policy)
            if name in remaining_controls:
                disk = (root / name).read_bytes().replace(b"\r\n", b"\n")
                if content.replace(b"\r\n", b"\n") != disk:
                    raise PolicyError(
                        "Publication index policy controls differ from the working tree."
                    )
                remaining_controls.remove(name)
        if remaining_controls:
            raise PolicyError("Publication index policy controls are missing.")
        return
    paths = manifest.read_text(encoding="utf-8-sig").splitlines()
    if not paths:
        raise PolicyError("Publication candidate manifest is empty.")
    for name in paths:
        inspect_path(name, policy, index=True)
        path = root / name
        if (
            path.resolve(strict=True) != path
            or not path.is_file()
            or path.stat().st_size > MAX_MEMBER
        ):
            raise PolicyError("Unsafe publication candidate detected.")
        inspect_content(path.read_bytes(), policy)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--policy-env", action="store_true")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--archive", type=Path, action="append", default=[])
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--write-local-ignore", action="store_true")
    args = parser.parse_args()
    try:
        root = args.root.resolve(strict=True)
        policy = load_policy(root, args.policy_env)
        print("Private policy valid.")
        if args.write_local_ignore:
            if args.policy_env or not args.validate_only:
                raise PolicyError("Local ignore export requires local validate-only mode.")
            from private_exclusion_policy import IGNORE_FILE

            with (root / IGNORE_FILE).open("x", encoding="utf-8") as file:
                file.write("\n".join(policy.git_ignore) + "\n")
        if args.validate_only:
            if args.archive or args.manifest:
                raise PolicyError("Validate-only mode cannot inspect publication candidates.")
            return
        scan_candidates(root, policy, args.manifest)
        for archive in args.archive:
            examine_archive(archive, policy)
    except PolicyError as error:
        raise SystemExit(str(error)) from None
    except (
        OSError,
        ValueError,
        subprocess.SubprocessError,
        BadZipFile,
        tarfile.TarError,
        RuntimeError,
        EOFError,
        zlib.error,
    ):
        raise SystemExit("Publication input unreadable or unverifiable.") from None
    print(f"Publication scan passed. Archives checked: {len(args.archive)}.")


if __name__ == "__main__":
    main()
