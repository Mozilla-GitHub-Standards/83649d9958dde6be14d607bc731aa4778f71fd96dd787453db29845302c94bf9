"""Yeelight adapter for Mozilla IoT Gateway."""

from gateway_addon import Device
from yeelight import Bulb
import gateway_addon
import socket
import threading
import time

from .yeelight_property import YeelightProperty
from .util import hsv_to_rgb


_POLL_INTERVAL = 5


class YeelightDevice(Device):
    """Yeelight device type."""

    def __init__(self, adapter, _id, dev_dict):
        """
        Initialize the object.

        adapter -- the Adapter managing this device
        _id -- ID of this device
        dev_dict -- the device object to initialize from
        """
        Device.__init__(self, adapter, _id)
        self._type = ['OnOffSwitch', 'Light']

        self.bulb = Bulb(dev_dict['ip'])
        self.description = dev_dict['model']
        self.name = dev_dict['name']
        self.support = dev_dict['support'].split(' ')

        self.update_properties()

        has_color = False
        has_level = False

        if self.is_color():
            has_color = True
            self._type.append('ColorControl')

            self.properties['color'] = YeelightProperty(
                self,
                'color',
                {
                    '@type': 'ColorProperty',
                    'label': 'Color',
                    'type': 'string',
                },
                self.color())
        elif gateway_addon.API_VERSION >= 2 and self.is_variable_color_temp():
            has_color = True
            self._type.append('ColorControl')

            self.properties['colorTemperature'] = YeelightProperty(
                self,
                'colorTemperature',
                {
                    '@type': 'ColorTemperatureProperty',
                    'label': 'Color Temperature',
                    'type': 'number',
                    'unit': 'kelvin',
                    'min': 1700,
                    'max': 6500,
                },
                self.color_temp())

        if self.is_dimmable():
            self.properties['level'] = YeelightProperty(
                self,
                'level',
                {
                    '@type': 'BrightnessProperty',
                    'label': 'Brightness',
                    'type': 'number',
                    'unit': 'percent',
                    'min': 0,
                    'max': 100,
                },
                self.brightness())

        self.properties['on'] = YeelightProperty(
            self,
            'on',
            {
                '@type': 'OnOffProperty',
                'label': 'On/Off',
                'type': 'boolean',
            },
            self.is_on())

        if has_color and has_level:
            self.type = 'dimmableColorLight'
        elif has_color:
            self.type = 'onOffColorLight'
        elif has_level:
            self.type = 'dimmableLight'
        else:
            self.type = 'onOffLight'

        t = threading.Thread(target=self.poll)
        t.daemon = True
        t.start()

    def poll(self):
        """Poll the device for changes."""
        while True:
            time.sleep(_POLL_INTERVAL)
            self.update_properties()

            for prop in self.properties.values():
                prop.update()

    def update_properties(self):
        """Update the cached properties."""
        try:
            self.properties = self.bulb.get_properties()
        except socket.error:
            pass

    def is_dimmable(self):
        """Determine whether or not the light is dimmable."""
        return 'set_bright' in self.support

    def is_color(self):
        """Determine whether or not the light is color-changing."""
        return 'set_rgb' in self.support and 'set_hsv' in self.support

    def is_variable_color_temp(self):
        """Determine whether or not the light is color-temp-changing."""
        return 'set_ct_abx' in self.support

    def is_on(self):
        """Determine whether or not the light is on."""
        return self.properties['power'] == 'on'

    def color_temp(self):
        """Determine the current color temperature."""
        return int(self.properties['ct'])

    def color(self):
        """Determine the current color of the light."""
        mode = int(self.properties['color_mode'])

        if mode == 1:
            # RGB mode
            return '#{:06X}'.format(int(self.properties['rgb']))
        elif mode == 3:
            # HSV mode
            return hsv_to_rgb(int(self.properties['hue']),
                              int(self.properties['sat']),
                              int(self.properties['bright']))
        else:
            # Color temperature mode
            return '#000000'

    def brightness(self):
        """Determine the current brightness of the light."""
        return int(self.properties['bright'])