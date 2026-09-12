"""Small browser check for state selection, required markers and geocoding."""
import os
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get('CHROME_PATH', '/opt/google/chrome/chrome'),
        args=['--no-sandbox'],
    )
    page = browser.new_page(viewport={'width': 1280, 'height': 900})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:5173', wait_until='domcontentloaded')
    page.wait_for_timeout(2_000)
    if page.get_by_label('Password', exact=True).count() == 0:
        raise AssertionError(f'Login did not render. Browser errors: {errors}; body: {page.locator("body").inner_text()}')
    page.get_by_label('Password', exact=True).fill(os.environ.get('JEEVANGRID_DEMO_PASSWORD', 'JeevanGridDemo!26'))
    page.get_by_role('button', name='Sign in', exact=True).click()
    page.get_by_role('link', name='Add site', exact=True).first.click()
    state_search = page.get_by_label('State or union territory', exact=True)
    expect(state_search).to_be_visible(timeout=15_000)
    assert state_search.get_attribute('list') == 'india-state-options'
    assert page.locator('.required-mark').count() >= 6
    page.get_by_label('Search location', exact=True).fill('Ahm')
    matches = page.get_by_role('listbox', name='Location matches')
    expect(matches).to_be_visible(timeout=20_000)
    assert 'ahm' in matches.inner_text().lower()
    # The best match fills coordinates before the user clicks a suggestion.
    expect(page.get_by_label('Latitude', exact=True)).not_to_have_value('')
    expect(page.get_by_label('Longitude', exact=True)).not_to_have_value('')
    matches.get_by_role('option').first.click()
    assert page.get_by_label('Latitude').input_value()
    assert page.get_by_label('Longitude').input_value()
    assert page.get_by_label('Timezone').input_value() == 'Asia/Kolkata'
    print('Location form passed: searchable state/location, prefix suggestions and automatic coordinate fill.')
    browser.close()
