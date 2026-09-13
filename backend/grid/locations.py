import requests
from .validation import fail

def search(query, state=""):
    """Resolve an Indian place name without exposing the browser to a third-party API."""
    query=query.strip();state=state.strip()
    if len(query) < 3: fail('Enter at least three characters of a village, town or district.')
    if len(state) > 100: fail('State or union territory must be at most 100 characters.')
    try:
        response = requests.get(
            'https://geocoding-api.open-meteo.com/v1/search',
            params={'name': query, 'count': 20, 'language': 'en', 'format': 'json', 'countryCode': 'IN'},
            timeout=10,
        )
        response.raise_for_status()
        raw = response.json().get('results', [])
    except (requests.RequestException, ValueError, AttributeError):
        raise LookupError('Location search is temporarily unavailable. Enter coordinates manually.')
    matches = []
    for item in raw:
        # Some Indian GeoNames records omit admin1. Keep the operator-selected
        # state in that case, surface the verification flag, and show district
        # context so the operator can reject a similarly named place.
        admin1 = item.get('admin1')
        if item.get('country_code') != 'IN' or (state and admin1 and admin1.casefold() != state.casefold()):
            continue
        if not all(key in item for key in ('name', 'latitude', 'longitude')):
            continue
        matches.append({
            'id': item.get('id'), 'name': item['name'], 'state': admin1 or state,
            'district': item.get('admin2') or item.get('admin3') or item['name'],
            'latitude': item['latitude'], 'longitude': item['longitude'],
            'timezone': item.get('timezone') or 'Asia/Kolkata',
            'state_verified': bool(admin1),
            'label': ', '.join(filter(None, [item['name'], item.get('admin2'), admin1 or state])),
        })
        if len(matches) == 8: break
    return {'results': matches, 'attribution': 'Open-Meteo geocoding; location data based on GeoNames'}
