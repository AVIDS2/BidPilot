"""Provider registry — resolves user provider configurations from the database.

Reads the provider_config table to find the active configuration for a user,
returning connection parameters for the appropriate LLM/embedding adapter.
"""

from dataclasses import dataclass
import logging
from app.db import SessionLocal
from app.models import ProviderConfig
from app.security.secrets import decrypt_secret

logger = logging.getLogger(__name__)


@dataclass
class ProviderParams:
    provider_type: str  # "openai" or "anthropic"
    api_key: str
    api_url: str | None
    model: str


def get_active_provider(user_id: str, provider_type: str = "openai") -> ProviderParams | None:
    """Get the active provider configuration for a user.

    Args:
        user_id: The user's UUID.
        provider_type: "openai" or "anthropic".

    Returns:
        ProviderParams if an active config exists, None otherwise.
    """
    db = SessionLocal()
    try:
        config = (
            db.query(ProviderConfig)
            .filter(
                ProviderConfig.user_id == user_id,
                ProviderConfig.provider_type == provider_type,
                ProviderConfig.is_active == True,
            )
            .first()
        )
        if config is None:
            # Fallback: any config of this type (take the most recent)
            config = (
                db.query(ProviderConfig)
                .filter(
                    ProviderConfig.user_id == user_id,
                    ProviderConfig.provider_type == provider_type,
                )
                .order_by(ProviderConfig.created_at.desc())
                .first()
            )
        if config is None:
            return None

        return ProviderParams(
            provider_type=config.provider_type,
            api_key=decrypt_secret(config.api_key),
            api_url=config.api_url,
            model=config.model,
        )
    except Exception as exc:
        logger.warning("Failed to resolve provider config for user %s: %s", user_id, exc)
        return None
    finally:
        db.close()


def get_provider_by_id(config_id: str) -> ProviderParams | None:
    """Get a provider configuration by its ID.

    Args:
        config_id: The ProviderConfig UUID.

    Returns:
        ProviderParams if found, None otherwise.
    """
    db = SessionLocal()
    try:
        config = db.query(ProviderConfig).filter(ProviderConfig.id == config_id).first()
        if config is None:
            return None
        return ProviderParams(
            provider_type=config.provider_type,
            api_key=decrypt_secret(config.api_key),
            api_url=config.api_url,
            model=config.model,
        )
    except Exception as exc:
        logger.warning("Failed to resolve provider config %s: %s", config_id, exc)
        return None
    finally:
        db.close()
