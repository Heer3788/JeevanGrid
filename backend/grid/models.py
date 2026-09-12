from django.conf import settings
from django.db import models


class Organization(models.Model):
    name = models.CharField(max_length=160)


class UserRole(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='grid_role')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    role = models.CharField(max_length=16, choices=[('admin', 'Admin'), ('operator', 'Operator')])


class Site(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    name = models.CharField(max_length=160)
    state = models.CharField(max_length=100, default='Arunachal Pradesh')
    district = models.CharField(max_length=100, default='Papum Pare')
    latitude = models.FloatField(default=27.2297)
    longitude = models.FloatField(default=93.3412)
    timezone = models.CharField(max_length=80, default='Asia/Kolkata')
    archived = models.BooleanField(default=False)
    configuration_version = models.PositiveIntegerField(default=1)
    provenance = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class SiteAssignment(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='assignments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['site', 'user'], name='unique_site_operator')]


class ConfigBase(models.Model):
    data = models.JSONField(default=dict)
    class Meta:
        abstract = True


class SolarConfig(ConfigBase):
    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name='solar')


class WindConfig(ConfigBase):
    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name='wind')


class BatteryConfig(ConfigBase):
    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name='battery')


class GeneratorConfig(ConfigBase):
    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name='generator')


class SitePolicy(ConfigBase):
    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name='policy')


class LoadProfile(models.Model):
    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name='load_profile')
    data = models.JSONField(default=dict)
    provenance = models.CharField(max_length=80, default='simulated_from_published_totals')


class LoadInterval(models.Model):
    profile = models.ForeignKey(LoadProfile, on_delete=models.CASCADE, related_name='intervals')
    timestamp = models.DateTimeField()
    critical_kw = models.FloatField()
    normal_kw = models.FloatField()
    flexible_kw = models.FloatField()
    class Meta:
        ordering = ['timestamp']
        constraints = [models.UniqueConstraint(fields=['profile', 'timestamp'], name='unique_load_interval')]


class DispatchableLoad(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='flexible_loads')
    data = models.JSONField(default=dict)


class SiteReading(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='readings')
    timestamp = models.DateTimeField()
    data = models.JSONField(default=dict)
    provenance = models.CharField(max_length=40, default='operator')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    class Meta:
        ordering = ['-timestamp', '-pk']


class WeatherInterval(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='weather')
    timestamp = models.DateTimeField()
    retrieved_at = models.DateTimeField()
    source = models.CharField(max_length=40)
    data = models.JSONField(default=dict)
    class Meta:
        ordering = ['timestamp']


class OptimizationRun(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='runs')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    configuration_version = models.PositiveIntegerField()
    status = models.CharField(max_length=16)
    mode = models.CharField(max_length=24)
    snapshot = models.JSONField(default=dict)
    metrics = models.JSONField(default=dict)
    next_action = models.JSONField(default=dict)
    diagnostics = models.JSONField(default=list)
    solve_seconds = models.FloatField(default=0)
    class Meta:
        ordering = ['-created_at', '-pk']


class DispatchInterval(models.Model):
    run = models.ForeignKey(OptimizationRun, on_delete=models.CASCADE, related_name='intervals')
    timestamp = models.DateTimeField()
    data = models.JSONField(default=dict)
    class Meta:
        ordering = ['timestamp']


class ScenarioRun(models.Model):
    baseline = models.ForeignKey(OptimizationRun, on_delete=models.CASCADE, related_name='scenarios')
    result = models.OneToOneField(OptimizationRun, on_delete=models.CASCADE, related_name='scenario')
    name = models.CharField(max_length=120)
    overrides = models.JSONField(default=dict)


class OperatorDecision(models.Model):
    run = models.ForeignKey(OptimizationRun, on_delete=models.CASCADE, related_name='decisions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    decision = models.CharField(max_length=16, choices=[('confirm', 'Confirm'), ('override', 'Override')])
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
