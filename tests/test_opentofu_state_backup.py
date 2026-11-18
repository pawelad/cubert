"""Check the OpenTofu state backup script and `opentofu:apply`, with stub tools."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.support import ROOT, project_env, render_template

BACKUP_SCRIPT = ROOT / "template/.config/opentofu/state-backup.sh"
PING_URL = "https://example.test/ping-token"
# Must never appear in a process argument.
ACCESS_KEY = "r2-access-key-value"
ENCRYPTED = json.dumps({"encryption_version": "v0", "encrypted_data": "abc"})


def stub(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o700)


def run_backup(
    tmp_path: Path, *, fail_copy: bool = False, ping_url: str = PING_URL
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    calls = tmp_path / "calls"
    calls.touch()
    stub(tmp_path, "wget", 'printf "ping %s\\n" "$6" >> "$CALLS"\n')
    stub(tmp_path, "rclone", 'printf "%s\\n" "$*" >> "$CALLS"\n[ -z "$FAIL_COPY" ]\n')
    result = subprocess.run(  # noqa: S603
        ["sh", str(BACKUP_SCRIPT)],  # noqa: S607
        env={
            "PATH": f"{tmp_path}:{os.defpath}",
            "CALLS": str(calls),
            "FAIL_COPY": "1" if fail_copy else "",
            "HEALTHCHECKS_PING_URL": ping_url,
            "STATE_BUCKET": "demo-opentofu-state",
            "BACKUP_BUCKET": "demo-opentofu-state-backups",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    return result, calls.read_text().splitlines()


def test_backup_copies_only_the_state_object_and_pings_success(
    tmp_path: Path,
) -> None:
    result, calls = run_backup(tmp_path)

    assert result.returncode == 0, result.stderr
    assert calls == [
        f"ping {PING_URL}/start",
        (
            "copyto r2:demo-opentofu-state/terraform.tfstate "
            "b2:demo-opentofu-state-backups/terraform.tfstate --ignore-times"
        ),
        f"ping {PING_URL}",
    ]


def test_failed_backup_pings_failure(tmp_path: Path) -> None:
    result, calls = run_backup(tmp_path, fail_copy=True)

    assert result.returncode == 1
    assert calls[-1] == f"ping {PING_URL}/fail"


def test_backup_without_ping_url_fails_before_copying(tmp_path: Path) -> None:
    result, calls = run_backup(tmp_path, ping_url="")

    assert result.returncode != 0
    assert calls == []


def test_apply_without_the_backup_only_applies(tmp_path: Path) -> None:
    if shutil.which("copier") is None:
        pytest.skip("needs copier on PATH")
    project = render_template(tmp_path, opentofu="true", openspec="none")
    task = (project / ".config/mise/tasks/opentofu/apply").read_text()

    assert "gh workflow run" not in task
    assert not (project / ".github/workflows/opentofu-state-backup.yml").exists()
    assert not (project / ".config/opentofu").exists()
    assert 'tofu apply -input=false -lock-timeout=60s "$@"' in task


@pytest.fixture(scope="module")
def apply_task(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if shutil.which("copier") is None:
        pytest.skip("needs copier on PATH")
    project = render_template(
        tmp_path_factory.mktemp("render"),
        opentofu="true",
        opentofu_state_backup="true",
        openspec="none",
    )
    return project / ".config/mise/tasks/opentofu/apply"


def run_apply(
    tmp_path: Path,
    task: Path,
    *,
    state: str = ENCRYPTED,
    changes: bool = True,
    gh_fails: bool = False,
) -> tuple[subprocess.CompletedProcess[str], list[str], Path]:
    """Run the task with stubs: `tofu` changes the ETag that `curl --head` reports."""
    tools = tmp_path / "bin"
    tools.mkdir()
    calls = tmp_path / "calls"
    calls.touch()
    etag = tmp_path / "etag"
    etag.write_text("one")
    (tmp_path / "state").write_text(state)
    stub(
        tools,
        "curl",
        'printf "curl %s\\n" "$*" >> "$CALLS"\ncat > /dev/null\n'
        'case " $* " in\n'
        '  *" --head "*) printf \'ETag: "%s"\\r\\n\' "$(cat "$ETAG")" ;;\n'
        '  *) while [ "$1" != --output ]; do shift; done; cp "$STATE" "$2" ;;\n'
        "esac\n",
    )
    stub(
        tools,
        "tofu",
        'printf "tofu %s\\n" "$*" >> "$CALLS"\n'
        '[ -z "$CHANGES" ] || echo two > "$ETAG"\n',
    )
    stub(tools, "gh", 'printf "gh %s\\n" "$*" >> "$CALLS"\n[ -z "$GH_FAILS" ]\n')
    env = project_env()
    env.update(
        PATH=f"{tools}{os.pathsep}{env['PATH']}",
        CALLS=str(calls),
        ETAG=str(etag),
        STATE=str(tmp_path / "state"),
        CHANGES="1" if changes else "",
        GH_FAILS="1" if gh_fails else "",
        AWS_ACCESS_KEY_ID="key-id",
        AWS_SECRET_ACCESS_KEY=ACCESS_KEY,
        AWS_ENDPOINT_URL_S3="https://account.eu.r2.cloudflarestorage.com/",
        MISE_PROJECT_ROOT=str(tmp_path),
        # Skip the mise exec rerun that loads the OpenTofu env.
        OPENTOFU_TASK_ENV="1",
    )
    result = subprocess.run(  # noqa: S603
        ["bash", str(task), "tfplan"],  # noqa: S607
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result, calls.read_text().splitlines(), tmp_path / "tmp/opentofu-state"


def test_apply_dispatches_the_backup_when_the_state_changes(
    tmp_path: Path, apply_task: Path
) -> None:
    result, calls, snapshots = run_apply(tmp_path, apply_task)

    assert result.returncode == 0, result.stderr
    assert [call.split()[0] for call in calls] == [
        "curl", "curl", "tofu", "curl", "gh",
    ]  # fmt: skip
    assert calls[0].endswith(
        "https://account.eu.r2.cloudflarestorage.com/demo-opentofu-state/terraform.tfstate"
    )
    assert calls[2] == "tofu apply -input=false -lock-timeout=60s tfplan"
    assert calls[4] == (
        "gh workflow run opentofu-state-backup.yml --repo pawelad/demo --ref main"
    )
    assert not any(ACCESS_KEY in call for call in calls)
    [snapshot] = snapshots.iterdir()
    assert snapshot.read_text() == ENCRYPTED
    assert snapshot.stat().st_mode & 0o077 == 0


def test_apply_skips_the_backup_when_the_state_is_unchanged(
    tmp_path: Path, apply_task: Path
) -> None:
    result, calls, _ = run_apply(tmp_path, apply_task, changes=False)

    assert result.returncode == 0, result.stderr
    assert any(call.startswith("tofu apply") for call in calls)
    assert not any(call.startswith("gh ") for call in calls)
    assert "State unchanged" in result.stdout


def test_apply_refuses_a_plaintext_state(tmp_path: Path, apply_task: Path) -> None:
    result, calls, snapshots = run_apply(
        tmp_path, apply_task, state='{"version": 4, "resources": []}'
    )

    assert result.returncode == 1
    assert "not encrypted" in result.stderr
    assert not any(call.startswith("tofu ") for call in calls)
    assert list(snapshots.iterdir()) == []


def test_apply_only_warns_when_the_dispatch_fails(
    tmp_path: Path, apply_task: Path
) -> None:
    result, calls, _ = run_apply(tmp_path, apply_task, gh_fails=True)

    assert result.returncode == 0
    assert calls[-1].startswith("gh workflow run")
    assert "dispatch failed" in result.stderr


@pytest.mark.parametrize(
    "bucket", ["Demo-state", "-demo-state", "demo_state", "x" * 56]
)
def test_unsupported_state_bucket_fails_before_render(
    tmp_path: Path, bucket: str
) -> None:
    if shutil.which("copier") is None:
        pytest.skip("needs copier on PATH")
    with pytest.raises(AssertionError, match="Validation error for question"):
        render_template(
            tmp_path,
            opentofu="true",
            opentofu_state_backup="true",
            opentofu_state_bucket=bucket,
        )
