"""Durable automatic stress checks; processed by the existing Python worker."""
from django.db import transaction
from . import models as m
from .validation import PRESETS


def preset_results(run):
    results = {}
    for scenario in run.scenarios.select_related('result').order_by('pk'):
        if scenario.name in PRESETS and scenario.overrides == PRESETS[scenario.name]:
            results[scenario.name] = scenario
    return results


def assess(run, one_at_a_time=False):
    from .services import simulate
    present = preset_results(run)
    for name, overrides in PRESETS.items():
        if name not in present:
            simulate(run.site, run.created_by, run, name, overrides)
            if one_at_a_time:
                break
    return len(preset_results(run)) == len(PRESETS)


def process_next():
    with transaction.atomic():
        job = m.PlanAssessment.objects.filter(status='pending').order_by('pk').first()
        if not job:
            return False
        if not m.PlanAssessment.objects.filter(pk=job.pk, status='pending').update(status='running', error=''):
            return False
    try:
        complete = assess(job.run, one_at_a_time=True)
    except Exception as error:
        job.status, job.error = 'failed', str(error)[:1000]
    else:
        job.status, job.error = 'complete' if complete else 'pending', ''
    job.save(update_fields=['status', 'error', 'updated_at'])
    return True
