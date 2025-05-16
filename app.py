from flask import Flask, render_template, request, jsonify
import requests
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

def get_weather_icon(weather_code):
    """Map Open-Meteo weather codes to Weather Icons classes"""
    icon_map = {
        0: 'wi-day-sunny', 1: 'wi-day-sunny-overcast', 2: 'wi-day-cloudy', 3: 'wi-cloudy',
        45: 'wi-fog', 48: 'wi-fog', 51: 'wi-sprinkle', 53: 'wi-sprinkle', 55: 'wi-sprinkle',
        56: 'wi-rain-mix', 57: 'wi-rain-mix', 61: 'wi-rain', 63: 'wi-rain', 65: 'wi-rain',
        66: 'wi-rain-mix', 67: 'wi-rain-mix', 71: 'wi-snow', 73: 'wi-snow', 75: 'wi-snow',
        77: 'wi-snowflake-cold', 80: 'wi-showers', 81: 'wi-showers', 82: 'wi-showers',
        85: 'wi-snow', 86: 'wi-snow', 95: 'wi-thunderstorm', 96: 'wi-thunderstorm',
        99: 'wi-thunderstorm'
    }
    return icon_map.get(weather_code, 'wi-day-sunny')

def validate_api_response(data):
    """Validate the structure of the Open-Meteo API response"""
    required_keys = {
        'current_weather': ['temperature', 'windspeed', 'weathercode'],
        'hourly': ['relativehumidity_2m', 'apparent_temperature', 'surface_pressure', 'uv_index'],
        'daily': ['time', 'weathercode', 'temperature_2m_max', 'temperature_2m_min']
    }

    for category, keys in required_keys.items():
        if category not in data:
            raise ValueError(f"Missing {category} in API response")
        for key in keys:
            if key not in data[category]:
                raise ValueError(f"Missing {key} in {category} data")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_weather', methods=['POST'])
def get_weather():
    city = request.form.get('city')
    if not city:
        return jsonify({'error': 'City name is required'}), 400

    try:
        # Geocoding
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        geo_params = {"name": city, "count": 1, "format": "json"}
        geo_response = requests.get(geo_url, params=geo_params)
        geo_response.raise_for_status()
        geo_data = geo_response.json()
        app.logger.debug(f"Geocoding API response: {geo_data}")

        if not geo_data.get('results'):
            return jsonify({'error': 'City not found'}), 404

        location = geo_data['results'][0]
        lat = location.get('latitude')
        lon = location.get('longitude')
        name = location.get('name', city)

        if lat is None or lon is None:
            return jsonify({'error': 'Invalid geocoding response'}), 500

        # Weather API
        weather_url = "https://api.open-meteo.com/v1/forecast"
        weather_params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": True,
            "hourly": "temperature_2m,relativehumidity_2m,apparent_temperature,surface_pressure,uv_index",
            "daily": "weathercode,temperature_2m_max,temperature_2m_min",
            "timezone": "auto",
            "forecast_days": 5
        }

        weather_response = requests.get(weather_url, params=weather_params)
        weather_response.raise_for_status()
        weather_data = weather_response.json()
        app.logger.debug(f"Weather API response: {weather_data}")

        validate_api_response(weather_data)

        # Process data
        current = weather_data['current_weather']
        hourly = weather_data['hourly']
        daily = weather_data['daily']

        weather_info = {
            'city': name,
            'temperature': current.get('temperature', 'N/A'),
            'description': f"{current.get('temperature', 'N/A')}°C",
            'humidity': hourly['relativehumidity_2m'][0] if hourly['relativehumidity_2m'] else 'N/A',
            'wind_speed': current.get('windspeed', 'N/A'),
            'pressure': hourly['surface_pressure'][0] if hourly['surface_pressure'] else 'N/A',
            'feels_like': hourly['apparent_temperature'][0] if hourly['apparent_temperature'] else 'N/A',
            'uv_index': hourly['uv_index'][0] if hourly['uv_index'] else 'N/A',
            'condition_code': str(current.get('weathercode', 0)),  # Convert to string
            'forecast': []
        }

        weather_info['description'] += f" | {get_weather_icon(int(weather_info['condition_code']))}"

        # Process forecast
        for i in range(min(5, len(daily['time']))):
            try:
                forecast_day = {
                    'date': daily['time'][i],
                    'max_temp': daily['temperature_2m_max'][i],
                    'min_temp': daily['temperature_2m_min'][i],
                    'condition_code': str(daily['weathercode'][i])
                }
                weather_info['forecast'].append(forecast_day)
            except (IndexError, KeyError) as e:
                app.logger.error(f"Error processing forecast day {i}: {str(e)}")
                continue

        return jsonify(weather_info)

    except requests.exceptions.HTTPError as e:
        app.logger.error(f"HTTP error: {str(e)}")
        return jsonify({'error': f"API request failed: {str(e)}"}), 500
    except ValueError as e:
        app.logger.error(f"Data validation error: {str(e)}")
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': "Internal server error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)