"""Opt-in live interpretation benchmark. Never executes a workflow."""
import json,time
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from django.test import override_settings
from grid.assistant.evaluation import CASES,CONTEXT,VERSION
from grid.assistant.provider import interpret,ProviderUnavailable

class Command(BaseCommand):
    help='Evaluate exact intent/input matching against Groq; creates no application records.'
    def add_arguments(self,p):
        p.add_argument('--model',choices=['openai/gpt-oss-120b','openai/gpt-oss-20b'],default=settings.ASSISTANT_MODEL)
        p.add_argument('--output',default=str(settings.BASE_DIR/'.local'/'assistant-evaluation.jsonl'))
        p.add_argument('--limit',type=int,default=0)
        p.add_argument('--delay',type=float,default=15)
    def handle(self,*args,**opts):
        if not settings.GROQ_API_KEY:raise CommandError('GROQ_API_KEY is missing. No live model evaluation was run; no accuracy score is available.')
        output=Path(opts['output']);output.parent.mkdir(parents=True,exist_ok=True)
        existing=[json.loads(l) for l in output.read_text().splitlines() if l.strip()] if output.exists() else []
        records={r['id']:r for r in existing if r['model']==opts['model'] and r['version']==VERSION}
        cases=CASES[:opts['limit']] if opts['limit'] else CASES
        with override_settings(ASSISTANT_MODEL=opts['model']):
            for case in cases:
                if case['id'] in records:continue
                actual=None
                for attempt in range(3):
                    try:actual=interpret(case['text'],CONTEXT);break
                    except ProviderUnavailable as e:
                        if not e.retry_after or attempt==2:raise CommandError(str(e)+' Progress is saved; resume with the same output file.')
                        delay=e.retry_after
                        while delay>0:time.sleep(min(30,delay));delay-=min(30,delay)
                match=actual['workflow']==case['workflow'] and (not case['unambiguous'] or actual['inputs']==case['inputs'])
                record={'version':VERSION,'model':opts['model'],'id':case['id'],'text':case['text'],'expected':case,'actual':actual,'match':match}
                with output.open('a') as f:f.write(json.dumps(record)+'\n')
                records[case['id']]=record;self.stdout.write(case['id']+(' PASS' if match else ' FAIL'))
                time.sleep(max(0,min(30,opts['delay'])))
        scored=[records[c['id']] for c in CASES if c['unambiguous'] and c['id'] in records]
        accuracy=sum(r['match'] for r in scored)/len(scored) if scored else 0
        complete=len(records)==len(CASES)
        safe=all(records[c['id']]['match'] for c in CASES if not c['unambiguous'] and c['id'] in records)
        self.stdout.write(f'Exact workflow/input matching: {accuracy:.2%}; {len(scored)} unambiguous cases. Full suite complete: {complete}.')
        if not complete or accuracy<.98 or not safe:raise CommandError('Release gate not passed. Inspect failures, fix the interpreter, and use a new evaluation file for a fresh full run.')
        self.stdout.write('Interpretation gate passed. Run backend and browser release suites separately for authorization, execution, and completion-card checks.')
