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


def stub(directory: Path, name: str, body: str, interpreter: str = "sh") -> None:
    path = directory / name
    path.write_text(f"#!/bin/{interpreter}\n" + body)
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


SECRETS = {"none": {}, "proton-pass": {"secrets_vault": "demo"}}
CREDENTIALS = {
    "AWS_ACCESS_KEY_ID": "key-id",
    "AWS_SECRET_ACCESS_KEY": ACCESS_KEY,
    "AWS_ENDPOINT_URL_S3": "https://account.eu.r2.cloudflarestorage.com/",
}


@pytest.fixture(scope="module", params=list(SECRETS))
def apply_task(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    if shutil.which("copier") is None:
        pytest.skip("needs copier on PATH")
    project = render_template(
        tmp_path_factory.mktemp("render"),
        opentofu="true",
        opentofu_state_backup="true",
        openspec="none",
        secrets_provider=request.param,
        **SECRETS[request.param],
    )
    return project / ".config/mise/tasks/opentofu/apply"


def fnox_config(task: Path) -> Path:
    """Return the rendered fnox.toml. Its presence makes the task use fnox."""
    return task.parents[4] / "opentofu/fnox.toml"


def run_apply(
    tmp_path: Path,
    task: Path,
    *,
    state: str = ENCRYPTED,
    changes: bool = True,
    fails: str = "",
) -> tuple[subprocess.CompletedProcess[str], list[str], Path]:
    """Run the task with stubs: `tofu` changes the ETag that `curl --head` reports.

    `fails` names the stub that fails: `gh`, or `download` for the snapshot.
    """
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
        '  *) while [ "$1" != --output ]; do shift; done; cp "$STATE" "$2"\n'
        '     [ -z "$DOWNLOAD_FAILS" ] || exit 18 ;;\n'
        "esac\n",
    )
    stub(
        tools,
        "tofu",
        'printf "tofu %s\\n" "$*" >> "$CALLS"\n'
        '[ -z "$CHANGES" ] || echo two > "$ETAG"\n',
    )
    stub(tools, "gh", 'printf "gh %s\\n" "$*" >> "$CALLS"\n[ -z "$GH_FAILS" ]\n')
    # Like fnox, the stub sets the credentials only in the command that it runs.
    stub(
        tools,
        "fnox",
        'printf "%s\\n" "$*" >> "$FNOX_CALLS"\n'
        'while [ "$1" != -- ]; do shift; done\nshift\n'
        'export AWS_ACCESS_KEY_ID="$STUB_KEY_ID" AWS_SECRET_ACCESS_KEY="$STUB_KEY"\n'
        'export AWS_ENDPOINT_URL_S3="$STUB_ENDPOINT"\nexec "$@"\n',
        # dash, Ubuntu's sh, drops the `export -f r2_curl` env entry. fnox keeps it.
        interpreter="bash",
    )
    (tmp_path / "fnox_calls").touch()
    env = project_env()
    if fnox_config(task).exists():
        shutil.copy(fnox_config(task), tmp_path / "fnox.toml")
        credentials = {}
        for name in CREDENTIALS:
            env.pop(name, None)
    else:
        credentials = CREDENTIALS
    env.update(
        PATH=f"{tools}{os.pathsep}{env['PATH']}",
        CALLS=str(calls),
        ETAG=str(etag),
        STATE=str(tmp_path / "state"),
        CHANGES="1" if changes else "",
        GH_FAILS="1" if fails == "gh" else "",
        DOWNLOAD_FAILS="1" if fails == "download" else "",
        FNOX_CALLS=str(tmp_path / "fnox_calls"),
        STUB_KEY_ID=CREDENTIALS["AWS_ACCESS_KEY_ID"],
        STUB_KEY=CREDENTIALS["AWS_SECRET_ACCESS_KEY"],
        STUB_ENDPOINT=CREDENTIALS["AWS_ENDPOINT_URL_S3"],
        **credentials,
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
    if fnox_config(apply_task).exists():
        # The R2 reads are saved or compared, so they skip redaction. The apply masks.
        assert (tmp_path / "fnox_calls").read_text().splitlines() == [
            'exec --no-redact -- bash -c r2_curl "$@" r2_curl --head',
            'exec --no-redact -- bash -c r2_curl "$@" r2_curl --output '
            + str(next(snapshots.iterdir())),
            "exec -- tofu apply -input=false -lock-timeout=60s tfplan",
            'exec --no-redact -- bash -c r2_curl "$@" r2_curl --head',
        ]
    else:
        assert (tmp_path / "fnox_calls").read_text() == ""
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


@pytest.mark.parametrize(
    "state",
    [
        '{"encryption_version": "v0", "encrypted_data": null}',
        '{"encryption_version": "v0", "encrypted_data": ""}',
        '{"encryption_version": "", "encrypted_data": "abc"}',
        "not json",
    ],
)
def test_apply_refuses_a_state_without_encrypted_data(
    tmp_path: Path, apply_task: Path, state: str
) -> None:
    result, calls, snapshots = run_apply(tmp_path, apply_task, state=state)

    assert result.returncode == 1
    assert "not encrypted" in result.stderr
    assert not any(call.startswith("tofu ") for call in calls)
    assert list(snapshots.iterdir()) == []


def test_apply_removes_a_partial_snapshot_when_the_download_fails(
    tmp_path: Path, apply_task: Path
) -> None:
    result, calls, snapshots = run_apply(tmp_path, apply_task, fails="download")

    assert result.returncode == 1
    assert "cannot download" in result.stderr
    assert not any(call.startswith("tofu ") for call in calls)
    assert list(snapshots.iterdir()) == []


def test_apply_only_warns_when_the_dispatch_fails(
    tmp_path: Path, apply_task: Path
) -> None:
    result, calls, _ = run_apply(tmp_path, apply_task, fails="gh")

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
