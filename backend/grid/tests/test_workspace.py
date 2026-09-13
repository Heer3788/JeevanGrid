from copy import deepcopy
from unittest.mock import patch
import pytest
from django.core.management import call_command
from grid import models as m, services as svc, live
from grid.assessment import assess, process_next, preset_results
from grid.demo import PLACES, ACCOUNTS, place_configuration
from grid.tests.test_api import setup
from grid.validation import PRESETS, validate_configuration

pytestmark = pytest.mark.django_db


def test_plan_queues_complete_idempotent_assessment(setup):
    _, users, sites = setup
    run = svc.optimize(sites[0], users['admin'])
    assert run.assessment.status == 'pending'
    assert assess(run)
    first = set(run.scenarios.values_list('result_id', flat=True))
    assert len(first) == len(PRESETS)
    assert assess(run)
    assert set(run.scenarios.values_list('result_id', flat=True)) == first
    assert not m.PlanAssessment.objects.filter(run_id__in=first).exists()
    assert svc.reliability(sites[0])['stress_tested']


def test_custom_experiment_does_not_count_as_standard_check(setup):
    _, users, sites = setup
    run = svc.optimize(sites[0], users['admin'])
    svc.simulate(sites[0], users['admin'], run, 'cloudy', {'solar_multiplier': .8})
    assert not preset_results(run)
    assert not svc.reliability(sites[0])['stress_tested']


def test_assessment_failure_retry_and_permissions(setup):
    client, users, sites = setup
    run = svc.optimize(sites[0], users['admin'])
    with patch('grid.assessment.assess', side_effect=RuntimeError('Temporary solver failure')):
        assert process_next()
    run.assessment.refresh_from_db()
    assert run.assessment.status == 'failed'
    response = client.post(f'/api/optimization-runs/{run.pk}/scenarios', {}, format='json')
    assert response.data['status'] == 'failed'
    response = client.post(f'/api/optimization-runs/{run.pk}/scenarios', {'retry': True}, format='json')
    assert response.data['status'] == 'pending'
    client.force_authenticate(users['outsider'])
    assert client.post(f'/api/optimization-runs/{run.pk}/scenarios', {}, format='json').status_code == 404


def test_live_replay_preserves_selected_inputs_and_plan_identity(setup):
    client, users, sites = setup
    baseline = svc.optimize(sites[0], users['admin'])
    snapshot = deepcopy(baseline.snapshot)
    response = client.post(f'/api/sites/{sites[0].pk}/live', {'baseline_id': baseline.pk,
        'options': {'speed': 1, 'conservative': False, 'use_ml': False}}, format='json')
    assert response.status_code == 200
    session = m.LiveSession.objects.get(pk=response.data['session']['id'])
    assert session.snapshot['inputs'] == snapshot['inputs']
    assert session.snapshot['weather'] == snapshot['weather']
    assert session.snapshot['baseline_run_id'] == baseline.pk
    assert svc.latest_plan(sites[0]).pk == baseline.pk
    assert svc.site_summary(sites[0])['latest_run']['id'] == baseline.pk
    other = svc.optimize(sites[1], users['admin'])
    client.post(f'/api/sites/{sites[0].pk}/live', {'action':'pause'}, format='json')
    assert client.post(f'/api/sites/{sites[0].pk}/live', {'baseline_id':other.pk}, format='json').status_code == 400
    baseline.refresh_from_db()
    assert baseline.snapshot == snapshot


def test_seed_preserves_accounts_and_adds_sourced_sites():
    call_command('seed_demo')
    names = [p['name'] for p in PLACES]
    assert m.Site.objects.filter(name__in=names).count() == len(PLACES)
    from django.contrib.auth import get_user_model
    user = get_user_model().objects.get(username=ACCOUNTS[0]['email'])
    user.set_password('changed-by-user'); user.save()
    ids = set(m.Site.objects.values_list('pk', flat=True))
    call_command('seed_demo')
    user.refresh_from_db()
    assert user.check_password('changed-by-user')
    assert set(m.Site.objects.values_list('pk', flat=True)) == ids
    for place in PLACES:
        validate_configuration(place_configuration(place))
        site = m.Site.objects.get(name=place['name'])
        assert site.provenance['source_url'].startswith('https://')
        assert site.assignments.exists()


def test_executing_command_survives_rolling_replan(setup):
    _, users, sites = setup
    session = live.start(sites[0], users['admin'], {'speed':30})
    live.advance(session.pk)
    session.refresh_from_db()
    command = session.commands.filter(status='proposed').first()
    command.status='executing'; command.save(update_fields=['status'])
    live.replan(session.pk, 'Five-minute update')
    command.refresh_from_db()
    assert command.status == 'executing'


def test_demo_catalog_respects_custom_password_and_production_mode(settings):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    settings.DEBUG = True
    call_command('seed_demo')
    user = get_user_model().objects.get(username=ACCOUNTS[0]['email'])
    user.set_password('private-custom-password'); user.save()
    client = APIClient()
    response = client.get('/api/auth/demo-accounts')
    account = next(a for a in response.data if a['email'] == user.email)
    assert account['quick_login'] is False
    assert 'private-custom-password' not in response.content.decode()
    assert all('password' not in a for a in response.data)
    settings.DEBUG = False
    assert client.get('/api/auth/demo-accounts').data == []
