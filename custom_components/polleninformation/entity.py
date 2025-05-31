# custom_components/polleninformation/entity.py
"""Bas-Entity-klass för polleninformation.at."""
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, NAME, VERSION


class PollenEntity(CoordinatorEntity):
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator)
        self.config_entry = config_entry
        # DeviceInfo identifier med DOMAIN och entry_id
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=f"{NAME} {config_entry.entry_id}",
            model=VERSION,
        )

    @property
    def unique_id(self):
        """Returnera en unik ID för sensorn."""
        return f"{self.config_entry.entry_id}-{self.name}"

    @property
    def add_state_attributes(self):
        """Gemensamma attribut: update_success och last_updated."""
        return {
            "update_success": self.coordinator.last_update_success,
            "last_updated": (
                self.coordinator.last_updated.strftime("%Y-%m-%d %H:%M:%S")
                if self.coordinator.last_updated
                else None
            ),
        }
