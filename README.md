A fork from https://github.com/bhaggs/home-assistant-purpleair using
sensors locally instead of via the api.

A quick and dirty integration for Home Assistant to integrate PurpleAir
air quality sensors. This will create an `air_quality` sensor with the
relevant data and create an additional AQI `sensor` for ease-of-use.

Simply copy the `/purpleair` directory in to your config's
`custom_components` directory (you may need to create it), restart Home
Assistant, and add the integration via the UI (it's simple!).

To integrate your sensor, find it on your local network and assign a static
local ip (use a DHCP reservation for example): Then

1. Go to Home Assistant and go to the Integrations Page.
2. Add the PurpleAir integration.
3. Enter the ip address and finish.

You'll have two entities added: an `air_quality` entity and a `sensor`
entity. The air quality fills out all available values via the state
dictionary, and the sensor entity is simply the calculated AQI value,
for ease of use. (The AQI also shows up as an attribute on the air
quality entity as well).

Sensor data on PurpleAir is only updated every two minutes, and to be
nice, this integration will batch its updates every five minutes. If you
add multiple sensors, the new sensors will take up to five minutes to
get their data, as to not flood their free service with requests.

This component is licensed under the MIT license, so feel free to copy,
enhance, and redistribute as you see fit.

### Notes
This was only tested for outdoor sensors. 

## Releases

### 1.0.0

Initial release
