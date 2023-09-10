"""budget URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
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
from django.contrib import admin
from django.urls import path, re_path
from web import views

urlpatterns = [
    path(r'', views.home, name="home"),
    #path(r'^transaction/', views.transaction_new, name="transaction_new"),    
    re_path(r'account/(?P<tenant_id>[0-9]+)/settings/', views.settings, name="settings"),
    re_path(r'account/(?P<tenant_id>[0-9]+)/sorter/', views.sorter, name="sorter"),
    re_path(r'account/(?P<tenant_id>[0-9]+)/select_tag/', views.select_tag, name="select_tag"),
    re_path(r'account/(?P<tenant_id>[0-9]+)/recordmatcher/(?P<transactionruleset_id>[0-9]+)/', views.recordmatcher, name="recordmatcher"),
    re_path(r'account/(?P<tenant_id>[0-9]+)/recordmatcher/', views.recordmatcher, name="recordmatcher"),
    re_path(r'account/(?P<tenant_id>[0-9]+)/transactionrulesets/auto/', views.transactionrulesets_auto, name="transactionrulesets_auto"),
    re_path(r'account/(?P<tenant_id>[0-9]+)/transactionrulesets/(?P<transactionruleset_id>[0-9]+)/', views.transactionrulesets_list, name="transactionrulesets_list"),
    re_path(r'account/(?P<tenant_id>[0-9]+)/transactionrulesets/', views.transactionrulesets_list, name="transactionrulesets_list"),
    re_path(r'account/(?P<tenant_id>[0-9]+)/transactionruleset/(?P<transactionruleset_id>[0-9]+)/', views.transactionruleset_edit, name="transactionruleset_edit"),
    re_path(r'account/(?P<tenant_id>[0-9]+)/transactionruleset/(?P<rule>.+)/', views.transactionruleset_edit, name="transactionruleset_create"),        
    re_path(r'account/(?P<tenant_id>[0-9]+)/transactionruleset/', views.transactionruleset_edit, name="transactionruleset_create"),    
    
    # re_path(r'account/(?P<tenant_id>[0-9]+)/rulematches/', views.rulematches, name="rulematches"),
    # re_path(r'account/(?P<tenant_id>[0-9]+)/model/(?P<model_id>[0-9]+)/', views.model_edit, name="model_edit"),    
    # re_path(r'account/(?P<tenant_id>[0-9]+)/model/', views.model_edit, name="model_edit"),
    re_path(r'account/(?P<tenant_id>[0-9]+)/models/', views.model_list, name="model_list"),    
    re_path(r'account/(?P<tenant_id>[0-9]+)/files/reprocess/', views.reprocess_files, name="reprocess_files"),
    re_path(r'account/(?P<tenant_id>[0-9]+)/files/', views.files, name="files"),        
    re_path(r'account/(?P<tenant_id>[0-9]+)/filters/', views.filters, name="filters"),        
    re_path(r'account/(?P<tenant_id>[0-9]+)/record/(?P<record_id>[0-9]+)/type', views.update_record_type, name="update_record_type"),        
    re_path(r'account/(?P<tenant_id>[0-9]+)/records/delete/(?P<uploadedfile_id>[0-9]+)/', views.delete_uploadedfile, name="delete_uploadedfile"),
    re_path(r'account/(?P<tenant_id>[0-9]+)/records/auto/regroup/', views.regroup_auto_records, name="regroup_auto_records"),
    re_path(r'account/(?P<tenant_id>[0-9]+)/records/manual/regroup/', views.regroup_manual_records, name="regroup_manual_records"),
    re_path(r'account/(?P<tenant_id>[0-9]+)/records/', views.records, name='records'),
    # re_path(r'account/(?P<tenant_id>[0-9]+)/transaction/bulk/', views.transaction_bulk, name="transaction_bulk"),
    # re_path(r'account/(?P<tenant_id>[0-9]+)/transaction/', views.transaction_new_from_records, name="transaction_new_from_records"),
    # re_path(r'account/(?P<tenant_id>[0-9]+)/transaction/(?P<transaction_type>[a-z]+/', views.transaction_new_from_type, name="transaction_new_from_type"),
    # re_path(r'account/(?P<tenant_id>[0-9]+)/transaction/(?P<transaction_id>[0-9]+)/delete/', views.transaction_delete, name="transaction_delete"),
    re_path(r'account/(?P<tenant_id>[0-9]+)/transaction/(?P<transaction_id>[0-9]+)/edit/', views.transaction_edit, name="transaction_edit"),    
    re_path(r'account/(?P<tenant_id>[0-9]+)/transactions/', views.transactions, name="transactions"),
    re_path(r'account/(?P<tenant_id>[0-9]+)/transaction/', views.transaction_new, name="transaction_new"),    
    re_path(r'account/(?P<tenant_id>[0-9]+)/projection/', views.projection, name="projection"),
    re_path(r'account/(?P<tenant_id>[0-9]+)/creditcardexpenses/', views.creditcardexpenses, name="creditcardexpenses"),
    re_path(r'account/(?P<tenant_id>[0-9]+)/run_projections/', views.run_projections, name="run_projections"),
    re_path(r'account/(?P<tenant_id>[0-9]+)/(?P<model_name>[a-z]+)/(?P<model_id>[0-9]+)/', views.model_edit, name="model_edit"),
    re_path(r'account/(?P<tenant_id>[0-9]+)/(?P<model_name>[a-z]+)/', views.model_edit, name="model_edit"),
    re_path(r'account/(?P<tenant_id>[0-9]+)/', views.account_home, name="account_home"),
    path('admin/', admin.site.urls),
]
