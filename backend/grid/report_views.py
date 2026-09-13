from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from . import reports,models as m

@api_view(['POST'])
def comparison(request):return Response(reports.comparison(request.user,request.data.get('site_ids'),request.data.get('run_ids')))

def artifact_for(user,pk):
    a=get_object_or_404(m.ReportArtifact,pk=pk,owner=user)
    if not reports.allowed(user,a):raise PermissionDenied('Access to this report has been revoked.')
    return a

def summary(a):return {'id':a.pk,'status':'ready' if len(a.sha256)==64 else 'failed' if a.sha256 else 'queued','format':a.format,'name':a.name,'sha256':a.sha256 if len(a.sha256)==64 else None,'download':f'/api/reports/{a.pk}/download','created_at':a.created_at}

@api_view(['POST'])
def create(request):
    a=reports.create_report(request.user,request.data,request.data.get('format','pdf'))
    return Response(summary(a),status=202)

@api_view(['GET'])
def detail(request,pk):return Response(summary(artifact_for(request.user,pk)))

@api_view(['GET'])
def download(request,pk):
    a=artifact_for(request.user,pk)
    if len(a.sha256)!=64:return Response({'detail':'Report is not ready.'},status=409)
    import hashlib
    if hashlib.sha256(bytes(a.content)).hexdigest()!=a.sha256:return Response({'detail':'Report integrity check failed.'},status=409)
    res=HttpResponse(bytes(a.content),content_type={'pdf':'application/pdf','json':'application/json','csv':'application/zip'}[a.format])
    res['Content-Disposition']='attachment; filename="'+a.name+'"';res['X-Content-Type-Options']='nosniff';return res
