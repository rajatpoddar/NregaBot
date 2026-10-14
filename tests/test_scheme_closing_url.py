import pytest
from src import config


def test_scheme_closing_config_url():
    """Verify SCHEME_CLOSING_CONFIG has the VB-G-RAM-G compwork URL."""
    assert hasattr(config, "SCHEME_CLOSING_CONFIG")
    assert config.SCHEME_CLOSING_CONFIG.get("url") == "https://vbgramgde2.dord.gov.in/vbgramg/compwork.aspx"


def test_scheme_closing_url_rehosting():
    """Verify VB-G-RAM-G scheme closing URL adapts to state-specific hosts."""
    base_url = config.SCHEME_CLOSING_CONFIG["url"]
    
    # Default / empty state stays on vbgramgde2
    assert config.get_state_portal_url(base_url, "") == "https://vbgramgde2.dord.gov.in/vbgramg/compwork.aspx"
    
    # Rajasthan re-hosts to vbgramgde3
    assert config.get_state_portal_url(base_url, "Rajasthan") == "https://vbgramgde3.dord.gov.in/vbgramg/compwork.aspx"
