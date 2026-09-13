import hashlib
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from .. import models as m
from ..access import role,site_for
from ..validation import fail
from .catalog import public_catalog,CATALOG
from .engine import scope,TERMINAL
from .verify import verify_receipt,require
from ..reports import digest


def feature():
    if not settings.ASSISTANT_ENABLED:raise PermissionDenied('The assistant is disabled in application settings.')

def conversation_for(user,pk):
    feature();c=get_object_or_404(m.Conversation,pk=pk,owner=user,organization=role(user).organization)
    if c.site_id:site_for(user,c.site_id)
    # Revocation invalidates access to an earlier organization conversation containing that site.
    for job in c.workflows.all():scope(job)
    return c

def serialize(job):
    scope(job);steps=list(job.steps.all());status=job.status;error=job.error
    try:
        for step in steps:verify_receipt(step.receipt)
        if steps and steps[-1].receipt.get('result_hash'):require(digest(job.result)==steps[-1].receipt['result_hash'],'Result card differs from verified evidence.')
    except Exception:
        status='failed';error='Saved evidence failed verification. Completion details are unavailable.'
    return {'sites':list(m.Site.objects.filter(pk__in=job.context.get('site_ids',[])).values('id','name')),'id':job.pk,'message_id':job.message_id,'workflow':job.workflow,'label':CATALOG[job.workflow].label if job.workflow in CATALOG else 'Understanding request',
        'location_choices':job.context.get('location_choices',[]) if job.status=='clarification' else [],'version':job.version,'status':status,'inputs':job.inputs,'question':job.question,'error':error,
        'steps':[{'key':s.key,'label':s.label,'receipt':s.receipt,'verification':s.verification,'created_at':s.created_at} for s in steps],
        'expected_steps':list(CATALOG[job.workflow].steps) if job.workflow in CATALOG else [],
        'result':job.result if status=='succeeded' else {},'completed_changes':len(steps),'created_at':job.created_at,'updated_at':job.updated_at}

@api_view(['GET'])
def configuration(request):
    return Response({'enabled':settings.ASSISTANT_ENABLED,'configured':bool(settings.GROQ_API_KEY),'model':settings.ASSISTANT_MODEL,
        'catalog':public_catalog(request.user) if settings.ASSISTANT_ENABLED else []})

@api_view(['GET','POST'])
def conversations(request):
    feature()
    if request.method=='POST':
        pk=request.data.get('site_id')
        if pk is not None:
            if type(pk) is not int:fail('Invalid site ID.')
            site_for(request.user,pk)
        c=m.Conversation.objects.create(owner=request.user,organization=role(request.user).organization,site_id=pk)
        return Response({'id':c.pk,'site_id':c.site_id,'title':c.title},status=201)
    items=[]
    for c in m.Conversation.objects.filter(owner=request.user,organization=role(request.user).organization).order_by('-updated_at')[:100]:
        try:conversation_for(request.user,c.pk)
        except Exception:continue
        items.append({'id':c.pk,'site_id':c.site_id,'title':c.title,'updated_at':c.updated_at})
    return Response(items)

@api_view(['GET'])
def conversation(request,pk):
    c=conversation_for(request.user,pk)
    return Response({'id':c.pk,'site_id':c.site_id,'title':c.title,'messages':list(c.messages.values('id','role','text','created_at')),'workflows':[serialize(j) for j in c.workflows.all()],
        'attachments':list(m.ChatAttachment.objects.filter(conversation=c).values('id','name','sha256'))})

@api_view(['POST'])
@transaction.atomic
def messages(request,pk):
    c=conversation_for(request.user,pk);text=request.data.get('text','');key=request.data.get('request_key')
    if not isinstance(text,str) or not text.strip() or len(text)>16000:fail('Enter a message between 1 and 16,000 characters.')
    if not isinstance(key,str) or not 8<=len(key)<=80:fail('A stable request key (8–80 characters) is required.')
    workflow=request.data.get('workflow','');inputs=request.data.get('inputs',{})
    if workflow and workflow not in CATALOG:fail('Unsupported workflow ID.')
    if not isinstance(inputs,dict):fail('Inputs must be an object.')
    existing=c.workflows.filter(request_key=key).first()
    if existing:
        if existing.message.text!=text or (existing.context.get('submission_hash') and existing.context['submission_hash']!=digest({'text':text,'workflow':workflow,'inputs':inputs})):fail('This request key already belongs to another request.')
        return Response({'workflow_id':existing.pk,'conversation_id':c.pk,'duplicate':True})
    message=m.ChatMessage.objects.create(conversation=c,role='user',text=text)
    job=m.WorkflowRun.objects.create(conversation=c,message=message,request_key=key,workflow=workflow,inputs=inputs,context={'submission_hash':digest({'text':text,'workflow':workflow,'inputs':inputs})})
    c.title=text[:100];c.save(update_fields=['title','updated_at'])
    return Response({'workflow_id':job.pk,'conversation_id':c.pk},status=202)

@api_view(['POST'])
@transaction.atomic
def attachments(request,pk):
    c=conversation_for(request.user,pk);f=request.FILES.get('file')
    if not f or not f.name.lower().endswith('.csv') or f.size>5*1024*1024:fail('Attach a CSV file under 5 MB.')
    content=f.read()
    try:content.decode('utf-8-sig')
    except UnicodeError:fail('CSV must use UTF-8 encoding.')
    if m.ChatAttachment.objects.filter(conversation=c).count()>=12:fail('This conversation already has 12 attachments. Start another conversation.')
    a=m.ChatAttachment.objects.create(conversation=c,name=f.name[:160],content=content,sha256=hashlib.sha256(content).hexdigest())
    return Response({'id':a.pk,'name':a.name,'sha256':a.sha256},status=201)

@api_view(['GET'])
def workflow(request,pk):
    job=get_object_or_404(m.WorkflowRun,pk=pk,conversation__owner=request.user);conversation_for(request.user,job.conversation_id)
    return Response(serialize(job))

@api_view(['POST'])
@transaction.atomic
def cancel(request,pk):
    job=get_object_or_404(m.WorkflowRun.objects.select_for_update(),pk=pk,conversation__owner=request.user);conversation_for(request.user,job.conversation_id)
    if job.status not in TERMINAL:job.status='cancelled';job.save(update_fields=['status','updated_at'])
    return Response(serialize(job))

@api_view(['POST'])
@transaction.atomic
def clarify(request,pk):
    job=get_object_or_404(m.WorkflowRun.objects.select_for_update(),pk=pk,conversation__owner=request.user);c=conversation_for(request.user,job.conversation_id)
    if job.status!='clarification':fail('This request is not waiting for clarification.')
    text=request.data.get('text','')
    if not isinstance(text,str) or not text.strip() or len(text)>16000:fail('Enter the missing information.')
    message=m.ChatMessage.objects.create(conversation=c,role='user',text=text)
    ids=job.context.get('clarification_ids',[])+[message.pk]
    if len(ids)>10:fail('Start a new request after ten clarification messages.')
    # No workflow has executed before clarification. Reinterpret this request and its answers only.
    if job.steps.exists():fail('Completed steps cannot be reinterpreted. Start a new request.')
    job.context={'clarification_ids':ids,'submission_hash':job.context.get('submission_hash')};job.workflow='';job.inputs={};job.status='queued';job.attempts=0;job.next_attempt_at=None;job.question='';job.save()
    return Response({'workflow_id':job.pk},status=202)


@api_view(['POST'])
@transaction.atomic
def retry(request,pk):
    job=get_object_or_404(m.WorkflowRun.objects.select_for_update(),pk=pk,conversation__owner=request.user)
    conversation_for(request.user,job.conversation_id)
    if job.status!='unavailable':fail('Only a provider or weather availability failure can be retried. Other failures require a new request.')
    job.status='running' if job.context.get('validated') else 'queued';job.attempts=0;job.error='';job.next_attempt_at=None;job.save()
    return Response({'workflow_id':job.pk,'status':job.status},status=202)
