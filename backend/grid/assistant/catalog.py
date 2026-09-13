from dataclasses import dataclass
from django.conf import settings

@dataclass(frozen=True)
class Definition:
    label: str
    steps: tuple
    admin: bool = False
    version: int = 1
    transient_retries: int = 2
    branches: tuple = ('clarify_missing_inputs','record_domain_outcome','stop_on_verification_failure')

    @property
    def roles(self):return ('admin',) if self.admin else ('admin','operator')

    @property
    def required_inputs(self):
        fields=[]
        for step in self.steps:
            fields.extend({'site':['site identity and accepted fields'], 'reading':['site','readings'],
                'weather':['site','weather source','date for historical weather'],
                'scenario_solve':['baseline','overrides'],'compare':['2–5 sites or plans'],
                'replay':['baseline'],'event':['session','event'],'pause':['session'],
                'review':['plan','decision'],'command':['exact command ID','explicit decision'],
                'training':['site','dataset source'],'import':['site','CSV attachment'],
                'report':['evidence selection','format'],'answer':['question']}.get(step,[]))
        return tuple(dict.fromkeys(fields))

CATALOG = {
 'site.create':Definition('Create site',('site',),True),
 'site.update':Definition('Update site configuration',('site',),True),
 'site.assign':Definition('Assign operators',('site',),True),
 'site.archive':Definition('Archive site',('site',),True),
 'site.restore':Definition('Restore site',('site',),True),
 'readings.record':Definition('Record operating readings',('reading',)),
 'demand.import':Definition('Import demand CSV',('import',),True),
 'plan.generate':Definition('Generate and check plan',('weather','solve','plan','checks')),
 'scenario.test':Definition('Test conditions',('scenario_solve','scenario')),
 'compare':Definition('Compare sites or plans',('compare',)),
 'replay.start':Definition('Start simulated replay',('replay','observe')),
 'replay.event':Definition('Change replay conditions',('event','observe')),
 'replay.pause':Definition('Pause simulated replay',('pause',)),
 'plan.review':Definition('Review operating plan',('review',)),
 'command.review':Definition('Review simulated command',('command','observe_command')),
 'forecast.train':Definition('Train forecasting model',('training','model'),True),
 'report.export':Definition('Export evidence',('report','report_ready')),
 'create_and_plan':Definition('Create site and plan',('site','weather','solve','plan','checks'),True),
 'readings_and_plan':Definition('Record readings and replan',('reading','weather','solve','plan','checks')),
 'plan_and_report':Definition('Plan, check and report',('weather','solve','plan','checks','report','report_ready')),
 'test_and_compare':Definition('Test and compare',('scenario_solve','scenario','compare')),
 'compare_and_report':Definition('Compare and report',('compare','report','report_ready')),
 'question':Definition('Ask a question',('answer',)),
}

def enabled(name):
    return name in CATALOG and ('*' in settings.ASSISTANT_WORKFLOWS or name in settings.ASSISTANT_WORKFLOWS)

def public_catalog(user):
    from ..access import role
    return [{'id':k,'label':v.label,'steps':list(v.steps),'version':v.version,'roles':list(v.roles),'required_inputs':list(v.required_inputs),'verification':'Independent persisted-record and numerical checks','transient_retries':v.transient_retries} for k,v in CATALOG.items()
            if enabled(k) and (not v.admin or role(user).role=='admin')]
