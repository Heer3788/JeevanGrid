"""Deterministic browser regression: mocked chat API, no site mutations or model calls."""
import json
import os
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

URL = os.environ.get('JG_TEST_URL', 'http://127.0.0.1:5173')
OUT = Path(__file__).resolve().parent.parent / 'test-results'
OUT.mkdir(exist_ok=True)
DATE = '2026-09-13T02:20:00Z'
MARKDOWN = '''### Battery SOC

**SOC** means the energy stored in a battery, expressed as a percentage.

| Setting | Meaning |
| --- | --- |
| Minimum SOC | A hard lower limit |
| Reserve | An operating target |

1. Charge with available renewables.
2. Keep the battery within its limits.

<script>window.chatInjected = true</script>

[Unsafe link](javascript:alert(1))
'''


def conversation(pk, question, status='succeeded', answer=MARKDOWN):
    job = {'id': pk, 'message_id': pk, 'status': status, 'workflow': 'question',
           'label': 'Ask a question', 'sites': [], 'inputs': {}, 'question': '', 'error': '',
           'steps': [], 'expected_steps': ['answer'], 'completed_changes': 0,
           'created_at': DATE, 'updated_at': DATE,
           'result': {'kind': 'answer', 'text': answer, 'general': True, 'evidence': []} if status == 'succeeded' else {}}
    return {'id': pk, 'site_id': None, 'title': question, 'updated_at': DATE,
            'messages': [{'id': pk, 'role': 'user', 'text': question, 'created_at': DATE}],
            'workflows': [job], 'attachments': []}


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=os.environ.get('CHROME_PATH', '/opt/google/chrome/chrome'), headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    page.add_init_script("sessionStorage.setItem('jg-access','test');sessionStorage.setItem('jg-refresh','test');")
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    chats = {1: conversation(1, 'Explain operating reserve and minimum SOC.'), 2: conversation(2, 'Earlier pending request', 'queued')}
    held = []
    control = {'delay_load': None, 'delay_send': False}
    submissions = []

    def respond(route, value, status=200):
        route.fulfill(status=status, content_type='application/json', body=json.dumps(value))

    def api(route):
        path = urlparse(route.request.url).path.removeprefix('/api')
        method = route.request.method
        body = route.request.post_data_json if method == 'POST' and 'application/json' in route.request.headers.get('content-type', '') else {}
        if path == '/auth/me':
            return respond(route, {'id': 1, 'name': 'Demo administrator', 'email': 'chat-test@local', 'role': 'admin', 'organization': 'Chat test'})
        if path == '/assistant/config':
            return respond(route, {'enabled': True, 'configured': True, 'catalog': []})
        if path == '/sites':
            return respond(route, [])
        if path == '/assistant/conversations':
            if method == 'POST':
                pk = max(chats) + 1
                chats[pk] = {'id': pk, 'site_id': body.get('site_id'), 'title': 'New chat', 'updated_at': DATE, 'messages': [], 'workflows': [], 'attachments': []}
                return respond(route, chats[pk], 201)
            return respond(route, [{'id': c['id'], 'title': c['title'], 'site_id': c['site_id'], 'updated_at': DATE} for c in chats.values()])
        if path.startswith('/assistant/conversations/'):
            parts = path.split('/')
            pk = int(parts[3])
            if len(parts) == 4:
                if control['delay_load'] == pk:
                    control['delay_load'] = None
                    held.append((route, deepcopy(chats[pk])))
                    return
                return respond(route, chats[pk])
            if parts[4] == 'attachments':
                return respond(route, {'id': 51, 'name': 'load.csv'})
            if parts[4] == 'messages':
                submissions.append({'id': pk, **body})
                chats[pk] = conversation(pk, body['text'], answer='SOC tells you how much energy is stored in the battery.')
                if control['delay_send']:
                    control['delay_send'] = False
                    held.append((route, {'workflow_id': pk, 'conversation_id': pk}))
                    return
                return respond(route, {'workflow_id': pk, 'conversation_id': pk}, 202)
        raise AssertionError('Unexpected API route: ' + method + ' ' + path)

    page.route('**/api/**', api)
    page.goto(URL + '/assistant')
    history = page.get_by_role('complementary', name='Conversation history')
    expect(page.get_by_role('heading', name='How can I help?')).to_be_visible()
    expect(history).to_be_hidden()
    page.screenshot(path=str(OUT / 'chat-minimal-page.png'))
    page.get_by_role('button', name='History', exact=True).click()
    history.get_by_role('button', name='Explain operating reserve', exact=False).click()
    reply = page.get_by_role('article', name='JeevanGrid reply')
    expect(reply).to_be_visible()
    assert '###' not in reply.inner_text() and '**' not in reply.inner_text()
    expect(reply.locator('strong').filter(has_text='SOC').first).to_be_visible()
    expect(reply.get_by_role('table')).to_be_visible()
    expect(reply.locator('script')).to_have_count(0)
    expect(reply.locator('a[href^="javascript:"]')).to_have_count(0)
    assert not page.evaluate('Boolean(window.chatInjected)')
    expect(reply).not_to_contain_text('Verified completion')
    page.screenshot(path=str(OUT / 'chat-readable-answer.png'))

    page.get_by_role('button', name='History', exact=True).click()
    history.get_by_role('button', name='Earlier pending request', exact=False).click()
    expect(page.locator('.workflow-queued')).to_be_visible()
    expect(page.get_by_text('This message is waiting to start.', exact=False)).to_be_visible()
    composer = page.get_by_role('textbox', name='Message JeevanGrid assistant')
    composer.fill('Discard this draft')
    page.locator('input[type=file]').set_input_files({'name': 'load.csv', 'mimeType': 'text/csv', 'buffer': b'timestamp,critical_kw,normal_kw,flexible_kw\n'})
    expect(page.get_by_text('Attached #51:', exact=False)).to_be_visible()
    control['delay_load'] = 2
    page.wait_for_timeout(2300)
    assert held, 'A pending poll must be held to reproduce the original reset race'
    page.get_by_role('button', name='New chat', exact=True).click()
    expect(page.get_by_role('heading', name='How can I help?')).to_be_visible()
    for route, data in held:
        respond(route, data)
    held.clear()
    expect(composer).to_have_value('')
    expect(page.get_by_text('Attached #51:', exact=False)).to_have_count(0)
    expect(page.locator('.workflow-card')).to_have_count(0)
    expect(composer).to_be_focused()
    composer.fill('A question in a fresh conversation')
    page.get_by_role('button', name='Send', exact=True).click()
    expect(page.get_by_role('article', name='JeevanGrid reply')).to_contain_text('SOC tells you')
    assert submissions[-1]['id'] not in (1, 2)
    page.get_by_role('button', name='History', exact=True).click()
    expect(history.get_by_role('button', name='Earlier pending request', exact=False)).to_be_visible()

    # The drawer must also reject a late POST response, even when its component stays mounted.
    page.goto(URL + '/sites')
    page.get_by_role('button', name='Open JeevanGrid assistant').click()
    drawer = page.get_by_role('dialog', name='JeevanGrid assistant', exact=True)
    drawer.get_by_role('button', name='New chat', exact=True).click()
    control['delay_send'] = True
    drawer.get_by_role('textbox', name='Message JeevanGrid assistant').fill('Send into the old drawer chat')
    drawer.get_by_role('button', name='Send', exact=True).click()
    expect(drawer.get_by_role('button', name='Sending…', exact=True)).to_be_visible()
    page.wait_for_timeout(300)
    assert held
    drawer.get_by_role('button', name='New chat', exact=True).click()
    for route, data in held:
        respond(route, data)
    held.clear()
    expect(drawer.get_by_role('heading', name='How can I help?')).to_be_visible()
    expect(drawer.locator('.chat-user')).to_have_count(0)
    assert page.evaluate("sessionStorage.getItem('jg-conversation-chat-test@local-organization')") is None
    drawer.get_by_role('textbox', name='Message JeevanGrid assistant').fill('New drawer question')
    drawer.get_by_role('button', name='Send', exact=True).click()
    expect(drawer.get_by_role('article', name='JeevanGrid reply')).to_be_visible()
    assert submissions[-1]['id'] != submissions[-2]['id']
    page.keyboard.press('Escape')
    page.get_by_role('button', name='Open JeevanGrid assistant').click()
    expect(drawer.get_by_text('New drawer question', exact=True)).to_be_visible()
    page.set_viewport_size({'width': 390, 'height': 844})
    expect(drawer.get_by_role('button', name='New chat', exact=True)).to_be_visible()
    expect(drawer.get_by_role('button', name='Send', exact=True)).to_be_visible()
    assert drawer.evaluate('(el) => el.scrollWidth <= el.clientWidth + 1')
    page.screenshot(path=str(OUT / 'chat-mobile.png'))
    drawer.get_by_role('button', name='New chat', exact=True).click()
    expect(drawer.get_by_role('heading', name='How can I help?')).to_be_visible()
    page.screenshot(path=str(OUT / 'chat-minimal-drawer.png'))
    drawer.get_by_role('link', name='History', exact=True).click()
    expect(page.get_by_role('complementary', name='Conversation history')).to_be_visible()
    assert not errors, errors
    print('PASS: readable/safe replies, fresh-chat polling and POST races, cleared draft/attachment, preserved history, drawer restoration, and mobile controls. API fixtures only.')
    browser.close()
