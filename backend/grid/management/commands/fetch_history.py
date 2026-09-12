from django.core.management.base import BaseCommand
from grid.models import Site
from grid.weather import historical


class Command(BaseCommand):
    help='Download and cache a NASA POWER day for a site.'
    def add_arguments(self,parser):
        parser.add_argument('--site',type=int,required=True)
        parser.add_argument('--date',default='2025-01-15')
    def handle(self,*args,**options):
        result=historical(Site.objects.get(pk=options['site']),options['date'])
        self.stdout.write(f"{result['source']}: {len(result['intervals'])} hourly records; cached={result['cached']}")
