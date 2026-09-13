"""Shared authorization for HTTP views and workflow jobs."""
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from . import models as m
from .validation import fail

def role(user):
    try: return m.UserRole.objects.select_related('organization').get(user_id=user.pk)
    except m.UserRole.DoesNotExist: raise PermissionDenied('No JeevanGrid role assigned.')


def admin(user):
    if role(user).role != 'admin': raise PermissionDenied('Admin access required.')


def sites_for(user):
    r = role(user)
    q = m.Site.objects.filter(organization=r.organization)
    return q if r.role == 'admin' else q.filter(assignments__user=user).distinct()


def site_for(user, pk, writable=False):
    site = get_object_or_404(sites_for(user), pk=pk)
    if writable and site.archived: fail('This site is archived. Restore it before running or editing it.')
    return site


def run_for(user, pk):
    return get_object_or_404(m.OptimizationRun.objects.filter(site__in=sites_for(user)),pk=pk)
