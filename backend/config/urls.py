from django.contrib import admin
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from grid import views as v

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/optimization-runs/<int:pk>/analysis', v.run_analysis),
    path('api/optimization-runs/<int:pk>/scenarios', v.run_scenarios),
    path('api/auth/login',v.login), path('api/auth/me',v.me), path('api/auth/logout',v.logout),
    path('api/auth/refresh',TokenRefreshView.as_view()), path('api/members',v.members), path('api/defaults',v.defaults),
    path('api/locations/search',v.location_search),
    path('api/sites',v.sites), path('api/sites/<int:pk>',v.site_detail),
    path('api/sites/<int:pk>/configuration',v.configuration), path('api/sites/<int:pk>/readings',v.readings),
    path('api/sites/<int:pk>/load-profile/import',v.load_import), path('api/sites/<int:pk>/forecast/refresh',v.forecast_refresh),
    path('api/sites/<int:pk>/optimization-runs',v.optimization_runs), path('api/sites/<int:pk>/scenario-runs',v.scenarios),
    path('api/optimization-runs',v.run_list), path('api/optimization-runs/<int:pk>',v.run_detail),
    path('api/optimization-runs/<int:pk>/decision',v.decision),
    path('api/portfolio/reliability',v.portfolio), path('api/portfolio/resilience-runs',v.resilience),
]
