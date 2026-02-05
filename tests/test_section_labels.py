from homeassistant.helpers import selector

import custom_components.emergency_stop.config_flow as config_flow


def test_section_label_uses_available_selector():
    section = config_flow._section_label("Email provider")
    assert len(section) == 1
    value = next(iter(section.values()))
    if config_flow._SECTION_SELECTOR and config_flow._SECTION_SELECTOR_CONFIG:
        assert isinstance(value, config_flow._SECTION_SELECTOR)
        assert value.config.get("label") == "Email provider"
    else:
        assert isinstance(value, selector.ConstantSelector)
        assert value.config.get("label") == "Email provider"
