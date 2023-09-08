# Budget Badger 

Financial modeling at its finest. 

Two alternate methods of constructing a projection of future spending, budgeting, and financial stability. 

The projection relies on having a view of your income and spending, whether regular expenses, large one-time purchases or debt paydown. This information can be added to the system in one of two ways: importing historical records from your accounts and deriving a picture of your earning and spending with built-in intelligent analysis, or manually describing how you earn and spend money.

In practice, both methods will be used to build the most accurate picture. Analysis of historical records will provide the future picture for earning and spending that has been happening and you expect to continue happening. Manual descriptions are of course necessary for earning and spending that doesn't have a historical record but you expect to happen in the future. Large one-time transactions must also be manually added.

The entire picture could be built manually. Part of the incentive to use the historical record is that it's factual and objective, without any bias about maybe how you'd _like_ to spend and earn money. As you add grouping rules the records will be tagged as "accounted", and you will see a developing area of coverage. When the bulk of the capital volume has been tagged, you know the picture is more complete and will generate a projection closer to reality.

Another reason to build your projection from historical records is that new records can be added over time, and the system will adjust its picture accordingly based on changes in your activity and the grouping rules _weighted on recent activity_, so old habits can die peacefully.

The workflow will look something like this:

### Define your Accounts and Credit Cards 

This is a basic data entry step. These definitions are necessary because the earning and spending will be tracked within your specific holdings. Also, things you use credit cards for may be generally defined by descriptions and amounts over time, but to build a reliable projection this spending must be normalized over the billing cycles of those credit cards. 

### Upload Files for Accounts and Credit Cards and parse Records 

You will need to download CSV reports from your bank and credit cards, and anywhere else earning and spending happens, like money transfer services. The system is built to consume these reports as they are, so they only need to be re-uploaded here.

#### Record Intake 

Each line of a CSV will correspond to a Record in the system, however for CSVs of widely varying formats to coexist, we extract the three main features of the record: date, amount, and description. Everything else gets filed into a JSON structure that goes into an "extra fields" field. The amount is also carefully tuned. Not every institution gives a single "amount" column that is positive when the sum is a credit to you and negative otherwise. Sometimes this convention is reversed, sometimes there are specific "debit" and "credit" columns. In any case, we want all of our records to be one way: negative when money goes out, positive when money comes in.

#### Record Formats

Predefining the format of a CSV allows for a few novel features. One is the ability to set how positive and negative amounts are treated and normalize them on the values as they come into the system. Another is to be able to change this setting and re-import all records from the original document that was uploaded. Record Formats are associated with accounts and credit cards, one of which is chosen as the target at the time of upload. 

A developing feature is smarter Record Format creation, wherein the user only chooses the convention, and the system figures out the column names, creates a new Record Format if it needs to and associates it with the account or credit card you're targeting, or creates a new placeholder account or credit card if you simply tell it the one you need doesn't exist yet. ;

### Group Records automatically, with Rules, or by individual selection

The term "Transactions" here is somewhat nonstandard. A Transaction in this system is not a single bank transaction but rather a single institution, purpose, utility, job, etc. with which a pattern of spending or earning over time can be identified. A Transaction can be recurring, which would cover income from a job, utility or insurance payments, taxes, or even categories of spending, such as groceries, gas or dining out. If you take an annual vacation, that can also be captured as a Transaction - instead of breaking out individual items like plane tickets or hotels you can use historical records from previous vacations and let the system figure out how much you generally spend and account for that annual occurrence as a single Transaction in its projections.

The difference between a Transaction and a Credit Card Expense is mostly whether its associated with a bank account or a credit card. Both are generated from Records, which come from both sources, so it's possible to mix and match Records from either to build either. What's important is to achieve full accounting of the history so the future projection is as accurate as possible.

Transactions and Credit Card Expenses, if you haven't noticed by now, are built on groups of records. A grouping of records should provide the system with enough information to automatically determine most every parameter to define them. A bulk of your activity can be grouped correctly with some portion of the description text, or a date range, and the system will take a pass on its own to try this. The next pass is made by you, defining specific rules against record properties. If a finer grain is required, individual records can be selected to create groups. 

### Build Transactions and Credit Card Expenses from Groups automatically or manually intervening 

Once a group of Records is made, the hard part is over. The system can analyze the Records in a group gather enough information to build a Transaction or Credit Card Expense. You can of course review the work and make any corrections. The source of truth is the set of records themselves. The only other persistent data in the system are the rules you create, groups you manually define with individual records, and the Transactions and Credit Card Expenses you manually create or modify. Everything else is filled in automatically and the entire workflow will adapt as you add new records to the history. This means the more coverage you can achieve with Rules to group records and the less manual intervention you need to take, the more responsive the system will be.




### Manually add any expected future Transactions or Credit Card Expenses
### View a projection of future activity, saving, and growth across your holdings

## Development

All of the meaningful code in this project is ingrained directly in the web framework, however the functionality may be more convenient (certainly from a development perspective) as a command-line tool. This may just be my recent affinity for the Python/Sqlite feature production powerhouse, but in any case the logic can be made more accessible to the terminal without deteriment to the web view and it probably should.

As to features, the original goal of this project was to provide the best path through debt paydown given income and other regular or predictable expenses. Specifically, to know that X extra dollars can be put toward a mortgage principle on day Y without going in the red later on, and to know that the balance will bottom out on day Z, giving the ability to control these parameters a little.

In the course of developing the app to its current state, more elaborate features have come into focus. Say you want to buy a house in the next five years. Given your finances, when will you be able to afford how much of a down payment, and how will your savings grow or shrink with a new mortgage payment, insurance, and property taxes? Mostly this boils down to building projections and tracking the differences made by small changes today.

## Bootstrapping

### Database 

A user and database may be created by connecting as root@172.18.0.1, or whatever docker network root user 
is available, however this root user will not have privileges to grant privileges on that database.
Exec'ing into the container and connecting as root@localhost will allow the full setup.

```
$ docker exec -it frankdb_mariadb /bin/bash
# mariadb -u root -p
MariaDB [(none)]> create user if not exists badger identified by 'badger';
MariaDB [(none)]> create database if not exists budgetbadger;
MariaDB [(none)]> grant all privileges on budgetbadger.* to badger;
```

## Terminology 

Account: any balance of capital, held personally or by a third party
Record: historical statement line items for an Account (generalizable to a Transaction) or CreditCardTransaction (generalizable to a CreditCardExpense)
Transaction: generalized view of a set of Records attributable to an Account, enables future projections for an Account
CreditCardExpense: generalized view of a set of Records attributable to a CreditCardTransaction, enables future projections for a CreditCardTransaction
CreditCardTransaction: specialized Transaction where the amount is comprised of a set of CreditCardExpenses

Record (for an Account) rolls up to *Transaction 
Record (for a CreditCardTransaction) rolls up to CreditCardExpense
CreditCardExpense rolls up to CreditCardTransaction
CreditCardTransaction + other Transactions rolls up to an Account projection

Types of transactions:    
    Debt: any balance of debt, held personally or by a third party
    Income: any source of capital to an account
    CreditCard: 
    Utility:

## Workflow 

As explained earlier, the projection can come from manually entered data and/or by analyzing historical data. From the final "everything is declared" state, building a projection is simply putting all those transactions in order and tracking the balance in each account. Getting everything defined properly is the hard part.

Ideally, a program could read through historical data and be able to identify each utility, category, account, and debt - reliable patterns for all expenses and earnings. It can't, because there's a good bit of noise. It can start by grouping all data by "description". In some cases, this is enough to identify temporally even records with amounts inside a power of ten, roughly satisfying a recurring transaction: name, period, amount, and cycle date. Problems creep up when a single description may identify multiple accounts or spending patterns. Checks, for example, have no description from the bank records. 

Additionally, how should these patterns coalesce within the system? Ideally, of course, all records are easily grouped into patterns which exhibit the necessary features for planning and prediction: schedule and amount. But in reality, scanning historical records will come up with a first attempt which will invariably need to be reviewed and modified by the user. Once approved, a "pattern" can then be included in planning. But these automatic and tweaked patterns will need to be merged in with the ones manually added. And then the patterns identified by rule sets will also need to be included. Should the system automatic pattern identification work directly from rule sets? Should every pattern be required to build from rule sets? 

A pattern can be built from historical records or from nothing - anecdotally. 
If the system can automatically at least attempt to group records, it must be able to translate its "found" parameters into rules.
If the user can anecdotally declare a pattern, there must be some basis by which a rule can include future records in that pattern.
Note that observing a pattern and being able to define deterministic boundaries for that pattern are very different things.

TransactionRule 
- field
- operator
- value 

TransactionRuleSet
- join_operator
- transactionrules 
- records() -> analyze -> ProtoTransaction 

ProtoTransaction 
- name 
- period 
- amount 
- transaction_type 
- transactionruleset_id

Transaction + subtype
- name 
- period
- amount 
- prototransaction_id 

Record 
- description 
- date
- amount 

We can work both ways.. starting from Record, group by description and make a pass on simplistic rules that would create each group.
This can be tested (even!), and then standard record analysis done to produce a ProtoTransaction.
The user can also create a TransactionRuleSet -> ProtoTransaction workflow.
We should be mindful of capturing any one record in multiple groups.. 
The ProtoTransactions can be morphed/cast into their proper Transaction subtypes.
Future records will influence Transactions by way of TransactionRuleSet -> records analysis -> ProtoTransaction

So why have ProtoTransaction at all? Why not just generate the full Transaction subtype from the TransactionRuleSet? Well, that could work. One issue might be that since we have a variety of subtypes, we will want a buffer between the thing that does grouping into "some kind of pattern we can use for projection" and the thing that classes those patterns into behaving this way or that way. What we don't want is a monster block of code that must generalize _and_ classify.

RecordGrouper remains, and with the same initial responsibility: grouping records. But with a group, it must now attempt to define the TransactionRules that would recreate that group. Once a set of rules is found, the TransactionRuleSet is saved and the records are analyzed. The goal of the analysis is to be able to fill in a ProtoTransaction. The new ProtoTransaction has a foreign key back to the TrasnactionRuleSet that provided the records for the analysis that produced it (the ProtoTransaction). Given the transaction_type found in the analysis, the correct Transaction subtype is identified, further analysis is performed if necessary to fill in the subtype characteristics. And we're done.

## Notes from transaction rule sets 

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

## Modeling transaction sets 

family:
    - groceries
    - income 
    - medical 
    - donations
    - credit cards 
    - childcare 
    - internet 
    - phone 
    - vacation / travel 
    - clothing 

property:
    - mortgage 
    - property tax
    - insurance 
    - waste 
    - electric
    - gas 
    - water 
    - rental income 
    - maintenance 
    - repairs 

car:
    - gas 
    - insurance 
    - maintenance / repairs 
    - registration 

### Modeling rental properties 

A single property has a set of standard associated recurring transactions:
    - property taxes
    - insurance 
    - utilities
        - gas 
        - electric 
        - water 
        - sewage
        - waste 
    - condo association fees

Rental property inherits general property transactions and adds:
    - rental income 

Rental properties also have state:
    - is_rented: bool 

Rental property transactions are mutually exclusive depending on state:
    - is_rented=True [ rental income + some utilities ] 
    XOR 
    - is_rented=False [ all utilities ]

Other incidental transactions that may appear as Record/CreditCardExpense or Record/Transaction can be associated with rental properties:
    - maintenance
    - repairs 


Things to classify:
* "intermediary/recurring debt" - credit card, etc.
* rental property
* "single principle" debt - mortgage, etc.



## To-Do's

### 9/12/2022

* when creating a creditcardtransaction from records, capture the calculated "recurring amount" and use it as a waterline against the creditcardexpenses.. the operational "amount" for a creditcardtransaction should always use the sum of its creditcardexpenses, but these should be validated against the historical record
* be able to import a credit card statement CSV, possibly a separate Record* model, and derive CreditCardExpenses in the same fashion as Transactions from Records 
* better filtering and sorting of raw records: hide transaction-associated records, cherry pick records with checkboxes, hide transfers between known accounts
* be able to associate raw records with existing transactions
* better splitting algorithm.. duquesne light heatmap is broken, can't cherry pick
* current method:
    - manually splitting records into a group largely based on description but also maybe cycle date or amount
    - automatic analysis of the group to determine best guess amount, cycle date, period
    - manually confirming these values and creating a transactions from the results (but we can auto-accept the best guess)
    - when new records are added, wipe groups and transactions and re-do the process
    - if new records can be manually associated with existing transactions, the records can be reanalyzed and auto-update the transaction
* proposed change: automate the splitting/group associating, so that new records can fall into the existing buckets (or create new ones) which will trigger re-analysis of all records in the group and auto-updating the associated transaction
    - create a rule to identify current and future records in a group (automating the splitting process)
    - perform an analysis of the group to fill in any characteristics not presupposed by the rule (if the rule supposes description and cycle date range, the amount will need to be calculated. if only description, the cycle date will also need to be calculated)

* define a standard set of expenses scaffold and tag transactions/creditcardexpenses to fill it in. display the scaffold to show where information is missing. (the scaffold may declare "groceries" and if no tags exist for this, it's unaccounted for). per-family expenses, per-property expenses, per-car expenses.

### older 

* chart for generated projections
* separate generated projections line items by type (planned, extra payments, income/expense)
* review need for complex model inheritance 

### Workflow 

Multitenant by Account 
Per Account, a batch of incomes, utilities, other bills are stored at a Version 
Every new upload creates a new Version 
Not every upload will necessarily have enough information to fill in a complete picture of income/expense, so may need to be "the latest version of each biller/account", which means a mapping of actual expected billers/accounts needs to live outside the version purview 

* Set up debts (mortgage, auto, loans) with principal, interest, possibly expected payment schedule but P&I is probably enough 
* File regex patterns to map to expected billers, accounts, etc.
* Download all transactions in CSV format from citizens bank website 
* Upload CSV file directly to the app 
* Review uploaded records to make any manual changes, pre-classifications, regex patterns, etc. 
* App parses and groups records by description, amounts and dates to determine distinct billers, accounts, etc. 
* App scans groups to classify utilities, incomes, and other regular payments, filling in cycle date, frequency, name 
* App files this batch of groups as the next version 
* App produces projections for the next x period 
* Graph produced with overlay datasets

## Logic 

We want to establish 'accounts' - distinct entities with which transactions are 
exchanged. Important to these distinctions are the frequency, cycle date, and 
amount (generally if necessary) exchanged with the account so we can plan 
forward.

Most commonly accounts can be identified 
by 'description' with the exception of checks, which have no description. If
grouped by description, then frequency, cycle date, and amount are determined 
simply by patterns of payment dates and amounts found for that description. 
Checks are more difficult because accounts themselves must be identified 
by patterns found within dates and amounts of the checks themselves.

Possible heuristics for check-account identification:

* find all checks of an amount. find a pattern in the dates. if there's only one 
account for a particular amount, this should be readily identifiable, however 
reality is messy and identification needs to be able to handle missing data 
or shifted dates. if there are multiple accounts, 

When account name, frequency, cycle date, and amount have been identified,
an 'account' type is declared and this ID is written back to the original record.
Again, for records with descriptions, this happens in bulk. For checks, we
take a best guess approach at segmenting and grouping to tag with an account ID.

Batches of records uploaded are written to Records.
Records can be analyzed to generate a set of Accounts.
Some Accounts may already be recorded, some may be new. 
An old Account may have its parameters tweaked by a new analysis.
Some records may have an account ID already assigned, but new analysis
may decide to group it with a different account.
But the account ID of a record has no bearing on planning. Its primary function 
is to ensure each record is only considered to be data for one account.
Information flows from Record -> Account, uni-directional.