from django.shortcuts import render, redirect
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_http_methods
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.forms import modelformset_factory

import sys
from datetime import datetime
import logging
import traceback
from web.forms import new_transaction_rule_form_set, form_types, TransactionRuleSetForm, TransactionRuleForm, CreditCardForm, RecordTypeForm, UploadedFileForm, AccountForm, CreditCardExpenseFormSet
from web.models import records_from_rules, TransactionRule, TransactionRuleSet, RecordType, CreditCard, Account, Record, Transaction, RecurringTransaction, SingleTransaction, CreditCardTransaction, DebtTransaction, UploadedFile, PlannedPayment, ProtoTransaction
from web.util.viewutil import get_heatmap_data, get_records_template_data, transaction_type_display
from web.util.recordgrouper import RecordGrouper 
from web.util.projections import fill_planned_payments
from web.util.modelutil import TransactionTypes
from web.util.viewutil import process_uploaded_file, save_processed_records, ruleset_stats
# from web.util.cache import cache_fetch, cache_fetch_objects, cache_store
# from django.core import serializers

logger = logging.getLogger(__name__)

def home(request):

    return redirect('transactions', tenant_id=1)

def model_list(request, tenant_id):

    accounts = Account.objects.order_by('id')
    creditcards = CreditCard.objects.all()
    recordtypes = RecordType.objects.all()

    return render(request, "model_list.html", {'accounts': accounts, 'creditcards': creditcards, 'recordtypes': recordtypes})

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
        logger.info(f'deleting {model_name} {model_id}')

        try:
            model.delete()
        except:
            logger.error(f'{sys.exc_info()[0]} {sys.exc_info()[1]}')
            traceback.print_tb(sys.exc_info()[2])

        return redirect(f'model_list', tenant_id=tenant_id)
    elif request.method == "POST":
        form = model_map[model_name]['form'](request.POST, instance=model)
        if form.is_valid():
            form.save()
            return redirect(f'model_list', tenant_id=tenant_id)
    
    if not form:
        form = model_map[model_name]['form'](instance=model)
    
    return render(request, f'model_edit.html', {'form': form, 'model_name': model_map[model_name]['model'].__name__})

def transactionrulesets_list(request, tenant_id, transactionruleset_id=None):
    
    message = ""

    try:

        transactionrulesets_auto = TransactionRuleSet.objects.filter(is_auto=True)
        transactionrulesets_manual = TransactionRuleSet.objects.filter(is_auto=False)

        if False:
            for trs in transactionrulesets:
                record_stats = RecordGrouper.get_stats(trs.records())
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
                    'account': trs.records()[0].account,
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

    TransactionRuleFormSet = new_transaction_rule_form_set(extra=1)
    
    transactionruleset = TransactionRuleSet()
    transactionrule_formset = TransactionRuleFormSet(queryset=TransactionRule.objects.none())
    transactionruleset_form = TransactionRuleSetForm()
    
    transactionrules = []

    if transactionruleset_id:
        
        TransactionRuleFormSet = new_transaction_rule_form_set(extra=0)
        
        transactionruleset = TransactionRuleSet.objects.get(pk=transactionruleset_id)
        transactionrules = TransactionRule.objects.filter(transactionruleset_id=transactionruleset_id)
        transactionrule_formset = TransactionRuleFormSet(queryset=transactionrules)
        transactionruleset_form = TransactionRuleSetForm(instance=transactionruleset)

    template_data = {
        'auto_stats': ruleset_stats(transactionrulesets_auto),
        'manual_stats': ruleset_stats(transactionrulesets_manual),
        'transactionrulesets_auto': sorted(transactionrulesets_auto, key=lambda t: t.prototransaction.stats['monthly_amount'], reverse=True),
        'transactionrulesets_manual': sorted(transactionrulesets_manual, key=lambda t: t.priority, reverse=False),
        'message': message,
        'transactionruleset_form': transactionruleset_form,
        'recordfields': [ f.name for f in Record._meta.fields ],
        'transactionrule_formset': transactionrule_formset,
        'join_operators': TransactionRuleSet.join_operator_choices
    }

    return render(request, "transactionrulesets_list.html", template_data)

def transactionruleset_edit(request, tenant_id, transactionruleset_id=None, rule=None):

    TransactionRuleFormSet = new_transaction_rule_form_set(extra=1)

    transactionruleset = TransactionRuleSet()
    transactionrule_formset = TransactionRuleFormSet(queryset=TransactionRule.objects.none())
    # transactionrule_formset.forms.append(TransactionRuleForm())
    transactionruleset_form = TransactionRuleSetForm()

    transactionrules = []

    if transactionruleset_id:

        TransactionRuleFormSet = new_transaction_rule_form_set(extra=0)

        transactionruleset = TransactionRuleSet.objects.get(pk=transactionruleset_id)
        transactionrules = TransactionRule.objects.filter(transactionruleset_id=transactionruleset_id)
        transactionrule_formset = TransactionRuleFormSet(queryset=transactionrules)
        transactionruleset_form = TransactionRuleSetForm(instance=transactionruleset)

    response = {
        'success': False,
        'messages': [],
        'field_messages': {},
        'data': {
            'records': [],                 
            # 'unaccounted_record_ids': ""                
        }
    }
    
    if request.method == "DELETE":

        try:
            transactionruleset.delete()
            response['success'] = True 
        except:
            message = sys.exc_info()[1]
            logger.error(sys.exc_info()[0])
            logger.error(message)
            traceback.print_tb(sys.exc_info()[2])
            response['messages'].append(message)

        # return redirect(f'transactionrulesets_list', tenant_id=tenant_id)

    elif request.method == "POST":
        logger.warning(request.POST)
    
        TransactionRuleFormSet = new_transaction_rule_form_set(extra=0)
        
        transactionrule_formset = TransactionRuleFormSet(request.POST, queryset=transactionrules)

        if 'id' in request.POST and request.POST['id'].strip() != '':
            transactionruleset = TransactionRuleSet.objects.get(pk=request.POST['id'])
        
        transactionruleset_form = TransactionRuleSetForm(request.POST)
        if transactionruleset:
            transactionruleset_form = TransactionRuleSetForm(request.POST, instance=transactionruleset)

        if request.POST['submit_event_type'] in ["blur", "keyup", "change", "click", "DOMContentLoaded"]:

            try:

                if transactionruleset_form.is_valid():

                    transactionrule_formset.is_valid(preRuleSet=transactionruleset.id is None)
                    
                    logger.warning(f'Getting records from {[ form.cleaned_data for form in transactionrule_formset ]}')
                    filters = [ TransactionRule(**form.cleaned_data).filter() for form in transactionrule_formset ]
                    filters = [ f for f in filters if f ]
                    logger.warning(f'have {len(filters)} filters')
                    record_queryset = records_from_rules(filters, transactionruleset_form.cleaned_data['join_operator'])

                    # record_queryset = None
                    # for form in transactionrule_formset:                                                  
                    #     record_queryset = records_from_rule(form.cleaned_data['record_field'], form.cleaned_data['match_operator'], form.cleaned_data['match_value'], transactionruleset_form.cleaned_data['join_operator'], record_queryset=record_queryset)

                    # if record_queryset:
                        
                    record_data = [ { 
                        'id': r.id, 
                        'transaction_date': r.transaction_date, 
                        'description': r.description, 
                        'amount': r.amount, 
                        'account': r.uploaded_file.account.name if r.uploaded_file.account else r.uploaded_file.creditcard.name,              
                        'extra_fields': r.extra_fields
                    } for r in record_queryset ]
                    
                    response['data']['records'] = record_data 

                    # unaccounted_record_ids = [ str(r['id']) for r in record_data if not r['transaction'] ]
                    # response['data']['unaccounted_record_ids'] = ",".join(unaccounted_record_ids)
                    
                    recordstats = {
                        'total_record_count': len(record_data),
                        # 'unaccounted_record_count': len(unaccounted_record_ids),
                        **get_records_template_data(record_queryset)
                    }

                    response['data']['recordstats'] = render_to_string("_recordstats.html", context=recordstats)
                    response['data']['aggregate'] = render_to_string("_ruleset_aggregate.html", context=recordstats)
                    response['data']['heatmaps'] = render_to_string("_heatmaps.html", context={ 'heatmap_data': get_heatmap_data(record_queryset) })
                    response['data']['ruleresults'] = render_to_string("_ruleresults.html", context={ 'records': record_data })                    

                    # else:
                    #     message = "No queryset!"
                    #     response['messages'].append(message)
                    #     logger.error(message)
                    
                    response['success'] = True 
                
                response['messages'].extend(transactionruleset_form.errors)

            except ValidationError as ve:
                error_type = sys.exc_info()[0]
                logger.error(error_type)
                message = sys.exc_info()[1]
                logger.error(message)
                response['messages'].append(f'{error_type.__name__}\n{message}')
                traceback.print_tb(sys.exc_info()[2])
            except:
                error_type = sys.exc_info()[0]
                logger.error(error_type)
                message = str(sys.exc_info()[1])
                logger.error(message)
                response['messages'].append(f'{error_type.__name__}\n{message}')
                traceback.print_tb(sys.exc_info()[2])
            
        elif request.POST['submit_event_type'] == "submit":
            
            try:

                transactionruleset_form.is_valid() 
                transactionrule_formset.is_valid(preRuleSet=transactionruleset.id is None)

                transactionruleset = transactionruleset_form.save()

                # -- TODO: verify the is_valid() above actually does everything to ensure the save() below never, ever fails
                # -- TODO: maybe do a match/replace only on the deleted/changed rules instead of deleting everything 
                for transactionrule in transactionruleset.transactionrules.all():
                    transactionrule.delete()

                for form in transactionrule_formset:
                    trf = TransactionRuleForm({ **form.cleaned_data, 'transactionruleset': transactionruleset })
                    trf.is_valid()
                    trf.save()
                
                stats = RecordGrouper.get_stats(transactionruleset.records(refresh=True))

                logger.info(dir(transactionruleset))
                
                try:
                    transactionruleset.prototransaction.update_stats(stats)
                    transactionruleset.prototransaction.save() 
                except:
                    proto_transaction = ProtoTransaction.new_from(transactionruleset.name, stats, transactionruleset)

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
                
                # return redirect("transactionrulesets_list", tenant_id=tenant_id)

                response['success'] = True 

            except ValidationError as ve:
                error_type = sys.exc_info()[0]
                logger.error(error_type)
                message = str(sys.exc_info()[1])
                logger.error(message)
                response['messages'].append(f'{error_type.__name__}\n{message}')
                traceback.print_tb(sys.exc_info()[2])
            except:
                error_type = sys.exc_info()[0]
                logger.error(error_type)
                message = str(sys.exc_info()[1])
                logger.error(message)
                response['messages'].append(f'{error_type.__name__}\n{message}')
                traceback.print_tb(sys.exc_info()[2])

            # for form in formset:
            #     logger.warning(f'creating TransactionRule from {form.cleaned_data}')
            #     transaction_rule = TransactionRule(**form.cleaned_data)
            #     transaction_rule.transactionruleset = transactionruleset 
            #     transaction_rule.save()

    return JsonResponse(response)

    # if transactionruleset:
    #     transactionruleset_form = TransactionRuleSetForm(instance=transactionruleset)

    # template_data = {
    #     'transactionruleset_form': transactionruleset_form,
    #     'recordfields': [ f.name for f in Record._meta.fields ],
    #     'transactionrule_formset': transactionrule_formset,
    #     'join_operators': TransactionRuleSet.join_operator_choices
    # }
    
    # return render(request, "transactionruleset_edit.html", template_data)

def delete_uploadedfile(request, tenant_id, uploadedfile_id):
    success = False 
    message = ""

    try:
        uploadedfile = UploadedFile.objects.get(pk=uploadedfile_id)
        if uploadedfile:
            others = []
            if uploadedfile.account:
                others = UploadedFile.objects.filter(account=uploadedfile.account)
            elif uploadedfile.creditcard:
                others = UploadedFile.objects.filter(creditcard=uploadedfile.creditcard)
            
            others = [ o for o in others if o.id != uploadedfile.id ]

            logger.info(f'found {len(others)} previously uploaded files for the same account/credit card')

            logger.info(f'deleting up to {uploadedfile.records.count()} records from, and uploaded file {uploadedfile.original_filename}')
            uploadedfile.records.all().delete()
            uploadedfile.delete()
            
            for other in others:                
                other_details = process_uploaded_file(other)
                logger.info(f'found {len(other_details["records"])} reprocessing uploaded file {other.original_filename}')
                save_processed_records(other_details['records'], other)

            success = True 

    except:
        message = f'{sys.exc_info()[0].__name__}: {str(sys.exc_info()[1])}'
        logger.error(message)
        traceback.print_tb(sys.exc_info()[2])

    return JsonResponse({'success': success, 'message': message})

def records(request, tenant_id):
    
    hide_accounted = False 
    full_path = request.get_full_path()
    if '?' in full_path:
        querystring = { e.split('=')[0]: e.split('=')[1] for e in full_path.split('?')[1].split('&') }
        if 'hide_accounted' in querystring:
            hide_accounted = str(querystring['hide_accounted']) == "1"
    
    record_rules = RecordGrouper.get_record_rule_index()

    record_sort = '-transaction_date'

    if request.method == "POST":
        record_sort = request.POST['record_sort'] if 'record_sort' in request.POST else '-date' 

    records_by_account = [ { 
        'obj': a, 
        'records': Record.objects.filter(uploaded_file__account=a).order_by('-post_date') 
    } for a in Account.objects.all() ]

    records_by_creditcard = [ {
        'obj': c, 
        'records': Record.objects.filter(uploaded_file__creditcard=c).order_by('-post_date') 
    } for c in CreditCard.objects.all() ]

    if hide_accounted:
        for a in records_by_account:
            a['records'] = [ r for r in a['records'] if str(r.id) not in record_rules ]
        for c in records_by_creditcard:
            c['records'] = [ r for r in c['records'] if str(r.id) not in record_rules ]

    show_record_columns = ['id', 'transaction_date', 'description', 'amount', 'extra_fields', 'type']

    template_data = {
        'hide_accounted': hide_accounted,
        'record_rules': record_rules,
        'records_by_account': records_by_account,
        'records_by_creditcard': records_by_creditcard,
        'record_sort': record_sort,                
        'record_columns': [ r.name for r in Record._meta.fields if len(show_record_columns) == 0 or r.name in show_record_columns ]
    }

    return render(request, "records.html", template_data)

def files(request, tenant_id):

    uploadedfile_form = UploadedFileForm()
    message = ''

    if request.method == "POST" and 'upload' in request.FILES:

        logger.debug(request.POST)

        uploadedfile_form = UploadedFileForm(request.POST, request.FILES)

        if uploadedfile_form.is_valid():

            logger.debug(uploadedfile_form.cleaned_data)
            
            logger.warning(f'{uploadedfile_form.cleaned_data["upload"]} is valid')
            uploadedfile = uploadedfile_form.save()
            uploadedfile.refresh_from_db()
            # uploadedfile = UploadedFile.objects.get(pk=uploadedfile.id)

            # logger.debug(uploadedfile.creditcard.recordtype.csv_columns)

            try:
                file_details = process_uploaded_file(uploadedfile)
                uploadedfile.first_date = file_details['first_date']
                uploadedfile.last_date = file_details['last_date']
                uploadedfile.record_count = len(file_details['records'])
                uploadedfile.save()

                save_processed_records(file_details['records'], uploadedfile)

                return redirect('records', tenant_id=tenant_id)

            except:
                message = f'{sys.exc_info()[0].__name__}: {sys.exc_info()[1]}: therefore, deleting uploaded file {uploadedfile.id}'
                logger.warning(message)
                traceback.print_tb(sys.exc_info()[2])
                uploadedfile.delete()
            
            RecordGrouper.group_records()
                
    template_data = {
        'messages': [message],
        'uploadedfile_form': uploadedfile_form,
        'uploadedfiles': UploadedFile.objects.all().order_by('account_id', 'creditcard_id', 'first_date')
    }

    return render(request, "files.html", template_data)

def reprocess_files(request, tenant_id):

    files = UploadedFile.objects.all()
    for f in files:        
        details = process_uploaded_file(f)
        db_records = f.records.all()
        logger.info(f'Reprocessing {f.original_filename}/{f.account_name()} found {len(details["records"])} records, {len(db_records)} currently in database')
        logger.warning(f'Deleting {len(db_records)} from {f.account_name()}')
        db_records.delete()
        logger.info(f'Saving {len(details["records"])} records from reprocessing uploaded file {f.original_filename}')
        save_processed_records(details['records'], f)
    
    return redirect("files", tenant_id=tenant_id)

def regroup_records(request, tenant_id):

    try:
        RecordGrouper.group_records(force_regroup_all=True)
    except:
        message = str(sys.exc_info()[1])
        logger.error(sys.exc_info()[0])
        logger.error(message)
        traceback.print_tb(sys.exc_info()[2])

    return redirect("transactionrulesets_list", tenant_id=tenant_id)

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
    # transactionrulesets = TransactionRuleSet.objects.all()
    # for trs in transactionrulesets:
    #     records = trs.records()
    #     record_stats = RecordGrouper.get_stats(records)
    #     form_types[record_stats['transaction_type']].from_stats(record_stats)
    #     transaction = Transaction.from_stats(record_stats)
    #     PlannedPayment.create_from_transaction(transaction)

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
    income_transactions = RecurringTransaction.objects.filter(transaction_type=TransactionTypes.TRANSACTION_TYPE_INCOME).order_by('name')
    debt_transactions = DebtTransaction.objects.all().order_by('-interest_rate')
    utility_transactions = RecurringTransaction.objects.filter(transaction_type=TransactionTypes.TRANSACTION_TYPE_UTILITY).order_by('name')
    creditcard_transactions = CreditCardTransaction.objects.all()

    transactions = RecurringTransaction.objects.all()
    total_monthly_out = sum([ o.monthly_amount() for o in transactions if o.transaction_type not in [TransactionTypes.TRANSACTION_TYPE_INCOME] ])
    total_monthly_in = sum([ o.monthly_amount() for o in transactions if o.transaction_type in [TransactionTypes.TRANSACTION_TYPE_INCOME] ])
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

# def transaction_bulk(request, tenant_id):

#     TransactionIntakeFormSet = formset_factory(TransactionIntakeForm, can_delete=True, extra=0)
#     formset = TransactionIntakeFormSet()
#     formset_errors = []
#     formset_data = [ { 
#         'is_imported': True, 
#         'record_group_id': rg.id,
#         **RecordGrouper.get_record_group_stats(rg.id)        
#     } for rg in RecordGroup.objects.all() ]

#     if request.method == "POST":

#         # total_forms_range = range(int(request.POST['form-INITIAL_FORMS']))
#         # form_fields = ['name', 'amount', 'transaction_type', 'is_imported', 'record_group_id']

#         # stats_data = [ RecordGrouper.get_record_group_stats(request.POST[f'form-{i}-record_group_id']) for i in total_forms_range if f'form-{i}-record_group_id' in request.POST ]
#         # form_data = [ { k: request.POST[f'form-{i}-{k}'] for k in form_fields } for i in total_forms_range if f'form-{i}-{form_fields[0]}' in request.POST ]
#         # print(json.dumps(form_data[0], indent=4))
#         # formset_data = [ { **stats_data[index], **item } for index, item in enumerate(form_data) ]
#         # print(json.dumps(formset_data[0], indent=4))

#         formset = TransactionIntakeFormSet(request.POST, initial=formset_data)
#         print(f'validing {len(formset.forms)} forms in formset')
#         for form in formset.forms:
#             if form.is_valid():
#                 logger.warning(f'Form is valid.. saving!')
#                 logger.warning(form)
#                 form.save()                
#             else:
#                 # form_errors = [ e for e in form.errors ]
#                 formset_errors.append(form.errors)
#                 logger.warning(f'formset errors: {len(form.errors)}')
#                 print(form.errors)
#                 # print(form.non_form_errors())
#     else:
        
#         formset = TransactionIntakeFormSet(initial=formset_data)
    
#     return render(request, "transaction_bulk.html", {'formset': formset, 'formset_errors': formset_errors})

@require_http_methods(['POST'])
def transaction_new(request, tenant_id, transaction_type=None):

    transaction_form = None 
    transaction_type = None 
    records = []
    initial_data = {
        'is_imported': False 
    }

    '''
    we get here one of two ways:
        1. 'new [type]' from transactions page -> requires transmitting transaction_type 
        2. clicking 'create from records' on records page -> requires transmitting record IDs
    however, transactions are created in other ways:
        1. from bulk intake
        2. from rules (TBD)
        3. (TBD) automatically on file upload or user demand in place of "group records", we skip RecordGroup and just create the XTransaction
    '''
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
                'is_imported': True
                # 'record_ids': record_id_post
            }
    
    initial_data['transaction_type'] = transaction_type 

    # -- this is the actual post from the transaction create/edit form 
    if 'name' in request.POST:
    
        transaction_form = form_types[transaction_type](request.POST, initial=initial_data)

        if transaction_form.is_valid():
    
            transaction = transaction_form.save()
        
            # for record in records:
            #     record.transaction = transaction
            #     record.save()

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

    if request.method == "DELETE":
        transaction.delete() 

    elif request.method == "POST":

        # logger.warning("got post for %s" % name_slug)
        logger.warning(request.POST)
        transaction_form = form_class(request.POST, instance=transaction)

        if transaction_form.is_valid():
            transaction_form.save()
            return redirect('transactions', tenant_id=tenant_id)
        else:
            logger.error("not valid!")


    template_data = {        
        'form': transaction_form, 
        'new_or_edit': 'Edit', 
        'transaction_type_or_name': f'{transaction_type_display(transaction.transaction_type)}: {transaction.name}'
    }

    return render(request, "transaction_edit.html", template_data)

# def transaction_delete(request, tenant_id, transaction_id):

#     # logger.info("deleting %s" % name_slug)
#     # name = name_slug.replace('-', ' ')

#     transaction = Transaction.objects.get(pk=transaction_id)

#     if transaction:
#         transaction.delete()
#     else:
#         logger.error(f'could not delete transaction by id {transaction_id}')

#     return redirect("transactions", tenant_id=tenant_id)

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
