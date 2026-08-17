from __future__ import annotations

from .logging import get_logger

logger = get_logger()

_tls_configured = False


def configure_tls() -> None:
    global _tls_configured
    if _tls_configured:
        return
    try:
        import truststore

        truststore.inject_into_ssl()
        logger.debug("TLS: using the OS trust store via truststore.")
    except Exception as exc:
        logger.debug("TLS: truststore not active ({}); using default CA bundle.", exc)
    _tls_configured = True


__all__ = ["configure_tls"]
