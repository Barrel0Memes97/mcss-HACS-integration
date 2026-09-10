
from __future__ import annotations
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN

ACTIONS={"Start":2,"Stop":1,"Restart":4,"Kill":3}

async def async_setup_entry(hass,entry,async_add_entities):
    c=hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [MCSSButton(c,sid,name,action)
         for sid in c.data for name,action in ACTIONS.items()]
    )

class MCSSButton(CoordinatorEntity,ButtonEntity):
    def __init__(self,c,sid,name,action):
        super().__init__(c)
        self.sid,self.action=sid,action
        self._attr_name=name
        self._attr_unique_id=f"{sid}_{name}".lower()
        self._attr_icon={
            "Start":"mdi:play-circle","Stop":"mdi:stop-circle",
            "Restart":"mdi:restart","Kill":"mdi:skull-crossbones"
        }[name]

    @property
    def device_info(self):
        s=self.coordinator.data.get(self.sid,{})
        return DeviceInfo(
            identifiers={(DOMAIN,self.sid)},
            name=s.get("name",self.sid),
            manufacturer="MC Server Soft",
            model=s.get("type","Minecraft Server")
        )

    async def async_press(self):
        await self.coordinator.action(self.sid,self.action)
