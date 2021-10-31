from datetime import timedelta
import logging

from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval, async_track_point_in_utc_time
from homeassistant.util import dt

from .const import AQI_BREAKPOINTS, DISPATCHER_PURPLE_AIR_LOCAL, SCAN_INTERVAL, LOCAL_URL

_LOGGER = logging.getLogger(__name__)


def calc_aqi(value, index):
    if index not in AQI_BREAKPOINTS:
        _LOGGER.debug('calc_aqi requested for unknown type: %s', index)
        return None

    bp = next((bp for bp in AQI_BREAKPOINTS[index] if value >= bp['pm_low'] and value <=
              bp['pm_high']), None)
    if not bp:
        _LOGGER.debug('value %s did not fall in valid range for type %s', value, index)
        return None

    aqi_range = bp['aqi_high'] - bp['aqi_low']
    pm_range = bp['pm_high'] - bp['pm_low']
    c = value - bp['pm_low']
    return round((aqi_range/pm_range) * c + bp['aqi_low'])

def calc_epa_conversion(pm, rh):
    """Applies the EPA calibration to Purple's PM2.5 data.
    We floor it to 0 since the combination of very low pm2.5 concentration
    and very high humidity can lead to negative numbers.
    """
    if pm < 2:
      return pm
    return max(0, 0.534 * pm - 0.0844 * rh + 5.604)

class PurpleAirLocal:
    def __init__(self, hass, session):
        self._hass = hass
        self._session = session
        self._nodes = {}
        self._data = {}
        self._scan_interval = timedelta(seconds=SCAN_INTERVAL)
        self._shutdown_interval = None

    def is_node_registered(self, node_id):
        return node_id in self._data

    def get_property(self, node_id, prop):
        if node_id not in self._data:
            return None

        node = self._data[node_id]
        return node[prop]

    def get_reading(self, node_id, prop):
        readings = self._data[node_id]
        return readings[prop] if prop in readings else None

    def register_node(self, node_id, label, ip):
        if node_id in self._nodes:
            _LOGGER.debug('detected duplicate registration: %s', node_id)
            return

        self._nodes[node_id] = { 'label': label, 'ip': ip }
        _LOGGER.debug('registered new node: %s', node_id)

        if not self._shutdown_interval:
            _LOGGER.debug('starting background poll: %s', self._scan_interval)
            self._shutdown_interval = async_track_time_interval(
                self._hass,
                self._update,
                self._scan_interval
            )

            async_track_point_in_utc_time(
                self._hass,
                self._update,
                dt.utcnow() + timedelta(seconds=5)
            )

    def unregister_node(self, node_id):
        if node_id not in self._nodes:
            _LOGGER.debug('detected non-existent unregistration: %s', node_id)
            return

        del self._nodes[node_id]
        _LOGGER.debug('unregistered node: %s', node_id)

        if not self._nodes and self._shutdown_interval:
            _LOGGER.debug('no more nodes, shutting down interval')
            self._shutdown_interval()
            self._shutdown_interval = None


    async def _fetch_data(self, nodes):
        urls = []

        for node in nodes:
          urls.append(LOCAL_URL.format(ip=self._nodes[node]['ip']))

        _LOGGER.debug('fetch url list: %s', urls)

        results = []
        for url in urls:
            async with self._session.get(url) as response:
                if response.status != 200:
                    _LOGGER.warning('bad API response for %s: %s', url, response.status)

                json = await response.json()
                results.append(json)

        return results


    async def _update(self, now=None):
        nodes = [node_id for node_id in self._nodes]

        results = await self._fetch_data(nodes)

        nodes = {}
        for result in results:
            node_id = result['SensorId']
            readings = {}

            humidity = result['current_humidity']
            temp = result['current_temp_f']
            pressure = result['pressure']

            readings['humidity'] = float(humidity)
            readings['temp_f'] = float(temp)
            readings['pressure'] = float(pressure)

            pm25_atm_a = float(result['pm2_5_atm'])
            pm25_atm_b = float(result['pm2_5_atm_b'])
            pm25_atm = round((pm25_atm_a + pm25_atm_b)/2,1)
            pm25_cf1_a = float(result['pm2_5_cf_1'])
            pm25_cf1_b = float(result['pm2_5_cf_1_b'])
            pm25_cf1 = round((pm25_cf1_a + pm25_cf1_b)/2,1)
            readings['pm2_5_atm'] = pm25_atm

            readings['pm2_5_atm_aqi'] = calc_aqi(pm25_atm, 'pm2_5')
            readings['pm2_5_atm_aqi_epa'] = calc_aqi(calc_epa_conversion(pm25_cf1, humidity), 'pm2_5')

            nodes[node_id] = readings
            _LOGGER.debug('Got readings for %s: %s', node_id, readings)
        self._data = nodes
        async_dispatcher_send(self._hass, DISPATCHER_PURPLE_AIR_LOCAL)
