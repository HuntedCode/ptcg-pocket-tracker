"""
URL configuration for ptcgp_tracker project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
import tcg_collections.views as views
from tcg_collections.views import DashboardView, CollectionStatsAPI, SetBreakdownAPI, PackPickerAPI

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('accounts/register', views.register, name='register'),
    path('trade/matches/', views.trade_matches, name='trade_matches'),
    path('trade/propose/', views.propose_trades, name='propose_trades'),
    path('trade/detail/<int:match_id>', views.trade_detail, name='trade_detail'),
    path('trade/accept/<int:match_id>/', views.accept_match, name='accept_match'),
    path('trade/reject/<int:match_id>/', views.reject_match, name='reject_match'),
    path('trade/ignore/<int:match_id>/', views.ignore_match, name='ignore_match'),
    path('profile/<uuid:token>/', views.profile, name='profile'),
    path('message/send/<int:receiver_id>/', views.send_message, name='send_message'),
    path('message/inbox/', views.inbox, name='inbox'),
    path('pack/opener/', views.pack_opener, name='pack_opener'),
    path('get_booster_cards/', views.get_booster_cards, name='get_booster_cards'),
    path('collection/', views.collection, name='collection'),
    path('tracker/set/<int:set_id>/', views.tracker, name='tracker'),
    path('wishlist/<uuid:token>/', views.wishlist, name='wishlist'),
    path('toggle_dark_mode/', views.toggle_dark_mode, name='toggle_dark_mode'),

    # Dashboard paths
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('api/collection/stats/', CollectionStatsAPI.as_view(), name='collection_stats_api'),
    path('api/set/breakdown/', SetBreakdownAPI.as_view(), name='set_breakdown_api'),
    path('api/pack/picker/', PackPickerAPI.as_view(), name='pack_picker_api'),

]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
