# Treasury Department — Audit Exceptions

**Audited entity:** Treasury Department — Money Market and Securities Operations
**Audit period:** 27 September 2023 to 30 June 2026
**Accounting framework:** Plan Comptable des Établissements de Crédit (PCEC) — CEMAC / COBAC

> Exception 7.1.1 was drafted separately. The exceptions set out below are those for which the
> underlying transactions have been examined individually and traced to source entries.

**Risk rating scale:** High · Concern · Moderate

### Summary of exceptions

| Ref. | Exception | Rating |
|---|---|---|
| 7.1.1 | Inconsistent and Unreliable Securities Identification Codes | Concern |
| 7.1.2 | Repurchase Transaction Recorded Without Its Corresponding Cash Settlement | High |
| 7.1.3 | Securities Acquired on Integration Recorded as Central Bank Cash for Six Months | High |
| 7.1.4 | Accrued Interest Carried for Three Years and Written Off as an Operational Loss | High |
| 7.1.5 | Sale and Buy-Back Transactions Accounted for as Outright Disposals | High |
| 7.1.6 | Interface Suspense Accounts No Longer Clearing to Nil | High |
| 7.1.7 | Overstated Clearing of Accrued Interest on Migration to Calypso | High |
| 7.1.8 | Duplicated Interface Postings Remaining Uncorrected | Concern |
| 7.1.9 | Unexplained Difference in Accrued Interest Taken Up at Migration | Concern |
| 7.1.10 | Exposure to Excluded Sovereigns Not Fully Supported by the Explanation Provided | Concern |
| 7.1.11 | Securities Charge Account Used for Items Outside Its Purpose | Concern |
| 7.1.12 | Finance Suspense Account Used for a Large Manual Reversal Campaign and Carrying Integration Residues at Year-End | Concern |
| 7.1.13 | Central Bank Refinancing Recorded as Unsecured Overnight Interbank Borrowing | Concern |
| 7.1.14 | No Impairment Recognised Against the Securities Portfolio | Concern |
| 7.1.15 | Pledged Securities Recorded in Duplicate on the Annual Reporting Date | Moderate |
| 7.1.16 | Securities Transactions No Longer Supported by a Contract Record | High |
| 7.1.17 | Authorisation of Securities Postings Not Evidenced | High |
| 7.1.18 | Portfolio Income Recorded Under the Wrong Accounting Category | High |
| 7.1.19 | Account Balances Contrary to the Nature of the Account at Reporting Dates | High |
| 7.1.20 | Repurchase Transactions Identifiable Only Through Free-Text Narration | Concern |
| 7.1.21 | Securities Repeatedly Recycled with the Same Counterparty, and Gains Recognised on Financing Transactions | Concern |
| 7.1.22 | Repurchase Transactions Recorded Without Accrual and Settled Late | Concern |
| 7.1.23 | Collateral Pledged in Excess of the Outstanding Borrowing | Concern |
| 7.1.24 | Accrued Interest Not Reconciled to the Underlying Contracts | Concern |
| 7.1.25 | Implicit Portfolio Yield Materially Above Contractual Rates | Concern |
| 7.1.26 | Premium and Discount Recognised in Full on Disposal Rather Than Over the Holding Period | Concern |
| 7.1.27 | Cancelled, Pending and Hypothetical Deals Generating Accounting Entries | Concern |
| 7.1.28 | Executed Deals Without Corresponding Accounting Entries | Concern |
| 7.1.29 | Securities Acquired for Customers Transiting the Proprietary Portfolio | Concern |
| 7.1.30 | Contract Lifecycle Exceptions in the Legacy System | Moderate |
| 7.1.31 | Referential Integrity Weaknesses in the Contract Register | Moderate |

---

## 7.1.2 Repurchase Transaction Recorded Without Its Corresponding Cash Settlement

Examination of the bank's repurchase transactions with the Central Bank disclosed one operation
whose repayment was recorded in the General Ledger without the cash movement that should have
accompanied it. Deal 3349072 relates to XAF 90,000,000,000 borrowed from the BEAC from
18 to 26 December 2025 at 5.05%, giving rise to interest of XAF 101,000,000. The drawdown was
posted in full on 23 December 2025. The repayment was posted on 31 March 2026 — ninety-five days
after contractual maturity — and, while it extinguished the liability, recognised the interest
charge and released the pledged securities, no entry was passed to remove the funds from the
Central Bank settlement account.

The omission is confirmed by three independent verifications. Calypso generates two cash
settlement movements for every repurchase transaction — one for the drawdown, one for the
repayment — and 126 of the 129 repurchase transactions recorded during the period carry both.
This is the only matured transaction carrying a single settlement. The amount does not appear
anywhere in the 512,826 accounting lines made available, and the bank maintains a single
settlement account with the Central Bank, so the funds cannot have been released through an
alternative account. Finally, the Calypso interface suspense account carries the exact
counterpart of the omission, XAF (90,101,000,000), representing 95.4% of that account's balance.

The effect differs between the two reporting dates concerned. At 31 December 2025 only the
drawdown had been posted and the suspense account stood at nil; the matter at that date is one of
cut-off, a transaction that matured on 26 December being presented as outstanding, together with
its liability of XAF 90,000,000,000, its pledged securities of XAF 91,333,110,000 and no accrual
of the interest due. The cash overstatement arises on 31 March 2026 and remained uncorrected at
30 June 2026. We further note that the bank passed manual corrections on 14 August 2026 in respect
of two other repurchase transactions carrying interface residues, but none in respect of this one.

| | Amount (XAF) |
|---|---|
| Nominal borrowed | 90,000,000,000 |
| Contractual interest (5.05%, 8 days) | 101,000,000 |
| Expected net effect on the settlement account | (101,000,000) |
| Net effect recorded | 90,000,000,000 |
| **Cash overstatement from 31 March 2026** | **90,101,000,000** |

**Implications:**
- Material overstatement of the bank's cash position with the Central Bank in the financial
  statements at 30 June 2026.
- A matured liability, together with the related pledged collateral, presented as outstanding in
  the annual financial statements at 31 December 2025, with the corresponding interest unaccrued.
- Liquidity ratios and reserve requirement computations derived from an inaccurate settlement
  account balance.
- Failure of the monthly reconciliation of the Central Bank account, which would ordinarily have
  identified a difference of this magnitude within days.

**Recommendations:**
Treasury should obtain the Central Bank statement covering the period, establish the actual date
of disbursement, pass the missing entry and correct the settlement account balance. The effect on
the financial statements at 31 December 2025 and 30 June 2026 should be quantified and referred to
Financial Control for consideration. Treasury should further implement a completeness control
requiring every matured repurchase transaction to carry two cash settlement movements, and a
reconciliation at each reporting date between transactions that have matured and those still
carried in the balance sheet — the daily monitoring of interface suspense balances alone would not
have detected this matter at 31 December 2025, the account then standing at nil.

**Risk Rating: High.**

---

## 7.1.3 Securities Acquired on Integration Recorded as Central Bank Cash for Six Months

The integration of Standard Chartered Bank Cameroon into the bank's records was performed on
5 December 2025 and comprised 131 entries across 53 vouchers, covering the acquired correspondent
accounts, the foreign exchange position and a portfolio of treasury bills of XAF 27,200,000,000
placed in the securities conversion account. The use of a technical migration user, of conversion
accounts and of manual posting is consistent with an integration of this nature and calls for no
observation.

Our review did, however, establish that the conversion account was cleared on 9 December 2025
against the Central Bank settlement account rather than against the securities portfolio. The bank
thereby recorded the receipt of cash at the Central Bank when what it had received was securities,
as the narration itself indicates — *"Securities received from SCB to be booked manually"*. The
position was corrected only on 16 June 2026, when the same amount was credited to the settlement
account and debited to the treasury bills portfolio.

The matter is material to the annual financial statements. At 31 December 2025 the Central Bank
settlement account was reported at XAF 14,182,313,695; adjusted for the securities incorrectly
recorded within it, the account stands at XAF (13,017,686,305), that is to say in a credit
position. The treasury bills portfolio was correspondingly reported at XAF 15,210,000,000 rather
than XAF 42,410,000,000. We also observe that the entry of 16 June 2026 both recognised the seven
acquired securities and recorded their redemption, their discount and their interest in a single
posting, several having matured during the period in which they were carried as cash.

**Implications:**
- The bank's position with its central bank presented in the opposite sense to its actual
  position at the annual reporting date.
- Understatement of the securities portfolio by XAF 27,200,000,000 at 31 December 2025, with the
  related instruments absent from portfolio and maturity monitoring.
- Interest accruing on the acquired securities not recognised in the relevant receivable accounts
  during the period concerned, and the related income not attributable to the correct financial
  year.
- Potential misstatement of the reserve requirement and liquidity ratio reported at that date.

**Recommendations:**
Treasury, together with Financial Control, should quantify the effect on the financial statements
at 31 December 2025 and confirm whether those statements have been amended. The integration file
for the acquired portfolio should be obtained, comprising the schedule of securities transferred,
the valuation applied and the reconciliation with the custodian, and the interest accruing between
the transfer and its recognition should be reconstructed. Management should further confirm that
the remaining components of the integration have been allocated to their definitive accounts and
that no other balance has been left in a transit account.

**Risk Rating: High.**

---

## 7.1.4 Accrued Interest Carried for Three Years and Written Off as an Operational Loss

The bank operates a second accrued interest account, 511800101 *Créances rattachées — manuelles*,
maintained entirely by manual entry in parallel with the automated account. The account was not
included in the initial extraction and was identified only through references to it in the
narrations of other accounts. It carried 1,804 entries during the audit period, representing
XAF 72,917,728,314 in gross movements, of which more than thirteen hundred in 2024 alone.

The last operational movement on the account is dated 12 June 2025, four days before the migration
to Calypso. The clearing entry passed on migration addressed the automated account only, and this
account was left untouched. Its balance of XAF 314,918,217 thereafter remained unchanged, to the
franc, for more than a year.

A single entry was passed subsequently, on 31 July 2026 — that is, after the close of the audit
period. It cleared the account in full under the narration *"Operational Loss on accrued Interest
May 2022 – June 2025"*. The bank has therefore itself characterised the balance as an operational
loss covering more than three financial years, and has recognised it in a single entry falling
outside the period under review. No impairment had been recorded against the balance at any
earlier date.

| Reporting date | Balance (XAF) |
|---|---|
| 31 December 2023 | 1,159,423,914 |
| 31 December 2024 | 791,101,277 |
| 30 June 2025 | 314,918,217 |
| 31 December 2025 | 314,918,217 |
| 30 June 2026 | 314,918,217 |

**Implications:**
- Assets recognised in the financial statements at each of the above reporting dates which the
  bank has since determined to be irrecoverable.
- A loss relating to periods from May 2022 onwards recognised in a single entry in a later
  financial year, raising the question of the correct period of attribution and of a prior-period
  adjustment.
- Two parallel accrued interest circuits, one of them entirely manual, with no reconciliation
  between them and no evidence of periodic review.
- Absence of any impairment assessment over an asset carried at full value for three years.

**Recommendations:**
Treasury should obtain and present the supporting file for the write-off, identifying the
receivables it comprises, the contracts to which they relate and the date from which each became
doubtful, and should determine on that basis the financial year to which the loss is properly
attributable. The reason why the migration clearing entry addressed only the automated account
should be established and documented. Management should further justify the continued operation of
a wholly manual accrued interest circuit alongside the automated one and, where it is retained,
subject it to a documented monthly reconciliation and to the same impairment assessment as the
portfolio itself.

**Risk Rating: High.**

---

## 7.1.5 Sale and Buy-Back Transactions Accounted for as Outright Disposals

Review of the accounting treatment applied to sale and buy-back transactions found that these
operations are recorded as outright sales followed by outright purchases. The portfolio account is
credited on the first leg and debited on the second, no liability is recognised for the cash
received, no interest charge is recorded, and the securities are not disclosed as pledged. Two
hundred and fifteen such transactions were identified during the period, the counterparties being
in every case banks or financial institutions.

Regulation COBAC R-2003/03, as amended by Regulation COBAC R-2010/03, provides that a repurchase
transaction results, for the transferor, in the securities being retained as an asset and in the
recognition of a liability towards the transferee. The bank's own chart of accounts reflects this
treatment, providing dedicated accounts for the liability, the related accrued interest and the
interest charge. None of the seven accounts concerned was moved by any of these transactions.

The economic substance of the transactions was tested independently of the accounting narration.
Where the cash difference between the two legs equals the coupon accrued over the intervening
period, the clean price is necessarily identical on both legs and the repurchase price was
therefore fixed at inception. Fifty-five pairs of legs could be matched on identical security,
counterparty and nominal; in eleven of these the equality is verified to less than one franc, the
implied rate falling on the instrument's stated coupon to two decimal places. On those
transactions no price risk and no issuer credit risk were transferred.

We further note that the transactions are described by the dealing room in the terminology of the
repurchase market — *"SBB"*, *"near leg"*, *"far leg"*, and in places the term, *"for 30 days"* —
and that Calypso provides a dedicated portfolio for buy-sell-back transactions which is not used,
all 215 operations being held in the ordinary investment portfolios.

| Verification | Result |
|---|---|
| Transactions identified | 215 |
| Entries on the seven dedicated repurchase accounts | Nil |
| Matched leg pairs tested | 55 |
| Pairs where the cash difference equals the accrued coupon to under XAF 1 | 11 |
| Interest charge recognised | Nil |
| Liability recognised | Nil |

**Implications:**
- Securities removed from and returned to the balance sheet although they never leave the bank in
  economic terms, with the portfolio reported at each date not reflecting the instruments
  actually held.
- Disposal gains recognised on what are, in substance, financing transactions.
- Understatement of borrowings, and correspondingly of facilities granted where the bank stands
  on the other side, distorting the liquidity and transformation ratios.
- The use of the securities portfolio as collateral not apparent from either the balance sheet or
  the off-balance-sheet disclosures.
- The cost of this funding absorbed within securities income rather than presented as an interest
  charge, contrary to the prohibition on offsetting income and expenses.

**Recommendations:**
Treasury should obtain the master agreements executed with each counterparty and place them, with
the applicable regulation, on the audit file. The qualification of these transactions should be
referred to the external auditors for confirmation, and the effect of restatement as secured
financing on the balance sheet, the net banking income and the prudential ratios should be
quantified for each financial year. The dedicated buy-sell-back portfolio should be made mandatory
for these operations so that they cease to be identifiable only through free-text narration.

**Risk Rating: High.**

---

## 7.1.6 Interface Suspense Accounts No Longer Clearing to Nil

The three suspense accounts through which the Calypso interface passes its entries are intended to
clear to nil once a transaction has been posted in full. Each of them did so initially — sixty-four
occasions were observed across the three accounts, fifty-five on one account alone — which
establishes that the mechanism was correctly configured. Each account nevertheless carries a date
after which it has never returned to nil, the latest being 22 October 2025, and the balances have
since fluctuated without resolving.

The aggregate balance at 30 June 2026 is XAF (133,405,764,689). A detailed reconciliation performed
transaction by transaction accounts for that balance in full, to the franc, across the three
accounts.

| Account | Transactions with a residue | Balance at 30 June 2026 (XAF) |
|---|---|---|
| 467000186 — Calypso Bridge Account | 193 | (42,058,339,493) |
| 467000188 — Calypso Bridge Account Money Market | 8 | (94,451,445,974) |
| 467000243 — Calypso Mirror Trade Bridge Account | 127 | 3,104,020,778 |
| **Total** | | **(133,405,764,689)** |

The balances are not of the same nature. The money market account is explained almost entirely by
the single transaction addressed at 7.1.2. The securities account reflects a diffuse accumulation
across 193 transactions with no dominant item. Sixty-one transactions pass through two suspense
accounts, of which fifty-four clear to nil once both are taken together; their residues should not
be counted twice.

**Implications:**
- Balance sheet accounts carrying, at each reporting date, amounts which represent postings the
  interface has failed to complete rather than any economic position.
- Portfolio, cash and income accounts misstated by the corresponding amounts, since each residue
  represents a leg recorded on one side of an entry and not the other.
- Absence of a detective control: a mechanism which functioned and then ceased to function on an
  identifiable date was not escalated.

**Recommendations:**
Treasury should reconcile the date on which each account ceased to clear against the changes made
to the interface over the same period, the mechanism having operated correctly beforehand. The
detailed reconciliation should be used to allocate each residue to its transaction and to pass the
missing entries, distinguishing postings that are absent from those that have been duplicated.
A daily control over the balance of each suspense account, with escalation where an account has
not cleared within an agreed period, should be implemented and evidenced.

**Risk Rating: High.**

---

## 7.1.7 Overstated Clearing of Accrued Interest on Migration to Calypso

The clearing entry passed on migration credited the accrued interest account with the cumulative
interest accrued since inception on each contract, rather than with the balance remaining on the
account. Coupons already collected on certain contracts, which had already reduced that balance,
were consequently credited a second time. The account was credited with XAF 4,169,123,793 against a
balance of XAF 2,963,891,902 properly due.

The consequence was twofold. The accrued interest account, an asset account, was left with a credit
balance of XAF 1,205,231,891, and the Central Bank settlement account was debited with cash receipts
of the same excess amount. The position persisted for forty-five days and was outstanding at the
reporting date of 30 June 2025.

A correcting entry was passed on 31 July 2025. It debited the accrued interest account with
XAF 1,205,231,891 and credited the settlement account with XAF 1,207,226,407, the difference of
XAF 1,994,516 being charged to the securities commission account. The entry is therefore complete
and balanced; we observe, however, that the residual difference was extinguished as an expense
rather than analysed and allocated.

**Implications:**
- An asset account presented with a credit balance in the financial statements at 30 June 2025,
  a position which cannot arise in the ordinary course.
- Overstatement of the Central Bank settlement account by the same amount at that date.
- Failure of the monthly reconciliation of the Central Bank account over the period concerned.
- A residual difference cleared to an expense account without analysis, precluding any subsequent
  determination of its origin.

**Recommendations:**
Treasury should obtain the financial statements as at 30 June 2025 and confirm whether the credit
balance on the accrued interest account and the overstatement of the settlement account are
reflected in them. The methodology applied to determine the accrued interest to be taken up should
be documented and explained, having been based on the theoretical cumulative accrual per contract
rather than on the accounting balance. The allocation of the residual difference to an expense
account should be supported by the contract-by-contract analysis that ought to have preceded it
and, failing that, reclassified.

**Risk Rating: High.**

---

## 7.1.8 Duplicated Interface Postings Remaining Uncorrected

Testing of the Calypso interface established that certain movements have been posted to the
General Ledger more than once. Seventy-five movements were identified as duplicated over the
extraction, representing XAF 138,888,836,088, of which fifty-three movements and
XAF 34,670,442,550 fall within the audit period. Each duplication affects both legs of the entry
concerned, so that the portfolio, cash and income accounts are all overstated by the corresponding
amount.

Seven of these movements were subsequently corrected by manual entry, between twelve and eighty-five
days after the original posting. The remaining sixty-nine continue to leave a residue in the
accounts, affecting thirty-three accounts, of which twenty-two by a significant amount.

**Implications:**
- Overstatement of portfolio, cash and income balances by the duplicated amounts at each
  reporting date.
- Corrections dependent on manual detection and passed after a considerable delay, no automated
  control being in place to identify a movement posted twice.
- The interface control environment permitting the same movement to be transmitted more than once
  without rejection.

**Recommendations:**
Treasury, together with Information Technology, should identify the cause of the duplication within
the interface and implement a control preventing the retransmission of a movement already posted,
the movement reference being unique in the source system. The residues remaining on the
thirty-three accounts concerned should be quantified and cleared, and a periodic control over
duplicate movement references should be introduced and evidenced.

**Risk Rating: Concern.**

---

## 7.1.9 Unexplained Difference in Accrued Interest Taken Up at Migration

A reconciliation of the accrued interest taken up in Calypso against the interest carried by the
positions actually migrated identified a difference of XAF 364,292,724. Sixty-five positions were
transferred, the nominal being identical on both sides at XAF 126,688,763,333, of which ten are
discount instruments carrying no accrual. The positions migrated carried accrued interest of
XAF 2,725,169,325, whereas XAF 3,089,462,049 was taken up in the new system.

A second and independent difference was also noted. The balance of the originating account to be
cleared was XAF 2,963,891,902, of which XAF 238,722,577 cannot be attributed to any of the
positions migrated. Four hundred and twelve contracts outside the transferred portfolio carried a
residual accrual at that date.

**Implications:**
- Accrued interest recognised in the new system in excess of that supported by the positions
  transferred.
- A residual balance on the originating account which does not correspond to any position carried
  forward, and whose origin has not been established.
- Absence of a position-by-position reconciliation at the point of migration, which would have
  identified both differences at the time.

**Recommendations:**
Treasury should produce the position-by-position justification of the take-up difference, that
being the only basis on which the amount can be allocated and cleared, and should establish the
origin of the balance not attributable to the migrated positions, including the treatment applied
to the four hundred and twelve contracts concerned. Any amount which cannot be substantiated should
be referred to Financial Control for a decision as to its treatment.

**Risk Rating: Concern.**

---

## 7.1.10 Exposure to Excluded Sovereigns Not Fully Supported by the Explanation Provided

The bank has restricted its investment universe to four of the six CEMAC sovereigns, deliberately
excluding Chad and the Central African Republic. Three securities issued by those sovereigns were
nevertheless transacted following the migration to Calypso. Management has explained that the
instruments were acquired on behalf of customers and accordingly fall outside the scope of the
limits.

We have tested that explanation against the Calypso trade referential, which records the portfolio,
the counterparty and the price of each transaction. The explanation is supported in respect of the
two Central African Republic securities, representing XAF 34,200,000: each was purchased from a
correspondent bank and placed with retail customers on the same day, the customers holding the
instruments thereafter.

The explanation is not supported in respect of the Chad security, which represents 98.9% of the
amount concerned. The bank purchased XAF 3,000,000,000 nominal from one credit institution at
99.00 on 26 September 2025 into its own investment portfolio and sold it to another credit
institution at 97.64 on 30 September 2025. No customer held the instrument: the customer legs
present in the system offset one another over the two dates. The position was carried on the bank's
own portfolio for four days and a loss of XAF 10,800,000 was recognised on disposal.

| Security | Sovereign | Nominal (XAF) | Purchased from | Sold to | Test result |
|---|---|---|---|---|---|
| CF2A00000074 | Central African Republic | 22,900,000 | BICEC at 92.00 | Customer at 92.00 | Explanation supported |
| CF2J00000158 | Central African Republic | 11,300,000 | BICEC at 91.00 | Customer at 92.00 | Explanation supported |
| TD2A00000735 | Chad | 3,000,000,000 | SGC at 99.00 | UBC at 97.64 | **Proprietary position** |

**Implications:**
- A proprietary position taken in a sovereign expressly excluded by the risk policy, and a loss
  realised on it.
- Absence of a preventive control in the front-office system to block the capture of an instrument
  outside the authorised universe.
- Monitoring of sovereign limits performed on the legacy referential, which has received no
  entries since the migration, and therefore no longer covering the bank's actual exposure.

**Recommendations:**
Treasury should obtain from the Risk Committee a determination as to whether the sovereign
exclusion policy extends to securities acquired for placement with customers, so that the position
of the placement activity is settled. The investment decision relating to the Chad security should
be produced, together with its level of approval and an explanation of the loss realised. The
first-line control intended to prevent the capture of an instrument outside the authorised universe
should be evidenced, and limit monitoring should be re-established on the Calypso flow.

**Risk Rating: Concern.**

---

## 7.1.11 Securities Charge Account Used for Items Outside Its Purpose

Account 622000100 *Commissions et frais sur titres* is an expense account which the PCEC reserves
for intermediation commissions and custody costs, including the levies of the CEMAC central
depositary. Analysis of the 258 operating entries passed during the period — the three annual
closing entries being excluded as they discharge the account against income in the ordinary course
— found that 139 of them, representing XAF 616,516,632 and 68.8% of the net charge, relate to items
outside that purpose.

The principal component is XAF 626,048,767 of discounts and premiums on securities. A discount is
not a fee: it forms part of the cost of the instrument or of the disposal result and belongs within
securities income or deferred income. The bank has demonstrated the correct treatment itself, having
reclassified XAF 475,250,320 of discount out of this account to *Revenus de bons du Trésor* on
7 March 2025, debiting the income account so that the discount granted on sale reduced the yield on
the instrument. The treatment is therefore understood, and was applied on that one occasion.

The account further carries eighty-three interest adjustments with a net credit effect of
XAF 51,365,791, twenty entries of XAF 34,623,985 bearing no description of the charge they
represent beyond the transaction to which they relate, and twenty-nine entries of a few francs each
totalling XAF 217. We also note XAF 14,199,505 of brokerage commissions charged to named customers
and credited to this expense account.

| Nature | Entries | Net (XAF) | Within the account's purpose |
|---|---|---|---|
| Custody fees | 17 | 122,054,031 | Yes |
| CRCT depositary commissions | 10 | 47,897,564 | Yes |
| Intermediation commissions | 92 | 109,203,239 | Yes |
| Discounts and premiums | 24 | 626,048,767 | No |
| Interest adjustments | 83 | (51,365,791) | No |
| Differences and reclassifications | 12 | 7,209,671 | No |
| Unqualified transaction residues | 20 | 34,623,985 | No |

**Implications:**
- Overstatement of the commissions and fees line in the income statement, with securities income
  and deferred income understated by the corresponding amount.
- Income credited against an expense account, contrary to the prohibition on offsetting income and
  expenses, such that the net balance conveys nothing of the amounts actually transacted.
- No analytical review possible of what the bank pays in commissions and custody fees, and no
  basis on which to reconcile that cost to the statements of the depositary and the
  intermediaries.
- Entries of a few francs indicating differences extinguished rather than explained.

**Recommendations:**
Treasury should reclassify the discounts and premiums to securities income or deferred income as
appropriate, following the treatment the bank itself applied in March 2025, and should cease to
credit customer commissions to this account, such amounts being income and requiring recognition as
such. The unqualified residues should be justified individually. A standard should be established
requiring every entry to this account to carry the contract reference and the nature of the charge,
and the resulting balance should be reconciled annually to the statements of the CRCT, the
depositary and the intermediaries.

**Risk Rating: Concern.**

---

## 7.1.12 Finance Suspense Account Used for a Large Manual Reversal Campaign and Carrying Integration Residues at Year-End

The suspense account maintained by the Finance department, 466000107, is not in the ordinary
course a treasury account. Our review nevertheless identified 839 entries bearing a money market contract
reference or a CEMAC security code, all of which fall within four days in March and April 2024;
outside those four days the account carries no securities entry whatsoever.

Over those four days, 1,313 lines were passed through the account in 683 manual vouchers by four
operators, representing XAF 27,149,606,163 in gross movements. Of these, 1,153 lines amounting to
XAF 25,108,638,427 are reversals affecting 157 distinct contracts. The narrations identify the
objective, referring to the reversal of the manual accrued interest account addressed at 7.1.4;
twelve vouchers move both accounts simultaneously and the balance of that account fell from
XAF 1,032,503,694 to XAF 900,078,802 over the period. The exercise did not complete, the residual
balance having subsequently been written off. We also note that on 9 April 2024 the account stood
at XAF (1,640,165,908), that is in credit on an account designated as debtor, the two legs of the
same correction having been passed two days apart.

A separate matter arises on the balance carried at the reporting date. The account stood at
XAF 1,075,474,620 at 30 June 2026, of which XAF 1,075,318,728 arises from a single entry passed on
31 December 2025 under the narration *"Rclss compte inter branches"*. The nature of that balance is
established by the clearing entry of 25 August 2026, which reverses it in identical terms and
describes it as *"suspense account compte attente Fincon SCB entries on interbranch"*, including an
overdraft on the Standard Chartered New York account. The balance therefore represents unallocated
residues of the integration addressed at 7.1.3, carried in a suspense account for 237 days and
reported within assets at two successive reporting dates.

**Implications:**
- More than XAF 25 billion of securities income reversed and re-recorded by manual entry outside
  any automated processing, with no documentation linking the exercise to an identified decision.
- A suspense account presenting a credit balance of XAF 1.6 billion, contrary to its designation,
  by reason of the two legs of a correction being passed on different dates.
- Integration residues reported within assets at two reporting dates under a narration which does
  not disclose their nature.
- Absence of an ageing and escalation process over suspense account balances.

**Recommendations:**
Treasury and Financial Control should produce the correction memorandum underlying the reversal
campaign, identifying who authorised it, on what diagnosis, and why it was executed by manual entry
rather than by reprocessing. The retention of integration residues in a suspense account at the
annual reporting date should be justified, and the analysis which permitted their clearance in
August 2026 obtained. A clearing rule should be established whereby any suspense account balance
outstanding beyond thirty days is reported, line by line and with its origin, to the Audit
Committee.

**Risk Rating: Concern.**

---

## 7.1.13 Central Bank Refinancing Recorded as Unsecured Overnight Interbank Borrowing

The PCEC provides a dedicated series of accounts for repurchase transactions and for refinancing
obtained from the Central Bank, covering the liability, the related accrued interest, the interest
charge and the associated commissions. None of the thirteen accounts concerned was moved at any
point during the audit period. The single account carrying entries, that for interest on securities
given in repurchase, shows one entry within the period, being the annual closing entry discharging
a charge arising in May 2023.

The bank does record its refinancing with the Central Bank, but within the accounts for overnight
interbank borrowing: XAF 8,253,000,000,000 in gross movements on the borrowing account, an interest
charge of XAF 1,774,823,612, and XAF 10,039,318,740,000 of movements on the off-balance-sheet
account for securities pledged as collateral. The transactions are therefore recorded and the
collateral is monitored; the matter is one of classification.

**Implications:**
- Secured refinancing presented within unsecured interbank borrowing, so that the proportion of
  the bank's funding supported by collateral, and correspondingly the proportion of the portfolio
  which is encumbered, cannot be determined from the balance sheet.
- The entire cost of collateralised refinancing presented as a cost of unsecured borrowing.
- Disclosure of encumbered assets not supported by the underlying accounting classification.

**Recommendations:**
Treasury should obtain confirmation from Financial Control and the external auditors as to the
qualification of Central Bank refinancing, which the off-balance-sheet collateral records indicate
to be secured. Where that qualification is confirmed, the liability should be reclassified within
the dedicated accounts, and the effect on the presentation of the liquidity ratio and on the
disclosure of encumbered assets should be quantified. The dedicated accounts should be configured
within the product's accounting scheme, absent which the correct entry cannot be passed.

**Risk Rating: Concern.**

---

## 7.1.14 No Impairment Recognised Against the Securities Portfolio

None of the provision accounts for the investment portfolio was moved at any point during the audit
period, and the single account carrying entries shows a nil net balance throughout. No impairment
has therefore been recognised against the securities portfolio over three financial years.

The same review identified twenty-six of the thirty-four accounts examined as dormant, including
the off-balance-sheet accounts for securities receivable and deliverable in respect of primary
market intervention and grey market activity, notwithstanding that transactions of that nature are
recorded elsewhere in the accounts.

We note that the absence of impairment stands in contrast to the treatment ultimately applied to
the accrued interest balance addressed at 7.1.4, which was carried at full value for three years
and then written off in a single entry as an operational loss.

**Implications:**
- A sovereign portfolio of material size carried at full value over three financial years with no
  evidence of an impairment assessment.
- Deterioration absorbed in a single write-off in a later period rather than recognised
  progressively, with the corresponding effect on the results of the periods concerned.
- Commitments in respect of securities receivable and deliverable not monitored within the
  off-balance-sheet accounts provided for that purpose.

**Recommendations:**
Treasury and Financial Control should produce the impairment assessment performed at each reporting
date and the conclusion which supported the recognition of no provision. Where no such assessment
exists, one should be established, documented and performed at each reporting date. Management
should also explain why the off-balance-sheet accounts for grey market and primary market
commitments are not used while the corresponding transactions are recorded.

**Risk Rating: Concern.**

---

## 7.1.15 Pledged Securities Recorded in Duplicate on the Annual Reporting Date

Collateral pledged in support of Central Bank refinancing is monitored continuously within the
off-balance-sheet accounts, which carried 1,849 entries during the period. Our review nevertheless
identified four entries totalling XAF 6,200,000,000 passed on 31 December 2025 to a class 2 account
which is not otherwise used, recording four named Cameroonian treasury bonds as pledged. A single
entry reversed them in full on 16 June 2026.

The entries duplicate a monitoring mechanism which exists and operates, without any indication to
the reader of the accounts as to whether the two records relate to the same instruments. We further
note that the reversal does not describe a release of collateral but forms part of the clearing
entry for the Standard Chartered portfolio addressed at 7.1.3.

**Implications:**
- Collateral potentially recorded twice at the annual reporting date, in two separate accounts.
- An entry passed on the reporting date to an account not otherwise used, and reversed thereafter,
  with no evidence of an underlying change in the encumbrance.
- Disclosure of encumbered assets not derived from a single, consistent source.

**Recommendations:**
Treasury should obtain the Central Bank statement of pledged securities as at 31 December 2025 and
reconcile it both to the off-balance-sheet records and to these four entries, so as to establish
whether they duplicate existing records or relate to instruments not otherwise covered. The basis
for the entry should be produced, and a single method for recording pledged collateral should be
adopted and applied consistently.

**Risk Rating: Moderate.**

---

## 7.1.16 Securities Transactions No Longer Supported by a Contract Record

Since the migration of 16 June 2025, no contract record is created in the core banking system for
securities transactions. The money market contract register received its last entry on 12 June 2025
and 1,941 transactions concluded in Calypso since that date exist in the General Ledger as
accounting entries only, with no underlying contract carrying the nominal, the rate, the maturity
and the counterparty.

The structured information ordinarily conveyed by an accounting entry has been lost in the same
movement. Under the legacy module each posting carried one of six amount tags identifying the
nature of the event — principal, interest, accrual, and so forth — whereas the entirety of the
Calypso flow is posted under a single tag, *TXN_AMT*, through one module. The nature of an event
can therefore no longer be determined from the entry itself.

What remains is the narration. Of the 191,417 Calypso entries falling within the audit scope,
25,688 (13%) carry a structured description permitting a transaction to be identified, and 16,019
carry a free-text comment entered by the dealing room. The economic intent of an operation — and in
particular whether a sale is outright or forms part of a repurchase arrangement — is recorded
nowhere else.

**Implications:**
- Terms and conditions of transactions concluded since June 2025 cannot be verified against the
  accounting records, the two being no longer linked.
- Automated controls over the portfolio, over accruals and over maturities cannot operate, the
  data on which they depend being absent.
- The nature of an accounting event cannot be determined from the entry, making reconciliation,
  analytical review and exception reporting dependent on manual interpretation of narration.
- The qualification of transactions — and consequently their accounting treatment — rests on
  free-text entered at the discretion of the dealer.

**Recommendations:**
Treasury, together with Information Technology, should extend the interface so that each Calypso
transaction creates or updates a contract record in the core banking system carrying the nominal,
rate, maturity and counterparty, and so that the nature of the Calypso event is reported in a
structured field of the accounting entry rather than in narration. Pending that development, a
periodic reconciliation between the Calypso deal register and the General Ledger should be
established and evidenced, and the recording of economic intent should be moved from free text to a
mandatory coded field.

**Risk Rating: High.**

---

## 7.1.17 Authorisation of Securities Postings Not Evidenced

The four-eyes control configured in the core banking system does not operate over the securities
flow. All 191,417 entries bearing the Calypso product code — of which 154,480 fall within the audit
period — are captured and authorised under the single technical account CALYPSOUSR, without
exception. Capture and authorisation are therefore performed by the same identity in every case,
and the application control which governs manual entries has no effect on this flow. Since Calypso
itself lies outside the scope of the extractions provided, we are unable to express a view on
whether an equivalent control exists within that system.

We should record that the position is more favourable than the overall figures suggest. Of the
422,968 entries examined, 363,960 (86%) carry the same identifier in capture and in authorisation;
however, 357,465 of these are posted by technical accounts and the remaining 6,495 by end-of-day
batch accounts. **No named individual authorises an entry they have themselves captured.** The
four-eyes principle is therefore observed by operators, and is absent by construction from the
automated flows.

A separate matter concerns entries carrying no authoriser at all. Two thousand five hundred and
fifty-seven entries, forming 1,505 vouchers and representing XAF 858,460,551,906 on the debit side,
carry no value whatsoever in the authorisation field. They are posted exclusively by the technical
account ADMINUSER1 and consist, on examination, of incoming RTGS transfers received from
correspondent banks and of daily clearing house settlement balances, the great majority of which
are posted to the Central Bank settlement account. They are not treasury entries captured by an
operator; they are an automated inbound payment feed. The exception lies in the fact that this feed
posts to the bank's principal settlement account without any authorisation being evidenced, whether
by an individual or by a system account.

Finally, the position is comparable in the upstream system. Of the 3,480 deals recorded in the
Calypso register, 731 (21%) were captured under the generic accounts *calypso_user* and *admin*;
709 carry no identifiable trader, being recorded as *NONE*, *TRADER1*, *0* or *Trader*; and the
register contains no authorisation field of any kind. Two individuals appear under two distinct
labels each, the naming convention not being standardised.

| Population | Entries | Capture and authorisation by the same identity |
|---|---|---|
| Calypso product code | 191,417 | 191,417 (100%) |
| Technical accounts, all sources | 357,465 | 357,465 |
| End-of-day batch accounts | 6,495 | 6,495 |
| Named individuals | — | Nil |
| No authoriser recorded (ADMINUSER1) | 2,557 | Not applicable |

**Implications:**
- No independent authorisation over the securities flow within the core banking system, and no
  assurance obtainable as to whether such authorisation exists in the upstream system.
- An automated payment feed posting to the Central Bank settlement account with no evidence of
  authorisation, so that an erroneous or unauthorised posting would not be detected at the point
  of entry.
- Deals captured in the front-office system under generic accounts and without an identifiable
  trader, precluding any review of dealing authority, of limits by individual or of trading
  patterns.
- Absence of an authorisation field in the deal register, so that the existence of a second review
  before execution cannot be demonstrated.

**Recommendations:**
Treasury should obtain from Information Technology the functional ownership of the CALYPSOUSR and
ADMINUSER1 accounts, the list of individuals permitted to use them and the application audit trail
associated with each, and should establish where the authorisation of the securities flow is
performed and how it is evidenced. Where that authorisation resides within Calypso, its
configuration and the related user access matrix should be obtained and tested. The absence of any
authoriser on the inbound payment feed should be raised with Information Technology and corrected,
the Central Bank settlement account being the bank's principal settlement account. In the upstream
system, deal capture under generic accounts should be discontinued, the trader field made
mandatory, an authorisation field introduced, and the operator naming convention standardised.

**Risk Rating: High.**

---

## 7.1.18 Portfolio Income Recorded Under the Wrong Accounting Category

The PCEC assigns a distinct series of income accounts to each category of securities, so that
instruments held in the trading portfolio give rise to trading income and instruments held in the
investment portfolio to investment income. Testing of the correspondence between the balance sheet
category of each instrument and the income account credited found 41,879 entries recorded under the
incorrect category, against 487 correctly recorded. The predominant case is that of instruments
held in the trading portfolio whose income is credited to investment income, representing 41,705
entries and XAF 8,866,006,400 of income recognised since the migration.

The reclassification performed at migration is relevant to this matter. Positions representing
XAF 126,690,278,772 of nominal were transferred from the investment portfolio accounts to the
trading portfolio accounts on 16 June 2025, the income accounts credited thereafter having remained
those applicable to the former category.

**Implications:**
- Misstatement of the composition of net banking income between trading and investment activities.
- Income recognised in accounts which do not correspond to the balance sheet classification of the
  underlying instruments, affecting segment and regulatory reporting.
- A change in accounting category performed at migration without the corresponding change in
  income recognition, and without evidence of a documented decision supporting the
  reclassification itself.

**Recommendations:**
Treasury and Financial Control should establish and document the intended classification of each
portfolio, obtain the decision underlying the reclassification performed at migration, and align
the income accounts credited with the balance sheet category of the instruments concerned. The
accounting scheme of the Calypso interface should be amended so that the income account is derived
from the portfolio in which the instrument is held, and the income recognised since the migration
should be reclassified accordingly.

**Risk Rating: High.**

---

## 7.1.19 Account Balances Contrary to the Nature of the Account at Reporting Dates

Three accounts within the securities perimeter presented, at a reporting date, a balance in the
opposite sense to that which their nature admits. Two of these are individually significant.

| Account | Nature | Reporting date | Balance (XAF) | Origin |
|---|---|---|---|---|
| 511800100 — Créances rattachées, placement | Debtor | 30 June 2025 | (1,205,231,891) | Over-clearing at migration (7.1.7) |
| 472200106 — Produits perçus d'avance sur bons du Trésor | Creditor | 30 June 2026 | 686,724,016 | Not established |
| 559000101 — Dettes rattachées, prêts et emprunts au jour le jour | Creditor | 30 June 2026 | 66,000,000 | Unmatched reversal |

The first is explained by the migration matter reported separately. The second remains
unexplained and stood at XAF 718,339,497 at the end of the extraction. The third arises from a
single reversal entry passed without its symmetrical counterpart.

**Implications:**
- Balances presented in the financial statements which cannot arise in the ordinary course, and
  which indicate an incomplete or incorrect posting in each case.
- An unexplained debit balance on a deferred income account, increasing over the period, with no
  identified origin.
- Absence of a detective control over the direction of account balances at reporting dates.

**Recommendations:**
Treasury should obtain the justification of each balance at the reporting date concerned and
establish whether it was corrected thereafter, giving priority to the deferred income account,
whose balance has continued to increase. A systematic control should be introduced comparing the
direction of each balance to the nature of the account at every reporting date, with any exception
reported to Financial Control before the accounts are closed.

**Risk Rating: High.**

---

## 7.1.20 Repurchase Transactions Identifiable Only Through Free-Text Narration

Sale and buy-back transactions are identified in the accounting records solely by the comment
entered by the dealing room. Testing the completeness of that identification against the economic
signature of the transactions — the same instrument, the same counterparty, opposing quantities and
a repurchase within a limited period — disclosed 107 such round trips, of which 44, or 41%, carry no
comment identifying them as repurchase transactions. The population identified by narration
therefore understates the activity by a material margin.

We further note that Calypso provides a dedicated portfolio for buy-sell-back transactions, in
which 8 operations are recorded. None of the 215 transactions identified as sale and buy-back is
held within it, all being carried in the ordinary investment portfolios.

**Implications:**
- The population of repurchase transactions cannot be determined reliably, and any restatement or
  disclosure derived from it will be incomplete.
- Transactions whose economic substance is a secured financing indistinguishable, in the records,
  from outright portfolio activity.
- A classification mechanism which exists within the front-office system and is not used, leaving
  identification dependent on discretionary free text.

**Recommendations:**
Treasury should make the use of the dedicated portfolio mandatory for all sale and buy-back
transactions, so that they become identifiable from the system rather than from narration, and
should reclassify the transactions already concluded. A periodic control based on the economic
signature of round trips should be implemented to identify transactions not captured in the
dedicated portfolio.

**Risk Rating: Concern.**

---

## 7.1.21 Securities Repeatedly Recycled with the Same Counterparty, and Gains Recognised on Financing Transactions

Analysis of the sale and buy-back population identified instruments subject to repeated round trips
with the same counterparty. Eighty-two securities are involved in repeated commented transactions
and thirteen in repeated round trips evidenced by the deal register, one instrument having been
recycled nine times. The price of that instrument rises at each iteration, the cumulative
progression amounting to XAF 133,390,410 — a pattern characteristic of a rolled funding position
rather than of successive portfolio decisions.

Because the transactions are recorded as outright disposals, each iteration gives rise to a
recognised gain. The effect on the result of the audit period is XAF 182,465,990, and
XAF 1,045,123,213 over the whole extraction.

**Implications:**
- Income recognised on transactions which, in substance, represent the cost of funding rather than
  a realised portfolio gain.
- Results of individual financial years inflated by amounts arising from the repeated recycling of
  the same instruments.
- Concentration of funding on a limited number of counterparties and instruments not apparent from
  the accounting records.

**Recommendations:**
Treasury should quantify, for each financial year, the result recognised on transactions falling
within the repurchase population and present the effect of its reversal to Financial Control. The
rolled funding positions should be identified and monitored as funding lines, with the associated
counterparty concentration reported to the Asset and Liability Committee.

**Risk Rating: Concern.**

---

## 7.1.22 Repurchase Transactions Recorded Without Accrual and Settled Late

Review of the 129 repurchase transactions concluded with the Central Bank identified three related
weaknesses in their recording.

No interest accrual is recorded on these transactions at any point. Two transactions were
outstanding across a reporting date and the charge not attached to the period concerned amounts to
XAF 63,750,000.

Repayments are in a number of cases recorded well after contractual maturity. Fourteen transactions
were recorded more than five days after maturity, the longest delay being 133 days; the median
delay is one day, so the matter concerns a limited number of transactions rather than the process
as a whole. One liability extinguished contractually, amounting to XAF 90,000,000,000, was still
carried in the balance sheet at a reporting date.

Finally, one transaction of XAF 50,000,000,000 drawn during the period carries no repayment at the
end of the extraction, and the interest recorded on two transactions does not follow from their
contractual terms, giving a cumulative difference of XAF 35,951,388 against a recomputation
performed on an actual/360 basis, which reproduces the interest recorded on the remaining 127.

**Implications:**
- Interest expense not attached to the period in which it arises, affecting the comparability of
  results between reporting periods.
- Liabilities extinguished contractually but still presented in the balance sheet, and
  correspondingly a drawn position with no recorded repayment.
- Interest recorded on certain transactions which cannot be derived from their contractual terms,
  indicating either a capture error or a term not reflected in the records.

**Recommendations:**
Treasury should implement the accrual of interest on repurchase transactions at each reporting
date, without exception for transactions outstanding across the date. A control should be
established requiring every matured transaction to be recorded within an agreed period of maturity,
with escalation beyond it, and the outstanding transaction should be traced to the Central Bank
statement and settled in the records. The interest recorded on the two transactions in difference
should be recomputed and corrected.

**Risk Rating: Concern.**

---

## 7.1.23 Collateral Pledged in Excess of the Outstanding Borrowing

At 30 June 2026 the securities pledged as collateral in support of Central Bank refinancing amounted
to XAF 61,847,170,000 against drawn borrowings of XAF 50,000,000,000, representing a coverage ratio
of 124% and an excess of XAF 11,847,170,000. Securities remain pledged beyond the exposure they
support, the release of collateral not following the repayment of the corresponding borrowing.

**Implications:**
- Understatement of the liquidity reserve available to the bank, instruments being presented as
  encumbered when the borrowing they secured has been repaid.
- Collateral immobilised without economic justification, reducing the securities available for
  refinancing or disposal.
- Absence of a control reconciling pledged collateral to outstanding borrowings.

**Recommendations:**
Treasury should reconcile the securities pledged to the Central Bank against outstanding borrowings
at each reporting date and obtain the release of collateral no longer required. A control matching
the release of collateral to the repayment of the corresponding borrowing should be established and
performed as part of the periodic monitoring of the liquidity reserve.

**Risk Rating: Concern.**

---

## 7.1.24 Accrued Interest Not Reconciled to the Underlying Contracts

Accrued interest recorded on the portfolio was recomputed, contract by contract, for 465 contracts.
The interest recorded amounts to XAF 9,772,608,725 against XAF 9,844,982,264 on recomputation, a
difference of 0.74% overall. Eleven contracts nevertheless present an individual difference in
excess of XAF 5 million. The day-count convention applied is not uniform across the portfolio, three
conventions being in use, of which actual/actual predominates with 198 contracts.

A separate matter concerns the accumulation of accrued interest. At 30 June 2026 the balance of the
accrual accounts represents 1.31 years of coupon at the portfolio's median rate of 6.00%, amounting
to XAF 19,249,608,622. Accrued interest exceeding one full year of coupon indicates coupons accrued
and not collected, or accruals not reversed on collection.

**Implications:**
- Individual accrual balances which cannot be reconciled to the terms of the underlying contracts.
- Day-count conventions applied inconsistently across instruments of the same nature, affecting
  the comparability and accuracy of accrual computations.
- An accrual balance exceeding one year of coupon, indicating either uncollected coupons requiring
  assessment or accruals not reversed on collection.

**Recommendations:**
Treasury should perform and document a contract-by-contract reconciliation of the accrual accounts
at each reporting date, investigating in the first instance the eleven contracts presenting an
individual difference above XAF 5 million. The day-count convention applicable to each category of
instrument should be defined, recorded in the system and applied consistently. The composition of
the accrual balance should be analysed to identify coupons accrued and not collected, which should
be assessed for recoverability.

**Risk Rating: Concern.**

---

## 7.1.25 Implicit Portfolio Yield Materially Above Contractual Rates

The yield implicit in the income recognised on the portfolio was compared to the contractual rates
of the instruments held. The contractual rates do not exceed 7.00% at the 95th percentile, whereas
the implicit yield of the most recent financial year is 15.07%. The difference is present in each
of the years examined and is not attributable to a progressive change in the composition of the
portfolio.

A yield of this magnitude cannot be produced by coupon income alone. It indicates that income of a
different nature — in particular the premiums and discounts addressed at 7.1.26 and the gains
recognised on financing transactions addressed at 7.1.21 — is presented within portfolio income
without distinction.

**Implications:**
- Portfolio income presented in a manner which does not permit coupon income to be distinguished
  from gains of a different nature.
- Performance indicators derived from portfolio income which do not reflect the underlying yield of
  the instruments held.
- Analytical review over the portfolio rendered ineffective, an implicit yield of twice the
  contractual rate not having been identified by first-line monitoring.

**Recommendations:**
Treasury should analyse the composition of portfolio income by nature — coupon, premium and
discount, disposal result — and present each separately in management reporting. The implicit yield
should be computed and compared to contractual rates at each reporting date, with any material
divergence explained before the accounts are closed.

**Risk Rating: Concern.**

---

## 7.1.26 Premium and Discount Recognised in Full on Disposal Rather Than Over the Holding Period

Securities are carried in the portfolio accounts at par, the premium or discount arising on
acquisition being recorded separately in the regularisation accounts. At 30 June 2026 the portfolio
nominal amounts to XAF 244,098,816,666 and the regularisation balance to XAF 585,075,319, giving a
carrying value of XAF 244,683,891,985. We observe that the regularisation balance is in a debit
position at that date, which is contrary to the nature of the account.

The premium and discount are not amortised over the holding period of the instrument. They are
released in full on disposal, giving rise to income of XAF 7,640,766,066 over the audit period and
XAF 12,393,901,859 over the whole extraction.

**Implications:**
- Income recognised at the point of disposal rather than over the period during which the
  instrument is held, with a corresponding effect on the allocation of results between financial
  years.
- Carrying value of the portfolio determinable only by combining two sets of accounts, the
  portfolio accounts alone reflecting nominal rather than cost.
- A regularisation balance presented in the opposite sense to the nature of the account at a
  reporting date.

**Recommendations:**
Treasury and Financial Control should confirm the treatment of premiums and discounts against the
applicable accounting framework and, where amortisation over the holding period is required,
establish the computation and recognise it periodically. The direction of the regularisation
balance should be explained and corrected, and management reporting should present the carrying
value of the portfolio rather than its nominal.

**Risk Rating: Concern.**

---

## 7.1.27 Cancelled, Pending and Hypothetical Deals Generating Accounting Entries

The interface transmits deals to the General Ledger without regard to their status in the upstream
system. Twenty-six deals which did not reach a concluded status nevertheless generated 252
accounting entries representing XAF 68,737,189,808, one of them being a hypothetical deal captured
for simulation purposes. Two of these deals leave a permanent residue in the accounts, the effect on
the result being limited to XAF 82,850.

**Implications:**
- Accounting entries generated by transactions which were never concluded, including a simulation.
- Portfolio and cash balances temporarily reflecting positions the bank never held.
- Absence of a status check within the interface, so that the integrity of the accounting records
  depends on the discipline of deal capture.

**Recommendations:**
Treasury and Information Technology should implement a status check within the interface so that
only deals which have reached a concluded status generate accounting entries, and should establish
that simulations cannot be captured in a manner which permits their transmission. The residues left
by the two deals concerned should be identified and cleared.

**Risk Rating: Concern.**

---

## 7.1.28 Executed Deals Without Corresponding Accounting Entries

The converse case was also tested. Of the 3,480 deals in the Calypso register, 3,229 reached a
concluded status, of which 1,903 relate to portfolios covered by the accounting extraction. Of
those, 435 — representing 23% — carry no accounting entry whatsoever. Restricting the population to
deals negotiated during the audit period, 366 of 1,557 (24%) are in the same position.

**Implications:**
- Transactions concluded in the front-office system and absent from the accounting records, with
  the portfolio, cash and income balances understated accordingly.
- No reconciliation in place between the deal register and the General Ledger capable of
  identifying transmission failures.
- The completeness of the accounting records over securities activity cannot be asserted.

**Recommendations:**
Treasury should establish a daily reconciliation between the deals concluded in the upstream system
and the entries received in the General Ledger, with any difference investigated and cleared before
the following business day. The 435 deals identified should be examined individually to determine
whether the absence of entries reflects a transmission failure or a deal correctly excluded, and
the accounting effect of any genuine omission should be quantified.

**Risk Rating: Concern.**

---

## 7.1.29 Securities Acquired for Customers Transiting the Proprietary Portfolio

Securities placed with customers are first acquired into the bank's own portfolio and subsequently
transferred to the customer desk. Two hundred and two placement transactions were identified,
involving 29 securities, each of which also appears in the proprietary portfolio. The volume
transferred to the customer desk amounts to XAF 35,302,280,281, against placement commissions of
XAF 5,596,771. Customer securities carried off balance sheet at the reporting date amount to
XAF 23,893,110,000, and the mirror suspense account through which the transfers pass stood at
XAF 3,104,020,778 at that date.

**Implications:**
- Instruments acquired for placement indistinguishable, within the portfolio accounts, from those
  held on the bank's own account, so that proprietary exposure cannot be measured directly.
- Issuer and sovereign limits monitored on a portfolio which includes instruments intended for
  customers, as illustrated at 7.1.10.
- A residual balance on the mirror suspense account at the reporting date, indicating placements
  not fully transferred.

**Recommendations:**
Treasury should establish a means of identifying, within the portfolio accounts, instruments
acquired for placement with customers, whether by dedicated accounts or by an attribute carried on
the transaction, so that proprietary exposure can be measured and limits monitored on the correct
basis. The residual balance on the mirror suspense account should be analysed and cleared.

**Risk Rating: Concern.**

---

## 7.1.30 Contract Lifecycle Exceptions in the Legacy System

Examination of the securities contracts recorded in the legacy module before the migration
identified a number of lifecycle exceptions. Of the 446 settlements recorded during the period, 411
were early settlements, which are consistent with liquidity management and are not in themselves
exceptional; 30 occurred at maturity and 5, representing XAF 7,496,000,000, were recorded after
contractual maturity, the longest delay being two days.

Twenty-nine contracts were recorded and settled on the same day. Of these, 21 are disposals
following an actual holding period of up to 13 days, the contract having been captured late; the
remaining 8 are capture cancellations carrying no holding period, which nevertheless introduced
XAF 35,954,100,000 of notional into the records before being reversed.

The treatment of accrued interest on disposal is not uniform. Of the 21 disposals concerned, 9 carry
a reversal of the accrued interest, amounting to XAF 6,869,149, while 12 do not, leaving
XAF 16,406,021 of accrued interest in the accounts.

Finally, 259 sequences were identified in which a contract is closed and reopened on the same day,
for a higher, lower or identical amount. These sequences carry XAF 1,213,821,593,333 of gross
movement against a net cash flow of XAF (33,784,286,667), so that gross volumes derived from these
accounts do not represent flows. Twenty-two contracts were captured more than five days after
negotiation, the longest delay being 30 days.

**Implications:**
- Notional amounts introduced into the records by capture errors and reversed thereafter, without
  the reversal being traceable to an identified authorisation.
- Accrued interest retained in the accounts on disposals where the position no longer exists.
- Gross volumes on the securities accounts which substantially overstate the underlying activity,
  affecting any measure derived from them.
- Contracts captured after negotiation, so that the records do not reflect the position at the date
  it arose.

**Recommendations:**
Treasury should apply a uniform treatment to accrued interest on disposal and reverse the amounts
retained on the twelve disposals concerned. Capture cancellations should be subject to
authorisation and evidenced as such. Contracts should be captured on the day of negotiation, and
any measure of activity derived from these accounts should be established on a net basis, the gross
movement being materially affected by same-day closures and reopenings.

**Risk Rating: Moderate.**

---

## 7.1.31 Referential Integrity Weaknesses in the Contract Register

The money market contract register contains 603 lines for 596 distinct contracts, seven references
being duplicated. The nominal exposed to double counting amounts to XAF 11,039,000,000. Any measure
derived from the register without prior deduplication will therefore overstate the position.

Two contracts, representing XAF 3,500,000,000 of nominal, carry rates which cannot be reconciled to
comparable transactions of the same period and instrument, the difference exceeding ten percentage
points in one case.

**Implications:**
- Position and exposure measures derived from the register overstated by the duplicated contracts.
- Contracts carrying rates which cannot be substantiated by reference to market conditions,
  indicating either a capture error or a transaction requiring specific justification.
- Absence of a uniqueness control over contract references and of a reasonableness control over
  rates at capture.

**Recommendations:**
Treasury should identify the seven duplicated references, determine which record is authoritative
in each case and correct the register. The two contracts carrying divergent rates should be
supported by the dealing confirmation and, where the rate is confirmed, by an explanation of the
terms obtained. A uniqueness control over contract references and a reasonableness control
comparing the rate captured to comparable transactions should be implemented at the point of
capture.

**Risk Rating: Moderate.**

---

## Appendix — Cross-reference to the detailed audit report

| Exception | Detailed report reference |
|---|---|
| 7.1.1 | 11.3 |
| 7.1.2 | 11.8 |
| 7.1.3 | 12.5 |
| 7.1.4 | 12.7 |
| 7.1.5 | 8.2 |
| 7.1.6 | 6.4, 11.6 |
| 7.1.7 | 5.3 |
| 7.1.8 | 6.7 |
| 7.1.9 | 5.2 |
| 7.1.10 | 11.4 |
| 7.1.11 | 12.1 |
| 7.1.12 | 12.3, 3.8 |
| 7.1.13 | 12.2, 7.1 |
| 7.1.14 | 12.6 |
| 7.1.15 | 12.4 |
| 7.1.16 | 6.1, 6.3, 6.6 |
| 7.1.17 | 4.1, 4.2, 6.2, 10.4, 10.5 |
| 7.1.18 | 9.2, 5.5 |
| 7.1.19 | 9.4 |
| 7.1.20 | 8.1, 8.3 |
| 7.1.21 | 8.4, 8.5 |
| 7.1.22 | 7.2, 7.4, 7.5, 7.6 |
| 7.1.23 | 7.3 |
| 7.1.24 | 3.5, 3.7 |
| 7.1.25 | 9.3 |
| 7.1.26 | 11.5 |
| 7.1.27 | 10.2, 10.3 |
| 7.1.28 | 10.1 |
| 7.1.29 | 11.2 |
| 7.1.30 | 2.4, 3.1, 3.2, 3.3, 3.4 |
| 7.1.31 | 2.1, 2.6 |

The following matters recorded in the detailed report have not been raised as exceptions, for the
reasons stated:

- **1.2, 1.3** — extraction integrity; methodological observations bearing on the interpretation of
  the data.
- **1.4, 1.5** — posting conventions differing between the two systems; relevant to the reading of
  the records rather than to the control environment.
- **4.3** — weight of technical accounts in the accounting records; addressed directly by the
  authorisation exception at 7.1.17.
- **4.4** — postings made outside business hours; all ninety-five night-time entries fall on two
  dates only, being the migration date of 16 June 2025 and the reversal campaign of 29 March 2024
  reported at 7.1.12, and 391 of the 432 evening entries fall on those same dates together with
  9 April 2024. They are explained by two identified exceptional events and do not constitute a
  pattern of routine out-of-hours activity.
- **6.5** — daily reversal and reinstatement of accruals by Calypso, which inflates gross volumes
  without affecting the result.
- **9.1** — progression of the result of the activity.
- **11.7** — accounting scheme of the new arrangement, reconstructed and documented.
