"""Opt-in live demo acceptance: real API + Groq + workers; creates demo records."""
import json
import time
import uuid
from pathlib import Path
import requests
from django.core.management.base import BaseCommand, CommandError
from rest_framework_simplejwt.tokens import AccessToken
from grid import models as m
from grid.portfolio_seed import SEED_KEY


class Command(BaseCommand):
    help = 'Test real chatbot prompts against a seeded demo site; stores readings, plan, scenario, review, model and report.'

    def add_arguments(self, parser):
        parser.add_argument('--execute', action='store_true', help='Required: acknowledges local demo mutations and Groq API calls.')
        parser.add_argument('--base-url', default='http://127.0.0.1:8000')
        parser.add_argument('--output', default='.local/showcase-verification.json')

    def handle(self, *args, **options):
        if not options['execute']: raise CommandError('Pass --execute to create demo records using the real chatbot.')
        if options['base_url'] not in ['http://127.0.0.1:8000','http://localhost:8000']:
            raise CommandError('This verifier is restricted to the local demo server.')
        site = m.Site.objects.filter(provenance__seed_key=SEED_KEY,provenance__seed_index=3).first()
        if not site: raise CommandError('Run seed_portfolio first.')
        admin = m.UserRole.objects.get(organization=site.organization,user__username='admin@jeevangrid.local').user
        http = requests.Session()
        http.headers['Authorization'] = 'Bearer '+str(AccessToken.for_user(admin))

        def api(method, path, body=None):
            response = http.request(method,options['base_url']+'/api'+path,json=body,timeout=60)
            response.raise_for_status()
            return response.json()

        def counts():
            return {'readings':site.readings.count(),'plans':site.runs.exclude(mode__in=['scenario','live_simulation']).count(),
                    'scenarios':m.ScenarioRun.objects.filter(baseline__site=site).count(),
                    'dispatch_intervals':m.DispatchInterval.objects.filter(run__site=site).count(),
                    'decisions':m.OperatorDecision.objects.filter(run__site=site).count(),
                    'forecast_models':site.forecast_models.count(),
                    'reports':m.ReportArtifact.objects.filter(owner=admin).count()}

        name = site.name
        cases = [
            (f'For {name}, record battery SOC 45%, fuel 20 litres, diesel price 94 INR/L, generator available and off. Event: final-round demonstration.', 'readings.record', 'readings'),
            (f'Generate a 24-hour plan for {name} using simulated weather.', 'plan.generate', 'plans'),
            (f'For {name}, test 50% lower solar availability against its latest plan and compare the results.', 'test_and_compare', 'scenarios'),
            (f'Confirm the latest operating plan for {name}. Reason: reviewed for the final-round demonstration.', 'plan.review', 'decisions'),
            (f'Export the latest operating plan for {name} as a PDF report.', 'report.export', 'reports'),
            (f'Train the demand and solar forecasting models for {name} using simulated training data.', 'forecast.train', 'forecast_models'),
        ]
        results=[]
        output=Path(options['output']); output.parent.mkdir(parents=True,exist_ok=True)
        for prompt,expected,table in cases:
            before=counts(); start=time.monotonic()
            # Limit provider context to this newly generated, non-sensitive demo site.
            # This matches opening the assistant from that site's workspace.
            conversation=api('POST','/assistant/conversations',{'site_id':site.pk})
            submitted=api('POST',f'/assistant/conversations/{conversation["id"]}/messages',
                          {'text':prompt,'request_key':uuid.uuid4().hex})
            job_id=submitted['workflow_id']
            while time.monotonic()-start<180:
                job=m.WorkflowRun.objects.get(pk=job_id)
                if job.status in ['succeeded','failed','unavailable','clarification','cancelled']: break
                time.sleep(2)
            data=api('GET',f'/assistant/workflows/{job_id}')
            after=counts()
            entry={'prompt':prompt,'workflow_id':job_id,'conversation_id':conversation['id'],
                   'workflow':data['workflow'],'status':data['status'],'seconds':round(time.monotonic()-start,2),
                   'before':before,'after':after,'added':{k:after[k]-before[k] for k in before},
                   'receipts':[s['receipt'] for s in data['steps']], 'error':data['error'],'question':data['question']}
            results.append(entry)
            output.write_text(json.dumps({'site_id':site.pk,'site_name':name,'checks':results},indent=2,default=str),encoding='utf-8')
            self.stdout.write(f'{expected}: {entry["status"]} / interpreted {entry["workflow"]}; added {entry["added"]}; {entry["seconds"]}s')
            if data['status']!='succeeded' or data['workflow']!=expected or after[table] != before[table]+1:
                raise CommandError('Showcase check did not pass; inspect the evidence JSON. No results were fabricated.')
        self.stdout.write(self.style.SUCCESS(f'All six real-chat workflows verified. Evidence: {output}'))
