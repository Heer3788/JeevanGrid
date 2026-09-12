from django.contrib import admin

from .models import (
    BatteryConfig,
    DispatchableLoad,
    DispatchInterval,
    GeneratorConfig,
    LoadInterval,
    LoadProfile,
    OperatorDecision,
    OptimizationRun,
    Organization,
    ScenarioRun,
    Site,
    SiteAssignment,
    SitePolicy,
    SiteReading,
    SolarConfig,
    UserRole,
    WeatherInterval,
    WindConfig,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'state', 'district', 'archived', 'configuration_version', 'created_at')
    list_filter = ('state', 'archived')
    search_fields = ('name', 'state', 'district')
    readonly_fields = ('created_at',)


@admin.register(OptimizationRun)
class OptimizationRunAdmin(admin.ModelAdmin):
    list_display = ('id', 'site', 'mode', 'status', 'configuration_version', 'solve_seconds', 'created_at')
    list_filter = ('status', 'mode', 'site')
    search_fields = ('site__name',)
    readonly_fields = ('created_at',)


@admin.register(ScenarioRun)
class ScenarioRunAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'baseline', 'result')
    search_fields = ('name', 'baseline__site__name')


@admin.register(WeatherInterval)
class WeatherIntervalAdmin(admin.ModelAdmin):
    list_display = ('id', 'site', 'timestamp', 'retrieved_at', 'source')
    list_filter = ('source', 'site')
    search_fields = ('site__name',)


@admin.register(DispatchInterval)
class DispatchIntervalAdmin(admin.ModelAdmin):
    list_display = ('id', 'run', 'timestamp')
    list_filter = ('run__site',)


@admin.register(LoadInterval)
class LoadIntervalAdmin(admin.ModelAdmin):
    list_display = ('id', 'profile', 'timestamp', 'critical_kw', 'normal_kw', 'flexible_kw')


@admin.register(SiteReading)
class SiteReadingAdmin(admin.ModelAdmin):
    list_display = ('id', 'site', 'timestamp', 'provenance', 'created_by')
    list_filter = ('provenance', 'site')


@admin.register(OperatorDecision)
class OperatorDecisionAdmin(admin.ModelAdmin):
    list_display = ('id', 'run', 'user', 'decision', 'created_at')
    list_filter = ('decision',)


admin.site.register([
    UserRole,
    SiteAssignment,
    SolarConfig,
    WindConfig,
    BatteryConfig,
    GeneratorConfig,
    SitePolicy,
    LoadProfile,
    DispatchableLoad,
])

admin.site.site_header = 'JeevanGrid data administration'
admin.site.site_title = 'JeevanGrid Admin'
admin.site.index_title = 'Sites, configurations and optimization data'
