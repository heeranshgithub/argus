"""Load configuration from AWS Secrets Manager into the process environment.

Deployment (App Runner) keeps every secret in a single Secrets Manager entry
holding a flat JSON object of ``ENV_VAR -> value``. Pointing ``AWS_SECRETS_ID``
at that secret is what turns this module on; without it nothing here runs and
the app keeps reading a local ``.env`` exactly as it does in development.

The values land in ``os.environ`` rather than in :class:`~app.config.Settings`
directly, so ``Settings`` stays a plain pydantic-settings model with no cloud
dependency and no separate code path to keep in sync.
"""

import json
import os

from app.logging_config import get_logger

log = get_logger("aws_secrets")

#: Env var naming the secret (name or full ARN) to load. Unset -> no-op.
SECRETS_ID_VAR = "AWS_SECRETS_ID"


class SecretsLoadError(RuntimeError):
    """Raised when a requested secret cannot be fetched or parsed."""


def _resolve_region(secret_id: str) -> str | None:
    """Determine the region for the Secrets Manager client.

    boto3 needs an explicit region to build an endpoint and does *not* infer one
    from an ARN passed as ``SecretId``. Whether a given runtime exports
    ``AWS_REGION`` into the container is not something we want to depend on, so
    when a full ARN is configured we read the region straight out of it. Falls
    back to the standard env vars, then to ``None`` (letting boto3's own config
    chain decide) for a bare secret name.

    ARN shape: ``arn:aws:secretsmanager:<region>:<account>:secret:<name>``.
    """
    if secret_id.startswith("arn:"):
        parts = secret_id.split(":")
        if len(parts) > 3 and parts[3]:
            return parts[3]
    return os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")


def load_aws_secrets(*, override: bool = False) -> list[str]:
    """Merge the JSON secret named by ``AWS_SECRETS_ID`` into ``os.environ``.

    Returns the list of env var names that were set, so callers can log the
    keys (never the values). Returns an empty list when ``AWS_SECRETS_ID`` is
    unset — the normal local-development case.

    Existing environment variables win by default: App Runner's own
    ``RuntimeEnvironmentVariables`` and anything exported by an operator are
    treated as deliberate per-deployment overrides of the stored secret. Pass
    ``override=True`` to invert that.

    Raises:
        SecretsLoadError: if the secret is requested but cannot be fetched,
            decoded, or parsed. Opting in makes the secret load-bearing, so a
            failure here must stop startup rather than leave the service
            running against half a configuration.
    """
    secret_id = os.environ.get(SECRETS_ID_VAR, "").strip()
    if not secret_id:
        return []

    # Imported lazily so boto3 is only needed where secrets are actually used;
    # tests and local runs never pay the import cost.
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise SecretsLoadError(
            f"{SECRETS_ID_VAR} is set but boto3 is not installed"
        ) from exc

    region = _resolve_region(secret_id)
    client = boto3.client("secretsmanager", region_name=region)

    try:
        response = client.get_secret_value(SecretId=secret_id)
    except (BotoCoreError, ClientError) as exc:
        raise SecretsLoadError(f"could not fetch secret {secret_id!r}: {exc}") from exc

    raw = response.get("SecretString")
    if raw is None:
        # Binary secrets are not a shape we write; treat as a config error.
        raise SecretsLoadError(f"secret {secret_id!r} has no SecretString")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SecretsLoadError(f"secret {secret_id!r} is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise SecretsLoadError(
            f"secret {secret_id!r} must be a JSON object, got {type(payload).__name__}"
        )

    applied: list[str] = []
    for key, value in payload.items():
        if value is None:
            continue
        if not override and key in os.environ:
            continue
        os.environ[key] = str(value)
        applied.append(key)

    # Keys only — values are secrets and must never reach the logs.
    log.info("aws_secrets_loaded", secret_id=secret_id, keys=sorted(applied))
    return applied
