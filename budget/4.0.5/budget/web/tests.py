from django.test import TestCase
import logging 
# Create your tests here.
from web.util.recordgrouper import RecordGrouper
from web.models import *

logger = logging.getLogger(__name__)

trs = TransactionRuleSet.objects.filter(is_auto=False)
for ruleset in trs:    
    records = ruleset.records()
    logger.warning(f'rule set: {ruleset.name} -- {len(records)} records')    
    RecordGrouper._get_timings(records)
