from tkinter import E
from django.db.models import Q
from django.shortcuts import render, redirect
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.forms import formset_factory, modelformset_factory

import json 
import sys
import math
from decimal import Decimal
from datetime import datetime, timedelta
import logging
import traceback
from web.forms import form_types, BaseTransactionRuleFormSet, TransactionRuleSetForm, TransactionRuleForm, CreditCardForm, RecordTypeForm, RecordForm, UploadedFileForm, AccountForm, TransactionForm, TransactionIntakeForm, CreditCardExpenseFormSet
from web.models import TransactionRule, TransactionRuleSet, RecordType, CreditCard, Vehicle, Property, Account, Record, RecordGroup, Transaction, RecurringTransaction, SingleTransaction, CreditCardTransaction, DebtTransaction, UploadedFile, PlannedPayment, CreditCardExpense
from web.viewutil import get_records_for_filter, get_recordgroup_data, get_heatmap_data, get_records_template_data, transaction_type_display
from web.util.recordgrouper import RecordGrouper 
from web.util.projections import fill_planned_payments
from web.modelutil import process_uploaded_file 
from web.util.cache import cache_fetch, cache_fetch_objects, cache_store
from django.core import serializers

logger = logging.getLogger(__name__)

# transaction_types = {
#     Transaction.TRANSACTION_TYPE_SINGLE: SingleTransaction,
#     Transaction.TRANSACTION_TYPE_INCOME: RecurringTransaction,
#     Transaction.TRANSACTION_TYPE_UTILITY: RecurringTransaction,
#     Transaction.TRANSACTION_TYPE_CREDITCARD: CreditCardTransaction,
#     Transaction.TRANSACTION_TYPE_DEBT: DebtTransaction
# }

def home(request):

    return redirect('transactions', tenant_id=1)

##### ACCOUNTS 

def accounts(request, tenant_id):

    accounts = Account.objects.order_by('id')
    creditcards = CreditCard.objects.all()
    recordtypes = RecordType.objects.all()

    return render(request, "accounts.html", {'accounts': accounts, 'creditcards': creditcards, 'recordtypes': recordtypes})

model_map = {
    'creditcard': {
        'model': CreditCard,
        'form': CreditCardForm 
    },
    'account': {
        'model': Account,
        'form': AccountForm
    },
    'recordtype': {
        'model': RecordType,
        'form': RecordTypeForm 
    }
}

def model_edit(request, tenant_id, model_name, model_id=None):

    form = None 
    model = model_map[model_name]['model']()

    if model_id:
        model = model_map[model_name]['model'].objects.get(pk=model_id)
    
    if request.method == "DELETE":
        model.delete()
        return redirect(f'accounts', tenant_id=tenant_id)
    elif request.method == "POST":
        form = model_map[model_name]['form'](request.POST, instance=model)
        if form.is_valid():
            form.save()
            return redirect(f'accounts', tenant_id=tenant_id)
    
    if not form:
        form = model_map[model_name]['form'](instance=model)
    
    return render(request, f'account_edit.html', {'form': form, 'model_name': model_map[model_name]['model'].__name__})

@require_http_methods(['GET', 'POST', 'DELETE'])
def account_edit(request, tenant_id, account_id=None):

    form = None 
    acc = Account()

    if account_id:
        acc = Account.objects.get(pk=account_id)

    if request.method == "DELETE":
      
        acc.delete()
        return redirect('accounts', tenant_id=tenant_id)

    elif request.method == "POST":
        form = AccountForm(request.POST, instance=acc)
        if form.is_valid():
            form.save()
            return redirect('accounts', tenant_id=tenant_id)

    if not form:
        form = AccountForm(instance=acc)

    return render(request, "account_edit.html", {'form': form})

##### RECORDS

def transactionrulesets_list(request, tenant_id):
    
    message = ""

    try:

        transactionrulesets = TransactionRuleSet.objects.all()
        if True:
            for trs in transactionrulesets:
                trs.evaluate(force=True) 
                record_stats = RecordGrouper.get_stats(trs.records)
                # logger.warning(record_stats['transaction_type'])

                initial_data = {
                    'name': f'{record_stats["description"]}:{datetime.strftime(datetime.now(), "%s")}',
                    'amount': f'{record_stats["recurring_amount"]:.2f}',
                    'is_imported': True,
                    'cycle_due_date': record_stats['most_frequent_date'],
                    'started_at': record_stats['started_at'],
                    'transaction_type': record_stats['transaction_type'],
                    'is_active': True,
                    'period': record_stats['period'],
                    'started_at': record_stats['started_at'],
                    'cycle_due_date': record_stats['most_frequent_date'],
                    'is_variable': record_stats['is_variable'],
                    'transactionruleset': trs,
                    'account': trs.records[0].account,
                    'transaction_at': datetime.now()
                }
                
                # logger.warning(initial_data)
                
                txform = form_types[record_stats['transaction_type']](initial_data)
                txform.is_valid()
                # logger.error('errors:')
                # logger.error(txform.errors)
                # logger.error(txform.data)
                # logger.error('made it here?!?!?!?!')

                trs.transaction = txform.save(commit=False)
                # logger.warning(trs.transaction)
    except:
        logger.error(sys.exc_info()[0])
        message = str(sys.exc_info()[1])
        logger.error(message)
        traceback.print_tb(sys.exc_info()[2])

    template_data = {
        'transactionrulesets': transactionrulesets,
        'message': message 
    }

    return render(request, "transactionrulesets_list.html", template_data)

def transactionruleset_edit(request, tenant_id, transactionruleset_id=None):
    
    TransactionRuleFormSet = modelformset_factory(TransactionRule, form=TransactionRuleForm, formset=BaseTransactionRuleFormSet, fields=('record_field', 'match_operator', 'match_value', 'transactionruleset'), extra=1)
    transactionruleset = TransactionRuleSet()
    transactionrule_formset = TransactionRuleFormSet(queryset=TransactionRule.objects.none())
    transactionruleset_form = TransactionRuleSetForm()

    transactionrules = []

    if transactionruleset_id:
        TransactionRuleFormSet = modelformset_factory(TransactionRule, form=TransactionRuleForm, formset=BaseTransactionRuleFormSet, fields=('record_field', 'match_operator', 'match_value', 'transactionruleset'), extra=0)
        transactionruleset = TransactionRuleSet.objects.get(pk=transactionruleset_id)
        transactionrules = TransactionRule.objects.filter(transactionruleset_id=transactionruleset_id)
        transactionrule_formset = TransactionRuleFormSet(queryset=transactionrules)
        transactionruleset_form = TransactionRuleSetForm(instance=transactionruleset)

    if request.method == "DELETE":
        transactionruleset.delete()
        return redirect(f'transactionrulesets_list', tenant_id=tenant_id)

    if request.method == "POST":

        logger.warning(request.POST)

        response = {
            'success': False,
            'message': "",
            'data': {
                'records': [], 
                'total_record_count': 0, 
                'unaccounted_record_count': 0, 
                'record_ids': ""
            }
        }
            
        TransactionRuleFormSet = modelformset_factory(TransactionRule, form=TransactionRuleForm, formset=BaseTransactionRuleFormSet, fields=('record_field', 'match_operator', 'match_value', 'transactionruleset'), extra=0)
        transactionrule_formset = TransactionRuleFormSet(request.POST, queryset=transactionrules)

        if 'id' in request.POST and request.POST['id'].strip() != '':
            transactionruleset = TransactionRuleSet.objects.get(pk=request.POST['id'])
        
        transactionruleset_form = TransactionRuleSetForm(request.POST)
        if transactionruleset:
            transactionruleset_form = TransactionRuleSetForm(request.POST, instance=transactionruleset)

        if request.POST['submit_type'] in ["keyup", "change", "click", "DOMContentLoaded"]:

            try:

                transactionruleset_form.is_valid() 
                transactionrule_formset.is_valid(preRuleSet=transactionruleset.id is None)

                record_queryset = None    
                for form in transactionrule_formset:            
                    record_queryset = records_from_rule(form.cleaned_data['record_field'], form.cleaned_data['match_operator'], form.cleaned_data['match_value'], transactionruleset_form.cleaned_data['join_operator'], record_queryset=record_queryset)

                if record_queryset:
                    record_data = [ { 'id': r.id, 'transaction_date': r.transaction_date, 'description': r.description, 'amount': r.amount, 'transaction': str(r.transaction) if r.transaction else None } for r in record_queryset ]
                    unaccounted_record_ids = [ str(r['id']) for r in record_data if not r['transaction'] ]
                    response['data']['records'] = record_data 
                    response['data']['record_ids'] = ",".join(unaccounted_record_ids)
                    response['data']['total_record_count'] = len(record_data)
                    response['data']['unaccounted_record_count'] = len(unaccounted_record_ids)
                else:
                    message = "No queryset!"
                    response['message'] = message
                    logger.error(message)
                
                response['success'] = True 

            except ValidationError as ve:
                error_type = sys.exc_info()[0]
                logger.error(error_type)
                message = str(sys.exc_info()[1])
                logger.error(message)
                response['message'] = f'{response["message"]}{error_type.__name__}\n{message}'
                traceback.print_tb(sys.exc_info()[2])
            except:
                error_type = sys.exc_info()[0]
                logger.error(error_type)
                message = str(sys.exc_info()[1])
                logger.error(message)
                response['message'] = f'{response["message"]}{error_type.__name__}\n{message}'
                traceback.print_tb(sys.exc_info()[2])
                
            return JsonResponse(response)
        
        elif request.POST['submit_type'] == "submit":
            
            try:

                transactionruleset_form.is_valid() 
                transactionrule_formset.is_valid(preRuleSet=transactionruleset.id is None)

                transactionruleset = transactionruleset_form.save()

                for transactionrule in transactionruleset.transactionrules.all():
                    transactionrule.delete()

                logger.warning(dir(transactionrule_formset))

                logger.warning(f'saved transactionruleset {transactionruleset}')

                logger.warning(transactionrule_formset)

                for form in transactionrule_formset:
                    trf = TransactionRuleForm({ **form.cleaned_data, 'transactionruleset': transactionruleset })
                    trf.is_valid()
                    trf.save()

                # transactionrule_formset.save() 

                # -- breaking the formset and re-creating individual TransactionRuleForm was intended to inject the transactionruleset 
                # -- which was previously not included in the formset fields 
                # for form in transactionrule_formset:
                    
                    # logger.warning(f'checking TransactionRuleFormSet form data: {form.cleaned_data}')                    
                    # if form.is_valid():
                    #     trf = TransactionRuleForm({ **form.cleaned_data, 'transactionruleset': transactionruleset })
                    #     if 'id' in form.cleaned_data and form.cleaned_data["id"]:
                    #         logger.warning(f'creating form for existing transactionrule {form.cleaned_data["id"]}')
                    #         trf = TransactionRuleForm({ **form.cleaned_data, 'transactionruleset': transactionruleset }, instance=TransactionRule.objects.get(pk=form.cleaned_data['id']))
                    #     else:
                    #         logger.warning(f'id not in TransactionRuleFormSet form cleaned data or is null, saving TransactionRuleForm with transactionruleset {transactionruleset}')                        
                    #     trf.is_valid()
                    #     trf.save()
                
                return redirect("transactionrulesets_list", tenant_id=tenant_id)

            except ValidationError as ve:
                error_type = sys.exc_info()[0]
                logger.error(error_type)
                message = str(sys.exc_info()[1])
                logger.error(message)
                traceback.print_tb(sys.exc_info()[2])
            except:
                error_type = sys.exc_info()[0]
                logger.error(error_type)
                message = str(sys.exc_info()[1])
                logger.error(message)
                traceback.print_tb(sys.exc_info()[2])

            # for form in formset:
            #     logger.warning(f'creating TransactionRule from {form.cleaned_data}')
            #     transaction_rule = TransactionRule(**form.cleaned_data)
            #     transaction_rule.transactionruleset = transactionruleset 
            #     transaction_rule.save()

    transactionrulesets = TransactionRuleSet.objects.all()
    
    if transactionruleset:
        transactionruleset_form = TransactionRuleSetForm(instance=transactionruleset)

    template_data = {
        'transactionruleset_form': transactionruleset_form,
        'transactionrulesets': transactionrulesets,
        'recordfields': [ f.name for f in Record._meta.fields ],
        'transactionrule_formset': transactionrule_formset,
        'join_operators': TransactionRuleSet.join_operator_choices
    }

    '''
    from all account and creditcard records 
    filter out transactions moving money between our own accounts
    filter out redundant "pay back" transactions, paying off credit cards etc.
    identify sets of records that represent a "plannable" recurring payment 
    if the records are already in an amount-by-time set, find the recent, likely value to plan on and the period 
    if the records are scattered, calculate the amount over time: creditcard records will be monthly, account records can be anything
    creditcard records will become creditcardexpense, account records will become some transaction
    the important thing is to account for all historical records _somehow_
    that either a creditcardexpense or transaction exists that represents each historical record 
    and that the CCE/T is associated with the correct creditcard or account 

    records (from creditcard or account)
    -> filter to set 
    -> is on a period? -> histogram -> amount-over-period
    -> scattered? -> average -> amount-over-period 
    -> account records? -> create transaction
    -> creditcard records? -> create creditcardexpense 
    -> tag records with transaction or creditcardexpense
    '''
    return render(request, "transactionruleset_edit.html", template_data)

operation_map = {
    '<': '__lt',
    '=': '',
    '>': '__gt',
    'contains': '__icontains'
}

def records_from_rule(record_field, match_operator, match_value, join_operator, record_queryset=None):

    filter = {
        f'{record_field}{operation_map[match_operator]}': match_value
    }

    logger.warning(json.dumps(filter, indent=4))

    logger.warning(f'{join_operator}: {filter}')

    filterresults = None 

    if record_queryset:
        if join_operator == TransactionRuleSet.JOIN_OPERATOR_AND:
            filterresults = record_queryset.filter(**filter)
        elif join_operator == TransactionRuleSet.JOIN_OPERATOR_OR:
            filterresults = Record.objects.filter(**filter)
            filterresults = set(list(record_queryset) + list(filterresults))
    else:
        filterresults = Record.objects.filter(**filter) 

    return filterresults

# def rulematches(request, tenant_id):
#     rule = None 
#     recordfield = None 
#     success = False 
#     record_ids = ""
#     records = []
#     unaccounted_records = []
#     message = ""
    
#     try:
#         body = json.loads(request.body.decode('utf-8'))
#         if request.method == "POST":
#             recordfield = body['recordfield'] if 'recordfield' in body else None
#             rule = body['rule'] if 'rule' in body else None 
#             operation = body['operation'] if 'operation' in body else None 
#             record_data = records_from_rule(recordfield, operation, rule, TransactionRuleSet.JOIN_OPERATOR_AND)
#             record_data = [ { 'id': r.id, 'transaction_date': r.transaction_date, 'description': r.description, 'amount': r.amount, 'transaction': str(r.transaction) if r.transaction else None } for r in record_data ]
#             unaccounted_record_ids = [ str(r['id']) for r in record_data if not r['transaction'] ]
#             record_ids = ",".join(unaccounted_record_ids)
#         success = True
#     except:        
#         message = str(sys.exc_info()[1])
#         logger.error(sys.exc_info()[0])
#         logger.error(message)
#         traceback.print_tb(sys.exc_info()[2])

#     return JsonResponse({'success': success, 'message': message, 'data': {'records': record_data, 'record_count': len(record_data), 'unaccounted_record_count': len(unaccounted_record_ids), 'record_ids': record_ids}})

def delete_uploadedfile(request, tenant_id, uploadedfile_id):
    success = False 
    message = ""

    try:
        uploadedfile = UploadedFile.objects.get(pk=uploadedfile_id)
        if uploadedfile:
            uploadedfile.records.all().delete()
            uploadedfile.delete()
            success = True 
    except:
        message = str(sys.exc_info()[1])

    return JsonResponse({'success': success, 'message': message})

def records(request, tenant_id):
    
    attribute_filter = None 
    heatmap_region_filter = 0
    record_sort = '-transaction_date' 

    if request.method == "POST":
        attribute_filter = request.POST['attribute_filter'] if 'attribute_filter' in request.POST else None 
        heatmap_region_filter = int(request.POST['heatmap_region_filter']) if 'heatmap_region_filter' in request.POST else 0 
        record_sort = request.POST['record_sort'] if 'record_sort' in request.POST else '-date' 
    
    account_records = Record.objects.filter(Q(account__isnull=False) & ~Q(extra_fields__type='TRANSFER') & Q(transaction__isnull=True)).order_by(record_sort)
    creditcard_records = Record.objects.filter(creditcard__isnull=False).order_by(record_sort)
    
    account_record_count = len(account_records)
    creditcard_record_count = len(creditcard_records)

    filtered_account_records = get_records_for_filter(account_records, attribute_filter, heatmap_region_filter)
    filtered_creditcard_records = get_records_for_filter(creditcard_records, attribute_filter, heatmap_region_filter)

    recordgroup_data = get_recordgroup_data()

    template_data = {
        **get_records_template_data(filtered_account_records),
        'account_records': filtered_account_records,
        'creditcard_records': filtered_creditcard_records,
        'record_ids': ",".join([ str(r.pk) for r in filtered_account_records ]),
        'heatmap_region_filter': heatmap_region_filter, 
        'attribute_filter': attribute_filter,
        'record_sort': record_sort,        
        'recordgroup_data': recordgroup_data,
        'account_record_count': account_record_count,
        'creditcard_record_count': creditcard_record_count
    }

    if len(filtered_account_records) > 0:
        
        record_stats = RecordGrouper.get_stats(filtered_account_records)
        heatmap_data = get_heatmap_data(filtered_account_records) 
        
        template_data = {
            **template_data,
            'transaction_type': record_stats['transaction_type'],            
            'heatmap_data': heatmap_data            
        }

    return render(request, "records.html", template_data)

def files(request, tenant_id):

    uploadedfile_form = UploadedFileForm()

    if request.method == "POST":

        if 'upload' in request.FILES:
            
            uploadedfile_form = UploadedFileForm(request.POST, request.FILES)

            try:
                if uploadedfile_form.is_valid():
                    
                    logger.warning(f'{uploadedfile_form.cleaned_data["upload"]} is valid')
                    uploadedfile = uploadedfile_form.save()
                    uploadedfile = UploadedFile.objects.get(pk=uploadedfile.id)

                    file_details = process_uploaded_file(uploadedfile)

                    uploadedfile.first_date = file_details['first_date']
                    uploadedfile.last_date = file_details['last_date']
                    uploadedfile.record_count = len(file_details['records'])
                    uploadedfile.save()
                    
                    for record in file_details['records']:
                        try:
                            record_data = { 
                                **record, 
                                'uploaded_file': uploadedfile,
                                'account': uploadedfile.account,
                                'creditcard': uploadedfile.creditcard,
                                'description': record['description'] or ''
                            }
                            logger.warning(record_data)
                            record_form = RecordForm(record_data)
                            record_form.is_valid()
                            logger.warning(record_form.errors)
                            record_form.save()

                        except ValidationError as ve:
                            logger.error(sys.exc_info()[0])
                            logger.error(sys.exc_info()[1])
                            traceback.print_tb(sys.exc_info()[2])
                        except:
                            logger.error(sys.exc_info()[0])
                            logger.error(sys.exc_info()[1])
                            traceback.print_tb(sys.exc_info()[2])

                    RecordGrouper.group_records()

                    return redirect('records', tenant_id=tenant_id)
            except:
                message = sys.exc_info()[1]
                logger.error(message)
                traceback.print_tb(sys.exc_info()[2])

    template_data = {
        'uploadedfile_form': uploadedfile_form,
        'uploadedfiles': UploadedFile.objects.all()
    }

    return render(request, "files.html", template_data)

def regroup_records(request, tenant_id):

    try:
        RecordGrouper.group_records(force_regroup_all=True)
    except:
        message = str(sys.exc_info()[1])
        logger.error(sys.exc_info()[0])
        logger.error(message)
        traceback.print_tb(sys.exc_info()[2])

    return redirect("records", tenant_id=tenant_id)

##### PROJECTIONS 

def projection(request, tenant_id):

    '''
    transactionrulesets ->
    transactionrules -> 
    records -> 
    [ analysis/recordgrouper ] -> 
    ...
        - beef up recordgrouper to make final determination for transaction and creditcardexpense fields 
        - now, it makes decent guesses, but these will need to make the call 
    ...
    transactions/creditcardexpenses
    plannedpayments
    '''
    transactionrulesets = TransactionRuleSet.objects.all()
    for trs in transactionrulesets:
        records = trs.records()
        record_stats = RecordGrouper.get_stats(records)
        form_types[record_stats['transaction_type']].from_stats(record_stats)
        transaction = Transaction.from_stats(record_stats)
        PlannedPayment.create_from_transaction(transaction)

    payments = PlannedPayment.objects.order_by('payment_at', 'transaction__amount')

    return render(request, "projection.html", {'payments': payments})

def run_projections(request, tenant_id):

    error = False
    message = ""
    result = {}

    try:

        fill_planned_payments()

    except:
        error = True
        message = str(sys.exc_info()[1])
        logger.error(sys.exc_info()[0])
        logger.error(message)
        traceback.print_tb(sys.exc_info()[2])

    return JsonResponse({'error': error, 'message': message, 'result': result})

    # - set up start date and periods
    # - iterate through periods, figure which transactions fit
    # - write period transactions into PlannedPayment and calculated balances into Balance

##### TRANSACTIONS

def transactions(request, tenant_id):

    # categories = {
    #     'family': {
    #         'tags': ['groceries', 'income', 'medical', 'donations', 'credit_cards', 'childcare', 'internet', 'phone', 'vacation_travel', 'clothing']
    #     },
    #     'property': {
    #         'model': Property,
    #         'tags': ['mortgage', 'property_tax', 'insurance', 'waste', 'electric', 'gas', 'water', 'rental_income', 'maintenance', 'repairs']
    #     },
    #     'vehicle': {
    #         'model': Vehicle,
    #         'tags': ['gas', 'insurance', 'maintenance', 'repairs', 'registration']
    #     }
    # }

    # transaction_sets = { k: {} for k in categories }
    # for category in categories:
    #     if 'model' in categories[category]:
    #         for modelinstance in categories[category]['model'].objects.all():
    #             kwargs = { category: modelinstance }
    #             transaction_sets[category][modelinstance.name] = { tag: list(Transaction.objects.filter(**kwargs, tag__contains=f'{category}:{tag}')) for tag in categories[category]['tags'] }
    #     else:
    #         transaction_sets[category] = { tag: list(Transaction.objects.filter(tag__contains=f'{category}:{tag}')) for tag in categories[category]['tags'] }
    
    # logger.warning(json.dumps(transaction_sets, indent=4))

    single_transactions = SingleTransaction.objects.all().order_by('transaction_at')
    income_transactions = RecurringTransaction.objects.filter(transaction_type=Transaction.TRANSACTION_TYPE_INCOME).order_by('name')
    debt_transactions = DebtTransaction.objects.all().order_by('-interest_rate')
    utility_transactions = RecurringTransaction.objects.filter(transaction_type=Transaction.TRANSACTION_TYPE_UTILITY).order_by('name')
    creditcard_transactions = CreditCardTransaction.objects.all()

    transactions = RecurringTransaction.objects.all()
    total_monthly_out = sum([ o.monthly_amount() for o in transactions if o.transaction_type not in [Transaction.TRANSACTION_TYPE_INCOME] ])
    total_monthly_in = sum([ o.monthly_amount() for o in transactions if o.transaction_type in [Transaction.TRANSACTION_TYPE_INCOME] ])
    monthly_balance = total_monthly_in + total_monthly_out

    total_debt = sum([d.principal for d in debt_transactions])

    template_data = {
        'total_debt': total_debt,
        'monthly_balance': monthly_balance,
        'total_monthly_out': total_monthly_out,
        'total_monthly_in': total_monthly_in,
        'single_transactions': single_transactions,
        'income_transactions': income_transactions,
        'debt_transactions': debt_transactions,
        'utility_transactions': utility_transactions,
        'creditcard_transactions': creditcard_transactions
    }

    return render(request, "transactions.html", template_data)

def transaction_bulk(request, tenant_id):

    TransactionIntakeFormSet = formset_factory(TransactionIntakeForm, can_delete=True, extra=0)
    formset = TransactionIntakeFormSet()
    formset_errors = []
    formset_data = [ { 
        'is_imported': True, 
        'record_group_id': rg.id,
        **RecordGrouper.get_record_group_stats(rg.id)        
    } for rg in RecordGroup.objects.all() ]

    if request.method == "POST":

        # total_forms_range = range(int(request.POST['form-INITIAL_FORMS']))
        # form_fields = ['name', 'amount', 'transaction_type', 'is_imported', 'record_group_id']

        # stats_data = [ RecordGrouper.get_record_group_stats(request.POST[f'form-{i}-record_group_id']) for i in total_forms_range if f'form-{i}-record_group_id' in request.POST ]
        # form_data = [ { k: request.POST[f'form-{i}-{k}'] for k in form_fields } for i in total_forms_range if f'form-{i}-{form_fields[0]}' in request.POST ]
        # print(json.dumps(form_data[0], indent=4))
        # formset_data = [ { **stats_data[index], **item } for index, item in enumerate(form_data) ]
        # print(json.dumps(formset_data[0], indent=4))

        formset = TransactionIntakeFormSet(request.POST, initial=formset_data)
        print(f'validing {len(formset.forms)} forms in formset')
        for form in formset.forms:
            if form.is_valid():
                logger.warning(f'Form is valid.. saving!')
                logger.warning(form)
                form.save()                
            else:
                # form_errors = [ e for e in form.errors ]
                formset_errors.append(form.errors)
                logger.warning(f'formset errors: {len(form.errors)}')
                print(form.errors)
                # print(form.non_form_errors())
    else:
        
        formset = TransactionIntakeFormSet(initial=formset_data)
    
    return render(request, "transaction_bulk.html", {'formset': formset, 'formset_errors': formset_errors})

@require_http_methods(['POST'])
def transaction_new(request, tenant_id):

    transaction_form = None 
    transaction_type = None 
    records = []
    initial_data = {
        'is_imported': False 
    }

    if 'transaction_type' in request.POST:
        transaction_type = request.POST['transaction_type']        
    
    if 'record_ids' in request.POST:
        record_id_post = request.POST['record_ids']
        if record_id_post:
            records = [ Record.objects.get(pk=id) for id in record_id_post.split(',') ]
            record_stats = RecordGrouper.get_stats(records)
            transaction_type = transaction_type or record_stats['transaction_type']

            initial_data = { 
                **initial_data,
                **record_stats,             
                'name': record_stats['description'], 
                'amount': f'{record_stats["recurring_amount"]:.2f}',
                'cycle_due_date': record_stats['most_frequent_date'],
                'started_at': record_stats['started_at'],
                'is_imported': True,
                'record_ids': record_id_post
            }
    
    initial_data['transaction_type'] = transaction_type 

    if 'name' in request.POST:
    
        transaction_form = form_types[transaction_type](request.POST, initial=initial_data)

        if transaction_form.is_valid():
    
            transaction = transaction_form.save()
        
            for record in records:
                record.transaction = transaction
                record.save()

            return redirect('transactions', tenant_id=tenant_id)             
    
    template_data = {
        'form': transaction_form or form_types[transaction_type](initial=initial_data), 
        'new_or_edit': 'New', 
        'transaction_type_or_name': transaction_type_display(transaction_type),
        'records': records
    }

    return render(request, 'transaction_edit.html', template_data)

def transaction_edit(request, tenant_id, transaction_id):

    # logger.warning("editing %s" % name_slug)

    # transaction = Transaction.objects.filter(slug=name_slug)[0]
    base_transaction = Transaction.objects.get(pk=transaction_id)
    form_class = form_types[base_transaction.transaction_type]
    transaction = type(form_class().instance).objects.get(pk=transaction_id)
    logger.warning(f'Editing transaction type {transaction.transaction_type}')
    logger.warning(transaction)    
    transaction_form = form_class(instance=transaction)
    logger.warning(transaction_form.fields)

    if request.method == "POST":

        # logger.warning("got post for %s" % name_slug)
        logger.warning(request.POST)
        transaction_form = form_class(request.POST, instance=transaction)

        if transaction_form.is_valid():
            transaction_form.save()
            return redirect('transactions', tenant_id=tenant_id)
        else:
            logger.error("not valid!")


    template_data = {
        'records': transaction.records.all().order_by('-transaction_date'),
        'form': transaction_form, 
        'new_or_edit': 'Edit', 
        'transaction_type_or_name': f'{transaction_type_display(transaction.transaction_type)}: {transaction.name}'
    }

    return render(request, "transaction_edit.html", template_data)

def transaction_delete(request, tenant_id, transaction_id):

    # logger.info("deleting %s" % name_slug)
    # name = name_slug.replace('-', ' ')

    transaction = Transaction.objects.get(pk=transaction_id)

    if transaction:
        transaction.delete()
    else:
        logger.error(f'could not delete transaction by id {transaction_id}')

    return redirect("transactions", tenant_id=tenant_id)

def creditcardexpenses(request, tenant_id):

    #initial_data = [ {'id': e.id, 'name': e.name, 'amount': e.amount, 'creditcardtransaction': e.creditcardtransaction } for e in CreditCardExpense.objects.all() ]
    # initial_data = list(CreditCardExpense.objects.all())

    if request.method == "POST":
        expense_formset = CreditCardExpenseFormSet(request.POST)
        if expense_formset.is_valid():
            expense_formset.save()

        if request.POST.get('save_and_add'):
            return redirect('creditcardexpenses', tenant_id=tenant_id)
        else:
            return redirect('transactions', tenant_id=tenant_id)

    expense_formset = CreditCardExpenseFormSet()
    return render(request, "creditcardexpenses.html", {'expense_formset': expense_formset})
