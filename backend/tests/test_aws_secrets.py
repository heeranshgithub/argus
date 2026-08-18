"""Tests for the Secrets Manager -> os.environ loader."""

import json
import sys
import types

import pytest

from app.aws_secrets import SECRETS_ID_VAR, SecretsLoadError, load_aws_secrets


class _FakeClient:
    """Stands in for a boto3 secretsmanager client."""

    def __init__(self, *, payload: str | None = None, error: Exception | None = None):
        self._payload = payload
        self._error = error
        self.requested: str | None = None

    def get_secret_value(self, SecretId: str) -> dict[str, str]:
        self.requested = SecretId
        if self._error is not None:
            raise self._error
        return {} if self._payload is None else {"SecretString": self._payload}


@pytest.fixture
def fake_boto3(monkeypatch: pytest.MonkeyPatch):
    """Install a stub boto3/botocore so no AWS call is ever made."""
    holder: dict[str, _FakeClient] = {}

    def _install(client: _FakeClient) -> _FakeClient:
        holder["client"] = client
        boto3 = types.ModuleType("boto3")
        boto3.client = lambda service, region_name=None: client  # type: ignore[attr-defined]

        botocore = types.ModuleType("botocore")
        exceptions = types.ModuleType("botocore.exceptions")

        class BotoCoreError(Exception):
            pass

        class ClientError(Exception):
            pass

        exceptions.BotoCoreError = BotoCoreError  # type: ignore[attr-defined]
        exceptions.ClientError = ClientError  # type: ignore[attr-defined]
        botocore.exceptions = exceptions  # type: ignore[attr-defined]

        monkeypatch.setitem(sys.modules, "boto3", boto3)
        monkeypatch.setitem(sys.modules, "botocore", botocore)
        monkeypatch.setitem(sys.modules, "botocore.exceptions", exceptions)
        return client

    return _install


def test_no_secret_id_is_a_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SECRETS_ID_VAR, raising=False)
    assert load_aws_secrets() == []


def test_blank_secret_id_is_a_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SECRETS_ID_VAR, "   ")
    assert load_aws_secrets() == []


def test_loads_keys_into_environ(monkeypatch: pytest.MonkeyPatch, fake_boto3) -> None:
    fake_boto3(_FakeClient(payload=json.dumps({"MONGO_DB_NAME": "argus", "LOG_LEVEL": "DEBUG"})))
    monkeypatch.setenv(SECRETS_ID_VAR, "argus-backend/config")
    monkeypatch.delenv("MONGO_DB_NAME", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    applied = load_aws_secrets()

    assert sorted(applied) == ["LOG_LEVEL", "MONGO_DB_NAME"]
    import os

    assert os.environ["MONGO_DB_NAME"] == "argus"
    assert os.environ["LOG_LEVEL"] == "DEBUG"


def test_existing_env_wins_by_default(monkeypatch: pytest.MonkeyPatch, fake_boto3) -> None:
    fake_boto3(_FakeClient(payload=json.dumps({"LOG_LEVEL": "DEBUG"})))
    monkeypatch.setenv(SECRETS_ID_VAR, "argus-backend/config")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    assert load_aws_secrets() == []

    import os

    assert os.environ["LOG_LEVEL"] == "WARNING"


def test_override_flag_replaces_existing(monkeypatch: pytest.MonkeyPatch, fake_boto3) -> None:
    fake_boto3(_FakeClient(payload=json.dumps({"LOG_LEVEL": "DEBUG"})))
    monkeypatch.setenv(SECRETS_ID_VAR, "argus-backend/config")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    assert load_aws_secrets(override=True) == ["LOG_LEVEL"]

    import os

    assert os.environ["LOG_LEVEL"] == "DEBUG"


def test_null_values_are_skipped(monkeypatch: pytest.MonkeyPatch, fake_boto3) -> None:
    fake_boto3(_FakeClient(payload=json.dumps({"OPENROUTER_APP_URL": None, "LOG_LEVEL": "INFO"})))
    monkeypatch.setenv(SECRETS_ID_VAR, "argus-backend/config")
    monkeypatch.delenv("OPENROUTER_APP_URL", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    assert load_aws_secrets() == ["LOG_LEVEL"]

    import os

    assert "OPENROUTER_APP_URL" not in os.environ


def test_invalid_json_raises(monkeypatch: pytest.MonkeyPatch, fake_boto3) -> None:
    fake_boto3(_FakeClient(payload="not json"))
    monkeypatch.setenv(SECRETS_ID_VAR, "argus-backend/config")

    with pytest.raises(SecretsLoadError, match="not valid JSON"):
        load_aws_secrets()


def test_non_object_json_raises(monkeypatch: pytest.MonkeyPatch, fake_boto3) -> None:
    fake_boto3(_FakeClient(payload=json.dumps(["a", "b"])))
    monkeypatch.setenv(SECRETS_ID_VAR, "argus-backend/config")

    with pytest.raises(SecretsLoadError, match="must be a JSON object"):
        load_aws_secrets()


def test_missing_secret_string_raises(monkeypatch: pytest.MonkeyPatch, fake_boto3) -> None:
    fake_boto3(_FakeClient(payload=None))
    monkeypatch.setenv(SECRETS_ID_VAR, "argus-backend/config")

    with pytest.raises(SecretsLoadError, match="no SecretString"):
        load_aws_secrets()


def test_fetch_failure_raises(monkeypatch: pytest.MonkeyPatch, fake_boto3) -> None:
    client = fake_boto3(_FakeClient())
    # Pull ClientError from the stub the fixture just installed, so the raised
    # type is the same one load_aws_secrets() will catch.
    from botocore.exceptions import ClientError

    client._error = ClientError("denied")
    monkeypatch.setenv(SECRETS_ID_VAR, "argus-backend/config")

    with pytest.raises(SecretsLoadError, match="could not fetch secret"):
        load_aws_secrets()


@pytest.mark.parametrize(
    ("secret_id", "env_region", "expected"),
    [
        # A full ARN is authoritative — it wins even over a conflicting env var,
        # since the secret only exists in the region named in its own ARN.
        ("arn:aws:secretsmanager:ap-south-1:1234:secret:argus/config-AbCdEf", None, "ap-south-1"),
        (
            "arn:aws:secretsmanager:eu-west-1:1234:secret:argus/config-AbCdEf",
            "us-east-1",
            "eu-west-1",
        ),
        # A bare name has no region, so fall back to the environment.
        ("argus-backend/config", "us-east-1", "us-east-1"),
        ("argus-backend/config", None, None),
    ],
)
def test_region_resolution(
    monkeypatch: pytest.MonkeyPatch,
    secret_id: str,
    env_region: str | None,
    expected: str | None,
) -> None:
    from app.aws_secrets import _resolve_region

    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    if env_region is None:
        monkeypatch.delenv("AWS_REGION", raising=False)
    else:
        monkeypatch.setenv("AWS_REGION", env_region)

    assert _resolve_region(secret_id) == expected
