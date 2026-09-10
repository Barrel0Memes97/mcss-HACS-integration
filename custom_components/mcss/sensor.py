
from __future__ import annotations
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for sid in c.data:
        for name, key, unit, icon in [
            ("CPU","cpu","%","mdi:cpu-64-bit"),
            ("Memory used","memoryUsed","MB","mdi:memory"),
            ("Memory limit","memoryLimit","MB","mdi:memory"),
            ("Players online","playersOnline",None,"mdi:account-group"),
            ("Player limit","playerLimit",None,"mdi:account-multiple"),
        ]:
            entities.append(MCSSSensor(c,sid,name,key,unit,icon))
    async_add_entities(entities)

class MCSSSensor(CoordinatorEntity, SensorEntity):
    def __init__(self,c,sid,name,key,unit,icon):
        super().__init__(c)
        self.sid,self.key=sid,key
        self._attr_name=name
        self._attr_unique_id=f"{sid}_{key}".lower()
        self._attr_icon=icon
        self._attr_native_unit_of_measurement=unit

    @property
    def device_info(self):
        s=self.coordinator.data.get(self.sid,{})
        return DeviceInfo(
            identifiers={(DOMAIN,self.sid)},
            name=s.get("name",self.sid),
            manufacturer="MC Server Soft",
            model=s.get("type","Minecraft Server")
        )

    @property
    def native_value(self):
        return self.coordinator.data.get(self.sid,{}).get("stats",{}).get(self.key)
