"""Chat failures must be explicit, and a fresh conversation must be isolated."""
from unittest.mock import Mock, patch
import pytest
from django.test import override_settings
from grid import models as m
from grid.assistant import engine, provider
from grid.tests.test_api import setup
from grid.tests.test_assistant import job_for

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('content,reason', [(None, 'stop'), ('', 'stop'), ('  ', 'stop'), ('Half an answer', 'length')])
def test_empty_or_truncated_provider_answer_is_not_a_success(content, reason):
    response = Mock(ok=True, status_code=200)
    response.json.return_value = {'choices': [{'message': {'content': content}, 'finish_reason': reason}]}
    with override_settings(GROQ_API_KEY='test-only'), patch('grid.assistant.provider.requests.post', return_value=response):
        with pytest.raises(provider.ProviderUnavailable):
            provider.completion([{'role': 'user', 'content': 'Explain SOC'}])


def test_general_explanation_has_product_context_and_short_answer_guidance():
    with patch('grid.assistant.provider.completion', return_value='SOC is battery charge.') as complete:
        assert provider.explain('Explain SOC', [], general=True) == 'SOC is battery charge.'
    messages = complete.call_args.args[0]
    prompt = messages[0]['content']
    assert 'under 120 words' in prompt and 'no Markdown headings' in prompt
    assert 'No site records were retrieved' in prompt
    assert 'Minimum SOC is a hard modeled safety limit' in prompt
    assert 'Terminal SOC' in prompt and 'Do not invent site values' in prompt


def test_worker_claim_visible_during_interpretation_and_cancel_respected(setup):
    _, users, _ = setup
    job = job_for(users['admin'], '', {})
    def interpret(*args):
        assert m.WorkflowRun.objects.get(pk=job.pk).status == 'running'
        m.WorkflowRun.objects.filter(pk=job.pk).update(status='cancelled')
        return {'workflow': 'question', 'inputs': {}, 'question_kind': 'general', 'arguments': []}
    with patch('grid.assistant.provider.interpret', side_effect=interpret):
        engine.tick(job)
    job.refresh_from_db()
    assert job.status == 'cancelled' and not job.steps.exists()


def test_new_chat_keeps_history_without_inheriting_context(setup):
    client, users, sites = setup
    old = job_for(users['admin'], 'question', {'question': 'Old question'}, site=sites[0])
    old.status = 'succeeded'; old.context = {'site_ids': [sites[0].pk]}; old.save()
    created = client.post('/api/assistant/conversations', {'site_id': sites[1].pk}, format='json')
    assert created.status_code == 201
    new_id = created.data['id']
    submitted = client.post('/api/assistant/conversations/' + str(new_id) + '/messages', {
        'text': 'Explain SOC', 'request_key': 'fresh-chat-12345',
    }, format='json')
    new = m.WorkflowRun.objects.get(pk=submitted.data['workflow_id'])
    context = engine.context_for(new)
    assert context['previous_result'] is None
    assert context['site_scope'] == sites[1].pk
    assert {row['id'] for row in context['sites']} == {sites[1].pk}
    history = client.get('/api/assistant/conversations').data
    assert {old.conversation_id, new_id}.issubset({row['id'] for row in history})
    assert m.WorkflowRun.objects.get(pk=old.pk).status == 'succeeded'
