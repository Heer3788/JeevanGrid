import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from grid import models as m, services as svc
from grid.defaults import default_configuration, STUDY


class Command(BaseCommand):
    help = 'Create local demo users and three study-informed/simulated sites; never overwrite existing sites.'

    def add_arguments(self, parser):
        parser.add_argument('--with-runs', action='store_true')

    def handle(self,*args,**options):
        org,_=m.Organization.objects.get_or_create(name='JeevanGrid Demo Agency')
        users={}
        password=os.environ.get('JEEVANGRID_DEMO_PASSWORD','JeevanGridDemo!26')
        for kind in ['admin','operator']:
            email=f'{kind}@jeevangrid.local'
            user,new=get_user_model().objects.get_or_create(username=email,defaults={'email':email,'first_name':kind.title()})
            if new:
                user.set_password(password); user.save()
            m.UserRole.objects.get_or_create(user=user,defaults={'organization':org,'role':kind})
            users[kind]=user
        for i,name in enumerate(['Leporiang · study reference','Leporiang area · compact demo','Leporiang area · constrained demo']):
            if m.Site.objects.filter(organization=org,name=name).exists(): continue
            c=default_configuration()
            provenance={'site':'study' if i==0 else 'simulated','study_url':STUDY,
                'note':'Approximate village coordinates. Study reports surveyed totals and modelled capacities, not an operating installation. Operating parameters, flexible loads, critical split and prices are assumptions. No live telemetry.',
                'study_fields':['daily demand 876.41 kWh','101 kW peak','600 kW PV','100 kW wind','200 kW diesel','3000 kWh battery'] if i==0 else [],
                'assumed_fields':['all efficiencies','SOC policies','fuel curve','fuel price','battery replacement/throughput','power limits','critical/flexible split','pump schedule']}
            if i:
                for key in ['solar','wind','battery','generator']: c[key]['provenance']='simulated'
                c['solar']['capacity_kw']=100 if i==1 else 40
                c['wind']['capacity_kw']=20 if i==1 else 10
                c['battery'].update(capacity_kwh=300 if i==1 else 120,max_charge_kw=60,max_discharge_kw=60,
                    replacement_cost=3000000 if i==1 else 1200000,lifetime_throughput_kwh=900000 if i==1 else 360000)
                c['generator'].update(capacity_kw=100 if i==1 else 25,min_power_kw=20 if i==1 else 5,fuel_intercept=4 if i==1 else 1)
            site=m.Site.objects.create(organization=org,name=name,provenance=provenance)
            svc.save_configuration(site,c,increment=False)
            if i<2: m.SiteAssignment.objects.create(site=site,user=users['operator'])
            m.SiteReading.objects.create(site=site,timestamp=timezone.now(),provenance='simulated',data={
                'soc_pct':60,'fuel_l':500 if i<2 else 20,'generator_available':True,'generator_on':False,
                'event':'Demo operating state; no physical telemetry.','demand_multiplier':1,'diesel_price':90})
        if options['with_runs']:
            for site in m.Site.objects.filter(organization=org):
                if not site.runs.exists():
                    run=svc.optimize(site,users['admin'],'simulated')
                    self.stdout.write(f'{site.name}: {run.status}, {run.solve_seconds:.3f}s')
        self.stdout.write('Demo ready: admin@jeevangrid.local and operator@jeevangrid.local. Password from JEEVANGRID_DEMO_PASSWORD, default JeevanGridDemo!26.')
