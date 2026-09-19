# Carnet de bord — Audit Département Trésorerie

> Journal chronologique des travaux, requêtes exécutées, constats et questions ouvertes.
> Période d'audit : **27/09/2023 → 30/06/2026** (l'énoncé disait « 31 juin 2026 », mois à 30 jours).
> Outil : Python 3 / pandas 3.0.6 en ligne de commande. Tous les identifiants et n° de compte
> sont chargés en **chaînes de caractères** (`dtype=str`) pour préserver les zéros de tête.

---

## Session 1 — Prise de connaissance du dépôt

### 1.1 Inventaire physique
11 fichiers CSV, 97 Mo au total, 1 seul commit par lot de chargement.

| Fichier | Lignes (hors entête) | Rôle présumé |
|---|---|---|
| `MM_CONTRACT.csv` | 603 | Référentiel des **contrats** Money Market (Flexcube) |
| `money_market_transactions.csv` | 59 446 | Écritures comptables du module **MM** Flexcube |
| `calypso_transactions_Export Worksheet_part_1..4.csv` | 194 938 | Écritures déversées par **Calypso** dans le GL Flexcube |
| `FX_TRANSACTIONS.csv` | 48 122 | Écritures **FT** (transferts/change clientèle) |
| `transaction_history_of_key_account_Export Worksheet_part_1..4.csv` | 190 467 | Historique des **comptes clés** (nostri, BEAC, courtier) |

Les fichiers « part_N » sont bien des **découpages** d'un même export : entêtes identiques,
BOM UTF‑8, continuité chronologique. Rechargés par concaténation (`glob` + `concat`).

### 1.2 Schéma commun des fichiers de mouvements
Les 4 sources de mouvements partagent **exactement les 17 mêmes colonnes** (export d'une vue
type `ACVW_ALL_AC_ENTRIES` / `ACTB_HISTORY` Flexcube) :

| Colonne | Signification retenue |
|---|---|
| `DESCRIPTION` | Libellé libre. **Vide en MM**, porteur de toute l'info deal en Calypso |
| `TRN_REF_NO` | Référence de transaction Flexcube (16 car.) — voir codification §1.3 |
| `AC_NO` | N° de compte mouvementé : soit un **compte GL** (9 chiffres), soit un **compte client/nostro** |
| `AC_CCY` | Devise du compte |
| `FCY_AMOUNT` | Montant en devise (renseigné uniquement si compte en devise) |
| `LCY_AMOUNT` | Montant en monnaie locale **XAF** (toujours renseigné) |
| `TRN_DT` | Date comptable de l'écriture |
| `DRCR_IND` | Sens : `D` = débit, `C` = crédit |
| `USER_ID` / `AUTH_ID` | Saisie / validation (contrôle **4-eyes**) |
| `AMOUNT_TAG` | **Étiquette de montant** = nature de l'événement comptable |
| `STMT_DT` | Horodatage (date + heure) de passation |
| `AC_NATURAL_GL` | GL de rattachement quand `AC_NO` est un compte client |
| `PRODUCT` | Code produit Flexcube (4 car.) |
| `AC_GL_DESC` | Libellé du compte |
| `MODULE` | Module d'origine : `MM`, `FT`, `DE`, `RE`, `IC`, `RT`, `LC`, `CL` |
| `EXTERNAL_REF_NO` | Référence système externe — **clé de rapprochement Calypso** |

### 1.3 Codification de `TRN_REF_NO` / `CONTRACT_REF_NO` (décodée et vérifiée)
Format Flexcube sur **16 caractères** :

```
099  OTAP  23  280  0004
└─┬┘ └─┬─┘ └┬┘ └─┬┘ └─┬─┘
 │     │    │    │    └── séquence du jour (4 car., base 36 : 0-9 puis a-z/A-Z)
 │     │    │    └─────── quantième julien (jour de l'année, 001-366)
 │     │    └──────────── année sur 2 chiffres
 │     └───────────────── code PRODUIT (4 car.)
 └─────────────────────── code AGENCE (branch) = 099 = siège
```
**Vérification** : sur les 603 contrats MM, `agence+produit` de la référence = colonnes
`BRANCH`+`PRODUCT` à **100 %**, et la date reconstituée depuis le quantième julien
= `BOOKING_DATE` à **100 %**. La codification est donc certaine.

---

## Session 2 — Référentiel contrats MM (`MM_CONTRACT.csv`)

- 603 lignes, **596 contrats distincts** → **7 références en doublon exact** (lignes
  strictement identiques sur les 16 colonnes) : `099BTTR241940001`, `099OTAP222690002`,
  `099OTAP222690004`, `099OTAP241240006`, `099TBTR223430001`, `099TBTR233110001`,
  `099TBTR233390001`. Artefact d'extraction probable — **à confirmer auprès de l'IT**
  avant tout calcul d'encours (risque de double comptage de 8,0 Md XAF).
- 100 % `BRANCH=099`, `MODULE=MM`, `CURRENCY=XAF`, `PRODUCT_TYPE=L` (**L = Lending /
  placement** : la banque est prêteuse/souscriptrice, pas emprunteuse).

### 2.1 Catalogue produits MM
| Produit | Libellé métier déduit | Nb | Nominal cumulé (XAF) |
|---|---|---:|---:|
| `OTAP` | **O**bligations du **T**résor **A**ssimilables — **P**lacement | 488 | 992 642 023 333 |
| `TBTR` | **T**itres / **B**ons du **T**résor — Transaction | 111 | 194 677 000 000 |
| `BTTR` | **B**ons du **T**résor — Transaction | 2 | 4 000 000 000 |
| `MTPD` | Placement à terme (Money market Term Placement/Deposit) | 2 | 540 000 000 |

### 2.2 Contreparties — 100 % souverains CEMAC
| Code | Contrepartie | Nb contrats | Nominal (XAF) |
|---|---|---:|---:|
| `040730818` | ÉTAT DU CAMEROUN | 232 | 645 587 510 000 |
| `040730820` | ÉTAT DU GABON | 200 | 365 704 623 333 |
| `040730819` | ÉTAT DU CONGO | 122 | 142 113 450 000 |
| `040730821` | ÉTAT DE GUINÉE ÉQUATORIALE | 49 | 38 453 440 000 |

**Constat** : aucune diversification hors souverains CEMAC dans le portefeuille MM historique.
Concentration Cameroun = 49 % du nominal. Point à documenter côté **risque de concentration**.

### 2.3 Dates
`TRADE_DATE` ≤ `VALUE_DATE` ≤ `MATURITY_DATE`, `BOOKING_DATE` = date de saisie système.
Amplitude : trade du 30/06/2022 au **12/06/2025**, maturités jusqu'au **29/05/2030**.
→ Le référentiel MM **s'arrête au 12/06/2025** : cohérent avec la bascule sur Calypso.

---

## Session 3 — Écritures MM Flexcube (`money_market_transactions.csv`)

Période : **27/09/2023 → 16/06/2025**. 100 % `MODULE=MM`, 100 % `XAF`.
29 723 débits / 29 723 crédits — **partie double parfaitement équilibrée**
(vérifié : 0 écriture déséquilibrée sur 24 504 groupes `ref × date × tag`, somme D−C = 0).

### 3.1 Plan de comptes utilisé (PCEC — CEMAC)
| Compte | Libellé | Classe PCEC | Rôle dans le cycle |
|---|---|---|---|
| `511410100` | OBLIGATIONS DU TRESOR ASSIMILABLES PLACEMENT | 51 – Titres de placement | Nominal OTAP |
| `512200100` | BONS DE TRESOR - TRANSACTION | 51 – Titres de transaction | Nominal BTTR/TBTR |
| `512800100` | CREANCES RATTACHEES - TRANSACTION | 51 | Intérêts courus titres de transaction |
| `511800100` | CREANCES RATTACHEES - PLACEMENT | 51 | **Intérêts courus** titres de placement |
| `472200106` | PRODUITS PERCU D'AVANCE SUR BON DE TRESOR | 47 – Comptes de régularisation | Décote/prime BT étalée |
| `733400100` | REVENUS D'OBLIGATIONS ET BONS ASSIM. | 73 – Produits sur titres | Produit d'intérêt OTAP |
| `733200100` | REVENUS DE BONS DU TRESOR | 73 | Produit d'intérêt BT |
| `099ACO00001` | BANQUE DES ETATS DE L'AFRIQUE CENTRALE | Nostro BEAC | **Compte de règlement cash** |

### 3.2 Étiquettes d'événement (`AMOUNT_TAG`) et schémas comptables MM
| `AMOUNT_TAG` | Événement | Occurrences | Schéma (produit OTAP) |
|---|---|---:|---|
| `PRINCIPAL` | **Acquisition** / décaissement du nominal | 840 | **D** 511410100 / **C** 099ACO00001 |
| `INT_BT_ACCR` | **Accrual** quotidien des intérêts courus | 57 446 | **D** 511800100 / **C** 733400100 |
| `PRINCIPAL_LIQD` | **Liquidation** / remboursement du nominal | 894 | **D** 099ACO00001 / **C** 511410100 |
| `INT_BT_LIQD` | Encaissement des intérêts (BT) | 152 | **D** 099ACO00001 / **C** 472200106 |
| `INT_BT_DADJ` | Ajustement de décote à la souscription | 102 | **D** 472200106 / **C** 099ACO00001 |
| `INT_OB_ACCR` | Accrual intérêts (BTTR) | 12 | **D** 512800100 / **C** 733200100 |

Pour les **bons du trésor (TBTR)**, le schéma diffère : l'intérêt court en
**D 472200106 / C 733200100**, c'est-à-dire que le *produit perçu d'avance* (décote
encaissée à l'émission) est **repris au résultat** au fil du temps → traitement de
**titre à revenu précompté** (actualisation de la décote), conforme au PCEC.

### 3.3 Cycle de vie d'un titre sous Flexcube MM
```
1. TRADE_DATE/VALUE_DATE ── PRINCIPAL ──► D 511410100 (portefeuille) / C 099ACO00001 (cash BEAC)
2. chaque jour ─────────── INT_BT_ACCR ─► D 511800100 (courus) / C 733400100 (produits)
   (pour BT : D 472200106 / C 733200100, reprise de la décote)
3. MATURITY_DATE ───────── INT_BT_LIQD ─► D 099ACO00001 / C 472200106   (encaissement coupon BT)
                          PRINCIPAL_LIQD► D 099ACO00001 / C 511410100   (remboursement nominal)
```

### 3.4 ⚠ Constats d'audit — module MM
1. **`511800100` (créances rattachées placement) n'est JAMAIS crédité** sur toute la période :
   24 186 débits, **0 crédit**, solde cumulé **+8 414 808 583 XAF**. Le compte de produits
   `733400100` est crédité du même montant exact (−8 414 808 583). Autrement dit, **aucun
   dénouement de coupon OTAP n'est comptabilisé dans le module MM** : les intérêts courus
   s'accumulent sans jamais être soldés par un encaissement.
   → **Piste d'audit prioritaire** : soit les coupons sont encaissés hors module MM
   (écriture manuelle DE / autre module), soit il existe un **compte d'intérêts courus non
   apuré** — risque de surévaluation de l'actif et du PNB. À rapprocher du fichier des
   comptes clés et de la balance générale.
2. **Volumétrie acquisitions/liquidations** : 341 `PRINCIPAL` OTAP contre 374 `PRINCIPAL_LIQD`
   → plus de liquidations que d'acquisitions sur la fenêtre (normal : titres acquis avant
   le 27/09/2023). Solde net du compte 511410100 sur la période : **−35 293 650 000 XAF**
   (désinvestissement net).
3. **96 % des écritures sont passées par l'utilisateur `SYSTEM`** (56 764/59 446), c'est-à-dire
   par le traitement de fin de journée (EOD). Les écritures manuelles sont le fait de
   5 utilisateurs seulement : `BINEID00087` (1 410), `CHEICHEID059` (912),
   `NDJOCKOS0067` (340), `ELANGUEID060` (16), `DOUMAOS00039` (4).
   → Base de test pour le contrôle de **séparation des tâches** (`USER_ID` vs `AUTH_ID`).
4. Quelques groupes d'écritures présentent un `AMOUNT_TAG` à **montant 0** (`INT_OB_ACCR`,
   total = 0) — écritures techniques à investiguer.

---

## Session 4 — Écritures Calypso (`calypso_transactions_*.csv`)

Période : **16/06/2025 → 18/09/2026**. **194 938 lignes**.
Confirme intégralement la description métier fournie : **Calypso ne déverse que du grand livre**.
- `MODULE` = `DE` (Direct Entry / écriture directe) à **100 %**
- `PRODUCT` = `MNIP` à 100 % (produit technique d'interface)
- `USER_ID` = `AUTH_ID` = **`CALYPSOUSR`** à 100 %
- `AMOUNT_TAG` = `TXN_AMT` à 100 %
→ **Aucun contrat n'est créé dans Flexcube** : la table `MM_CONTRACT` s'arrête bien au 12/06/2025.
→ **Conséquence d'audit majeure** : l'utilisateur `CALYPSOUSR` est à la fois saisisseur et
valideur de 194 938 écritures — le contrôle **4-eyes de Flexcube est neutralisé** sur ce flux.
Le contrôle doit donc être recherché **dans Calypso** (hors périmètre des fichiers fournis).

### 4.1 Codification du champ `DESCRIPTION` (décodée)
4 formats coexistent, identifiés par le nombre de séparateurs `|` :

**Format A — 9 pipes (25 534 lignes) : écritures de flux (deal)**
```
|2693841|22741787|ACCRUAL_BS|Bond|GOGA|ABCM_FVOCI.Bond|GA000002048-7|BondGOGA/GA000002048-7/XAF/0D/03/29/2027/6%|
 └──┬──┘ └──┬───┘ └───┬────┘ └─┬┘ └─┬┘ └──────┬──────┘ └─────┬─────┘ └────────────────┬─────────────────────┘
 TradeId  TransferId  Événement Type Émetteur   Book         Code ISIN/titre      Description du titre
                                                                        Type/Émetteur/Code/Devise/…/Échéance/Taux
```
**Format B — 4 pipes (22 718)** : `VALUATION|<EVENT>|<BOOK>|<CODE_TITRE>|` (valorisation par titre)
**Format C — 2 pipes (141 034)** : `VALUATION|<EVENT>|<BOOK>` (valorisation agrégée)
**Format D — 0 pipe (5 652)** : `TRADE VALUATION/<EVENT>/<BOOK>/`

**`EXTERNAL_REF_NO`** : format `CLP<TradeId>_<TransferId>_<HHMMSS>` — **100 % renseigné**,
et `TradeId`/`TransferId` y sont **identiques à 100 %** à ceux du champ `DESCRIPTION`
(25 534/25 534 vérifiés). C'est donc **la clé de rapprochement Flexcube ↔ Calypso**.
→ **1 985 deals (TradeId)** et **95 139 mouvements (TransferId)** distincts sur la période.

### 4.2 Référentiel des « books » Calypso (portefeuilles)
| Book | Nb écritures | Activité |
|---|---:|---|
| `ABCM_FVOCI.Bond` | 169 896 | Obligations en **juste valeur par OCI** (IFRS 9) |
| `ABCM_FX.Trading.Spot` | 8 482 | **Change au comptant** (trading) |
| `ABCM_MM.Plmt.Tkn.Secured` | 6 886 | **Repo / pension livrée** (emprunt garanti) |
| `ABCM_FVOCI.Bills` | 4 628 | **Bons du trésor** en FVOCI |
| `ABCM_FX.Trading.Fwd` | 2 960 | **Change à terme** |
| `ABCM_MM.FundTransfer` | 1 128 | Transferts de trésorerie entre nostri |
| `ABCM_FI.Sales` | 946 | **Vente de titres à la clientèle** (compte de tiers) |
| `ABCM_BSB.Bond` | 12 | Buy-Sell-Back obligataire |

**Note IFRS/PCEC** : la nomenclature `FVOCI` est **IFRS 9**, alors que le plan de comptes
mouvementé est le **PCEC CEMAC** (511/512 titres de placement/transaction). Il y a donc
une **table de correspondance IFRS → PCEC** implicite dans le paramétrage Calypso,
qu'il faudra obtenir : c'est un point de contrôle (bon classement comptable des titres).

### 4.3 Émetteurs / contreparties Calypso (format A)
`BEAC` (13 490), `ACCESS NIGERIA` (3 320), `ACCESS CAMEROON` (1 880), `STONEXGB` (1 390),
`SGCM` (880), `RETLCUSTCM` (732), `ECOBANKCM` (686), `GOGA` (546), `GOCM` (444), `CCACM` (444),
`UBCM`, `ECOBANKCG`, `GOGQ`, `GOCG`, `BICECCM`, `UBACM`, `ECOBANKGQ`, `AGB CAMEROON`, `UBA CG`,
`SCBCM`, `BGFICM`, `CDCG`, `UGB S.A`, `BACM`, `ECOBANKGA`.
→ Codification : `GO`+pays = **Gouvernement** (GOCM Cameroun, GOGA Gabon, GOCG Congo,
GOGQ Guinée Éq.), puis banques de la place, `BEAC` = banque centrale, `STONEXGB` = courtier FX.
→ **Élargissement net du périmètre contrepartie** par rapport à Flexcube MM
(qui ne connaissait que 4 souverains) : arrivée du **repo BEAC** et des **contreparties bancaires**.

### 4.4 Types de produits Calypso (format A)
`FX` (8 482), `Repo` (6 652), `Bond` (5 420), `FXForward` (2 960), `TransferAgent` (1 128),
`BondMMDiscount` (546), `CA` (346 — *Corporate Action*).

### 4.5 Nomenclature des événements Calypso (`CLP_EVENT`)
| Événement | Nb | Sens métier |
|---|---:|---|
| `ACCRUAL` | 80 216 | Intérêts courus (couru du jour + **contre-passation de la veille**) |
| `PREM_DISC_YIELD` | 79 890 | Amortissement prime/décote au **TIE** (méthode du taux effectif) |
| `CST_S_SETTLED` | 8 286 | **Règlement cash** de l'opération |
| `NOMINAL` | 4 142 | Nominal du titre (entrée en portefeuille / collatéral) |
| `PREM_DISC_AM` | 3 646 | Amortissement prime/décote **linéaire** (bills) |
| `COT` / `COT_REV` | 3 348 / 3 372 | Position de change hors bilan et sa contre-passation |
| `NOMINAL_REV` | 2 666 | Contre-passation du nominal (sortie de collatéral) |
| `TDWAC_ACCRUAL`, `TDWAC_ACCRETION_YIELD/_SL` | 2 544 / 2 544 / 400 | Accrual & accrétion en **coût moyen pondéré** (Trade Date Weighted Average Cost) |
| `PRINCIPAL_DEPOSIT` | 522 | Principal du **repo** (emprunt au jour le jour) |
| `ACCRUAL_BS`, `ACCRUAL_REAL`, `PREM_DISC`, `PREM_DISC_REAL` | 1 050 / 650 / 464 / 102 | Courus au bilan / réalisés à la cession |
| `REALIZED_CLEAN_PL`, `REALIZED_PD_PL` | 300 / 62 | **Plus/moins-values réalisées** (prix pied de coupon / prime-décote) |
| `POSITION_VALUATION` | 164 | Valorisation de la position (provision) |
| `INTEREST` | 258 | Intérêts du repo |
| `NOM_FULL`, `COUPON_CLIP` | 190 / 8 | Nominal plein / détachement de coupon |
| `CM.FISales.BRK_COM`, `TRANSACTION_FEE`, `CM.FXPurchase_Fee` | 98 / 6 / 2 | Commissions |

**Observation structurante** : pour `ACCRUAL` et `PREM_DISC_YIELD`, le nombre de débits et de
crédits sur un même schéma est **quasi symétrique** (ex. 20 155 vs 19 836). Calypso pratique le
**« cancel & rebook »** : chaque jour il contre-passe l'intégralité du couru de la veille puis
repasse le couru cumulé à date. Toute analyse de flux doit donc raisonner **en net**, sinon
les volumes sont artificiellement doublés (3 816 Md XAF d'`ACCRUAL` bruts ≠ charge réelle).

### 4.6 Plan de comptes Calypso — comptes ajoutés par rapport au module MM
| Compte | Libellé | Usage |
|---|---|---|
| `467000186` | **CALYPSO BRIDGE ACCOUNT** | Compte de liaison (suspens) titres |
| `467000188` | **CALYPSO BRIDGE ACCOUNT MONEY MARKET** | Compte de liaison repo/MM |
| `467000243` | **CALYPSO MIRROR TRADE BRIDGE ACCOUNT** | Compte de liaison ventes clientèle |
| `472200108` | AUTRES PRODUITS COMPTABILISÉS D'AVANCE | Prime/décote obligations |
| `512410100` | OBLIGATIONS DU TRESOR ASSIMILABLES **TRANSACTIONS** | Nominal obligations |
| `511210100` | BONS DE TRESOR (BTA) - PLACEMENT | Nominal bills |
| `734400100` / `734200100` | REV. D'OBLIGATIONS / DE BONS (2ᵉ jeu) | Produits — **doublon fonctionnel** avec 733xxx |
| `591400100` | PROV. DÉPRÉCIATION DES OBLIGATIONS ET BONS ASSIMILÉS | Dépréciation |
| `952100100` / `995000100` | Titres affectés en garantie MM / contrepartie **hors bilan** | Collatéral repo |
| `971200100` / `971400100` | Devises achetées / vendues au comptant non encore reçues / livrées | **Hors bilan change comptant** |
| `972400100` / `979000100` | Devises vendues à terme non livrées / compte d'ajustement devises HB | **Hors bilan change à terme** |
| `475000xxx` / `476000xxx` | **Compte de position de change** / **contre-valeur** de la position | Mécanisme PCEC du change |
| `552400100` / `559000101` | Emprunt au jour le jour banques non associées / dettes rattachées | **Passif du repo** |
| `601100100` | INT. SUR OPS MARCHÉ MONÉTAIRE - OPS INTERBANCAIRES | **Charge d'intérêt** repo |
| `938000100` / `998000100` | Valeurs gérées pour compte de la clientèle / de tiers | Hors bilan titres clientèle |
| `725000100` | COMM. GESTION PORTEFEUILLE TITRES CPTE DE TIERS | Commission |
| `452600001` | COMPTE INTER BRANCHES | Liaison inter-agences |

### 4.7 Schémas comptables Calypso par book (extraits vérifiés)

**Obligations FVOCI (`ABCM_FVOCI.Bond`)**
```
Achat      NOMINAL        D 512410100 (titres)        / C 467000186 (bridge)
           PREM_DISC      D 467000186                 / C 472200108 (prime/décote)
Règlement  CST_S_SETTLED  D 467000186                 / C 099ACO00001 (BEAC)
Couru      ACCRUAL        D 512800100 (courus)        / C 733400100 (produits)   [+ contre-passation]
Étalement  PREM_DISC_YIELD D 472200108                / C 733400100 / 734400100  [+ contre-passation]
Dépréc.    POSITION_VALUATION D 734400100             / C 591400100 (provision)
Cession    REALIZED_CLEAN_PL D 472200108              / C 734400100  (+/- value)
```

**Bons du trésor FVOCI (`ABCM_FVOCI.Bills`)** : même logique via `511210100` / `472200106` / `733200100`,
avec amortissement **linéaire** (`PREM_DISC_AM`) au lieu du TIE.

**Repo / pension (`ABCM_MM.Plmt.Tkn.Secured`)** — la banque **emprunte** auprès de la BEAC :
```
Collatéral  NOMINAL      D 995000100 / C 952100100   (hors bilan : titres donnés en garantie)
Principal   PRINCIPAL_DEPOSIT D 552400100 / C 467000188  puis inverse au remboursement
Règlement   CST_S_SETTLED D 099ACO00001 / C 467000188  (encaissement des fonds empruntés)
Couru       ACCRUAL      D 559000101 / C 601100100    (charge d'intérêt + contre-passation)
Échéance    INTEREST     D 601100100 / C 467000188
Restitution NOMINAL_REV  D 952100100 / C 995000100
```
→ Volume **considérable** : 21 984 Md XAF de `PRINCIPAL_DEPOSIT` et 15 535 Md XAF de collatéral
mobilisé sur 15 mois. Le refinancement BEAC est massif et **roulé au jour le jour** (552400100
= « emprunt au jour le jour »). **Point d'audit** : risque de liquidité / dépendance BEAC.

**Change au comptant (`ABCM_FX.Trading.Spot`)**
```
Engagement  COT      D 971400100 (devises vendues non livrées) / C 971200100 (achetées non reçues)
            COT_REV  contre-passation à la livraison
Règlement   CST_S_SETTLED  D <nostro devise> / C 476000102 (contre-valeur)
                           D 475000102 (position de change) / C 476000160 (CV position Calypso)
```
→ Mécanisme PCEC classique : toute opération en devise transite par le couple
**475xxx (position de change, tenu en devise)** / **476xxx (contre-valeur, tenu en XAF)**.
L'écart entre les deux = **résultat de change**.

**Change à terme (`ABCM_FX.Trading.Fwd`)** : idem avec `972400100` / `979000100` en hors bilan.

**Ventes de titres à la clientèle (`ABCM_FI.Sales`)**
```
NOMINAL       D 998000100 / C 938000100   (hors bilan : valeurs gérées pour tiers)
CST_S_SETTLED D <compte client> / C 467000243 (bridge miroir) via 452600001 (inter-branches)
BRK_COM       D 467000243 / C 725000100   (commission de courtage encaissée)
```

---

## Questions ouvertes / à confirmer auprès de la banque
1. Où sont comptabilisés les **encaissements de coupons OTAP** (compte 511800100 jamais crédité) ?
2. Nature exacte des **7 doublons** du référentiel `MM_CONTRACT`.
3. Table de correspondance **classification IFRS 9 (FVOCI) ↔ comptes PCEC** paramétrée dans Calypso.
4. Pourquoi **deux jeux de comptes de produits** (733400100 *et* 734400100, 733200100 *et* 734200100) ?
5. Quel est le **contrôle de validation** (4-eyes) côté Calypso, puisqu'il est neutralisé côté Flexcube ?
6. Le référentiel des **deals Calypso** (l'équivalent de `MM_CONTRACT`) n'a pas été fourni : il est
   indispensable pour rapprocher nominal / taux / échéance des 1 985 deals.

---

## Session 5 — Fichier des comptes clés et fichier de change clientèle

### 5.1 `transaction_history_of_key_account_*.csv` — 190 467 lignes
Fichier **transversal, organisé par compte** et non par module. Il contient les jambes d'écriture
qui touchent les comptes de trésorerie, quel que soit le module d'origine :
`FT` 160 311, `DE` 25 269, `RE` 3 804, `MM` 994, `IC` 36, `RT` 26, `LC` 14, `CL` 13.

Comptes couverts (les « comptes clés ») :
| Compte | Devise | Intitulé | Lignes |
|---|---|---|---:|
| `00110000006` | XAF | STONEX FINANCIAL LIMITED (courtier) | 153 217 |
| `099ACO00001` | XAF | BEAC | 19 166 |
| `099ACO00013` | EUR | SOCIETE GENERALE PARIS | 7 240 |
| `099ACO00011` | USD | UBA AMERICA | 3 405 |
| `099ACO00008` / `099ACO00007` | USD/EUR | ACCESS BANK PLC | 3 374 |
| `099ACO00005` | USD | AFREXIMBANK | 967 |
| `099ACB00001` / `099ACB00002` | EUR/USD | BGFIBANK EUROPE | 1 731 |
| `099ACO00018` | EUR | ODDO BHF | 373 |
| `007ACB00034` / `007ACB00033` | EUR/USD | SCB FRANKFURT / NEW-YORK | 443 |
| `099ACO00014` | EUR | MASTERCARD ACCOUNT | 269 |
| `099ACO00002` | USD | ACCESS BANK UK | 180 |

### 5.2 Le compte STONEX et le produit `LBOT`
Le produit `LBOT` représente **149 872 lignes**, soit 79 % du fichier. Structure invariable :
3 jambes par opération sur le compte `00110000006`, toutes au **débit** :
`AMT_EQUIV` (montant variable) + `LBOT_COMM` (**500 XAF forfaitaires**) + `TDTVA_AMT`
(**96 XAF de TVA**, puis 97 à partir de 2026).
→ **49 947 opérations** sur la période, 114,65 Md XAF, **24,97 M XAF de commissions** encaissées.
Le compte est alimenté en sens inverse par `IN03` (146,1 Md), `MNIP`/Calypso (76,2 Md) et débité
par `RTGS` (142,8 Md). Solde net des mouvements : **−746 691 811 XAF**.

`ADMINUSER1` est saisisseur **et** valideur de 145 734 de ces lignes.

### 5.3 `FX_TRANSACTIONS.csv` — change et transferts clientèle
100 % `MODULE=FT`. Produits : `CSTF` (26 832), `CSBU` (11 744), `IN03` (9 530), `CST2`/`CSTO` (16).
Devises : XAF 33 610, EUR 9 868, USD 4 566, ZAR 40, GBP 38.
Étiquettes : `TFR_AMT` (principal), `AMT_EQUIV` (contre-valeur), `*_HBEAC`/`*_RBEAC` (commissions
BEAC), `TDTVA*_AMT` (TVA).
Comptes structurants : couple **`475000102` / `476000102`** (position de change EUR et sa
contre-valeur, 4 934 lignes chacun), **`475000100` / `476000100`** (idem USD, 2 267 lignes),
`434000142` (taxe sur transfert de fonds), `729000125` (commissions hors CEMAC).
→ Il s'agit du **change clientèle**, à distinguer du change pour compte propre logé dans Calypso.

---

## Session 6 — Contrôles croisés entre les quatre sources

### 6.1 Absence de double comptage
Clé de rapprochement : `TRN_REF_NO | AC_NO | DRCR_IND | AMOUNT_TAG | LCY_AMOUNT | STMT_DT`.

| Périmètre | Lignes |
|---|---:|
| Calypso seul | 192 037 |
| Comptes clés seul | 180 180 |
| MM seul | 58 368 |
| Change clientèle seul | 43 223 |
| FX ∩ comptes clés | 4 899 |
| Calypso ∩ comptes clés | 2 901 |
| MM ∩ comptes clés | 994 |

Les intersections sont exactement celles attendues (jambes sur nostri/BEAC).
**Doublons internes** : MM 84, comptes clés 1 493, Calypso 0, FX 0.

### 6.2 Couverture temporelle et intégrité calendaire
| Source | Début | Fin | Jours distincts |
|---|---|---|---:|
| FX | 2023-09-27 | 2026-09-18 | 709 |
| MM | 2023-09-27 | **2025-06-16** | 436 |
| Calypso | **2025-06-16** | 2026-09-18 | 319 |
| Comptes clés | 2023-09-27 | 2026-09-18 | 756 |

- **0 écriture antérieure au 27/09/2023** → l'extraction est bien bornée au début de période.
- **65 018 lignes postérieures au 30/06/2026** (Calypso 37 566, comptes clés 19 026, FX 8 426)
  → l'extraction déborde la période d'audit ; utile pour les événements postérieurs à la clôture.
- **0 écriture le samedi ou le dimanche** sur 492 973 lignes.
- **18 jours ouvrés sans aucune écriture**, tous identifiés comme **jours fériés camerounais** :
  25/12 (×3), 01/01 (×3), 01/05 (×3), 15/08 (×2), 10-11/02/2025 (Fête de la Jeunesse),
  19-20/05/2025 et 20/05/2026 (Fête Nationale), 29/05/2025 (Ascension), 03/04/2026 (Vendredi Saint).
  → **Aucun trou calendaire inexpliqué.**

---

## Session 7 — Bascule Flexcube → Calypso du 16/06/2025

### 7.1 Mécanique observée
Flexcube : le 16/06/2025, **130 lignes `PRINCIPAL_LIQD`** soldent 65 contrats
(55 obligations + 10 bons) pour **126 688 763 333 XAF**.
Calypso, le même jour : **65 positions réintroduites** (110 lignes `NOMINAL` obligations +
20 lignes bons) pour **126 690 278 772 XAF**, plus **3 089 462 049 XAF** d'intérêts courus repris
via `ACCRUAL_BS` au compte `512800100`.

**Écart de rapprochement : 1 515 439 XAF (0,0012 %)**, intégralement expliqué par une écriture
d'accrétion `734200100` passée le même jour, sans lien avec la migration.
→ **La migration est correctement rapprochée.**

### 7.2 Changement de comptes à la migration
| Avant (Flexcube) | Après (Calypso) | Nature du changement |
|---|---|---|
| `511410100` Obligations — **placement** | `512410100` Obligations — **transactions** | **Changement de catégorie PCEC** |
| `512200100` Bons — transaction | `511210100` Bons (BTA) — **placement** | Changement de catégorie PCEC |
| `511800100` Créances rattachées — placement | `512800100` Créances rattachées — transaction | Changement de compte de courus |
| `472200106` Produits perçus d'avance sur BT | `472200108` Autres produits comptabilisés d'avance | Nouveau compte pour les obligations |
→ À documenter : reclassement volontaire ou effet de paramétrage ? Les règles d'évaluation PCEC
diffèrent entre titres de placement et titres de transaction.

---

## Session 8 — Tests d'audit exécutés

### 8.1 Cycle de vie — tests de bouclage
- **Partie double MM** : 0 écriture déséquilibrée sur 24 504 groupes ; somme D−C = 0. ✔
- **Liquidation = nominal contractuel** : 0 écart sur 447 liquidations. ✔ (mais cf. interprétation)
- **Liquidations à l'échéance** : seulement **30 sur 447 (6,7 %)**.
- **Liquidation/réouverture** : 256 des 331 liquidations anticipées hors migration (77 %)
  sont accompagnées d'un achat le même jour sur la même contrepartie.
  → La trésorerie procède par **clôture intégrale + réouverture du solde**, Flexcube ne gérant pas
  le remboursement partiel. **Les volumes bruts MM ne sont donc pas des flux économiques.**
- **29 contrats créés et liquidés le jour même** : 83 662 200 000 XAF.
  `BINEID00087` 16 (51,55 Md), `CHEICHEID059` 7 (12,15 Md), `NDJOCKOS0067` 6 (19,95 Md).

### 8.2 Test de parité fixe EUR/XAF (655,957)
25 292 lignes EUR testées : **25 152 (99,45 %) exactement à la parité**.
140 écarts, répartis en 4 catégories (sur-parité 39 / sous-parité 17 / non converti 80 / aberrant 4).
Cas matériels documentés au §8.4 du rapport d'exploration.

### 8.3 Test sur le taux USD/XAF
Pas de parité fixe → test par **écart au taux médian du jour**. Trajectoire médiane mensuelle
cohérente (635 en 09/2023 → ~560-570 en 2026), sans rupture suspecte.
*Réserve* : les lignes de commission/taxe produisent des taux implicites dépourvus de sens (jusqu'à
6 408) ; un test fiable doit être restreint aux étiquettes de principal.

### 8.4 Comptes de position de change — bouclage
| Couple | Écart |
|---|---:|
| USD (`475000100`/`476000100`) | **0** |
| EUR (`475000102`/`476000102`) | **0** |
| Hors bilan comptant (`971200100`/`971400100`) | **0** |
| Hors bilan terme (`972400100`/`979000100`) | **0** |
| **Calypso (`475000160`/`476000160`)** | **+2 559 762 955 XAF** |

### 8.5 Pensions livrées BEAC
128 opérations, 5 506 Md XAF tirés, encours net comptable 20 Md au 14/09/2026.
Durées réelles : 99 à 0 jour, 11 à 1 jour, 7 à 2-3 jours, **10 à 6-7 jours**, **1 à 98 jours**,
1 non remboursée (50 Md tirés le 11/05/2026).
Cas `3349072` : 90 Md tirés le 23/12/2025, remboursés le 31/03/2026 ; couru passé **une seule fois**
(75 750 000 le 23/12), **contre-passé le lendemain**, puis aucun couru pendant 97 jours ;
règlement unique de 101 000 000 XAF au dénouement.
Collatéral net mobilisé `952100100` : 77,85 Md, contre 25 Md d'encours → écart ~53 Md.

### 8.6 Démonstration de l'absence de solde d'ouverture
Le cumul des mouvements du compte `552400100` atteint **−5 000 000 000 XAF dès la première
écriture du 07/11/2025** et reste à ce niveau plancher sur 18 dates. Un compte de passif ne pouvant
présenter un solde débiteur, cela établit qu'une opération tirée **avant le début de l'extraction**
y est remboursée → **les fichiers ne contiennent que des mouvements, aucun solde d'ouverture**.
Tous les encours cités doivent être retraités de +5 Md.

### 8.7 Séparation des tâches
| Population | Lignes | Auto-validation (`USER_ID` = `AUTH_ID`) |
|---|---:|---|
| Ensemble | 492 973 | 408 281 (82,8 %) |
| **Utilisateurs nominatifs** | — | **2 lignes** (compte `MIGRATION`, 717 865 477 XAF) |
| Comptes techniques | — | tout le reste |

Principaux comptes techniques auto-validants : `ADMINUSER1` 147 884, `CALYPSOUSR` 2 901 (dans le
fichier des comptes clés ; **194 938 dans le fichier Calypso**), `FLEXSWITCH` 2 506,
`PRIMUSUSR` 1 425, comptes `*EOD` (fin de journée).

**Écritures sans validateur** (`AUTH_ID` vide) : **3 076 lignes, 1 230 913 133 539 XAF**,
toutes par `ADMINUSER1` en module `DE`, réparties continûment d'octobre 2023 à septembre 2026.

Opérateurs humains les plus actifs (tous modules) :
`HARRY000079` 18 659 lignes, `ELANGUEID060` 13 603, `NDJOCKOS0067` 11 505, `YANICKID0057` 9 493,
`CHENID000201` 6 193, `BINEID00087` 5 009 (mais **3 650 Md XAF**, le plus gros montant),
`CHEICHEID059` 4 390.

### 8.8 Autres tests
- **Heures non ouvrables** (avant 7 h / après 20 h) : 68 277 lignes, très majoritairement les
  traitements automatiques (`SYSTEM` 39 890, `ADMINUSER1` 14 236, `CALYPSOUSR` 6 314).
  Opérateurs humains concernés : `HARRY000079` (1 833), `ELANGUEID060` (1 206),
  `YANICKID0057` (729), `NDJOCKOS0067` (150).
- **Montants ronds** : 5,36 % des flux principaux sont des multiples de 1 000 000 XAF —
  proportion normale, aucun signal.
- **Références non conformes** : `191701` et `291807` (6 caractères au lieu de 16), utilisateur
  `MIGRATION`, le 05/12/2025, sur SCB Frankfurt et SCB New-York.

---

## État d'avancement

| Étape | Statut |
|---|---|
| Inventaire et chargement des fichiers | ✔ terminé |
| Décodage de la codification (références, produits, comptes, étiquettes) | ✔ terminé |
| Reconstitution des schémas comptables Flexcube MM | ✔ terminé |
| Reconstitution des schémas comptables Calypso | ✔ terminé |
| Cycle de vie d'un titre (achat → liquidation), deux systèmes | ✔ terminé |
| Rapprochement de la migration du 16/06/2025 | ✔ terminé |
| Contrôles croisés et intégrité des données | ✔ terminé |
| Tests de change (parité EUR, taux USD, position de change) | ✔ terminé |
| Analyse des pensions livrées BEAC | ✔ terminé |
| Tests de contrôle interne (4 yeux, heures, montants) | ✔ terminé |
| **Rapport d'exploration** | ✔ rédigé (`rapport d'exploration.md`) |
| Retraitement des volumes bruts (neutralisation liquidation/réouverture) | ⏳ à faire |
| Reconstitution de l'encours de portefeuille par titre | ⏳ bloqué — référentiel deals Calypso manquant |
| Recalcul indépendant des intérêts courus | ⏳ bloqué — données de marché manquantes |
| Rapprochement avec la balance générale | ⏳ bloqué — balance non fournie |

## Questions ouvertes (mises à jour)
1. Où sont comptabilisés les **encaissements de coupons sur obligations** ? Le compte `511800100`
   n'est **jamais** crédité (8,41 Md XAF de débits cumulés, 0 crédit).
2. Nature des **7 doublons** du référentiel `MM_CONTRACT` (8,0 Md XAF de double comptage potentiel).
3. **Table de correspondance IFRS 9 (FVOCI) ↔ PCEC** paramétrée dans Calypso.
4. Règle d'affectation entre les **deux jeux de comptes de produits** (`733xxx` / `734xxx`).
5. **Contrôle de validation dans Calypso**, puisqu'il est neutralisé côté Flexcube (`CALYPSOUSR`).
6. **Référentiel des deals Calypso** — indispensable, couvre 65 % de la période d'audit.
7. Habilitations de **`ADMINUSER1`** et justification des 3 076 écritures sans validateur.
8. **Politique de taux** appliquée aux opérations clientèle en EUR (marge intégrée au taux ?).
9. Justification du **reclassement placement → transaction** opéré lors de la migration.
10. Constatation du **résultat de change** (écart de 2,56 Md sur le couple `475000160`/`476000160`).
11. Conventions de **pension livrée BEAC** : durée contractuelle, taux, restitution du collatéral.
12. **Balance générale** aux dates d'arrêté — sans elle, aucun solde n'est vérifiable.

---

# SESSION 9 — Seconde extraction : comptes généraux Calypso

**Contexte** : à la suite du constat sur le compte d'intérêts courus jamais apuré, la banque a
fourni une extraction complémentaire des comptes généraux utilisés par Calypso, et a par ailleurs
indiqué avoir vérifié dans le système que **Calypso n'impacte jamais le compte `511800100`**.

`git fetch` + `git merge origin/main` → 3 fichiers, 143 953 lignes :
`calypson_key_account_Export Worksheet_part_1..3.csv`, période 27/09/2023 → 18/09/2026.
Même schéma à 17 colonnes. Fonction de chargement ajoutée : `ckey()` dans `scripts/load.py`.

## 9.1 Apport réel : 30 297 lignes inédites sur 143 953
Recouvrement recalculé sur 5 sources (clé : réf + compte + sens + tag + montant + horodatage) :

| Périmètre | Lignes |
|---|---:|
| Comptes clés seul | 180 180 |
| Calypso seul | 97 453 |
| **Nouvelle extraction ∩ Calypso** | 94 584 |
| MM seul | 53 720 |
| FX seul | 28 821 |
| **Nouvelle extraction seule** | **24 936** |
| Nouvelle extraction ∩ FX | 14 402 |
| Nouvelle extraction ∩ MM | 4 648 |

L'apport principal est l'**historique complet des comptes de position de change 2023-2026**
(`475…`/`476…`), là où la première extraction ne couvrait que la part du module `FT`.

## 9.2 Deux modules inconnus identifiés
**`RE` = RÉÉVALUATION** — 12 437 lignes, tag unique `ACREVALAMT`, produits `ACPO`/`ACRV`,
référence `001ACPO24078`, utilisateurs de fin de journée (`FLEXSWITCH`, `*EOD`).
Écriture-type : `D 475000100 (USD, FCY = 0,00) / C 476000100 (XAF)` — retranslation de la
contre-valeur au nouveau cours, sans modification de la position en devise.

**`RT` = CHANGE AU GUICHET** — 490 lignes, tags `OFS_AMT`/`TXN_AMT`, produits `FXSA` (vente
de devises, 400), `FXPW` (achat, 82), `FXSW` (swap, 2). Utilisateurs = **caissiers nominatifs**,
population distincte de la salle des marchés.

## 9.3 ⚠ La réévaluation ne touche aucun compte de résultat
Sur 12 437 écritures de réévaluation, **aucune ne mouvemente un compte de charge ou de produit**.
Tout se boucle entre `475…` et `476…`. Écritures équilibrées (résidu global 99 407 XAF).

| Devise | Compte de contre-valeur | Lignes | Réévaluation nette cumulée |
|---|---|---:|---:|
| USD | `476000100` | 5 428 | **+3 536 553 336 XAF** |
| EUR | `476000102` | 769 | −253 064 562 XAF |

Volatilité mensuelle marquée sur l'USD : +273,9 M (12/2023), −246,3 M (08/2024), +636,9 M (10/2025),
+251,3 M (07/2026). La quasi-nullité du compte EUR est cohérente avec la parité fixe.
→ Soit le résultat de change est viré par une écriture hors périmètre, soit il n'est pas constaté.

## 9.4 ⚠ Découverte majeure : 22 847 commentaires libres de la salle des marchés
Le champ `DESCRIPTION` au format 9 pipes comporte un **dixième champ** jusqu'ici vu comme vide :
il contient en réalité un **commentaire libre saisi par l'opérateur**.

| Catégorie | Lignes | Deals | Montant (XAF) |
|---|---:|---:|---:|
| Alimentation de compte | 4 724 | 509 | 1 051 263 605 798 |
| FX DEAL avec marge explicite | 4 554 | 208 | 2 402 811 854 548 |
| Autres | 3 652 | 233 | 3 209 684 175 340 |
| **SBB (Sell-Buy-Back)** | 1 675 | 215 | 3 767 467 539 902 |
| Achat | 687 | 85 | 1 173 505 810 996 |
| Vente | 630 | 85 | 339 821 505 362 |

C'est une **source de preuve sur l'intention économique**, invisible dans les seuls schémas
comptables.

## 9.5 ⚠ 215 Sell-Buy-Back comptabilisés en cession ferme
Commentaires explicites : `NEAR LEG SBB WITH CCA`, `FAR LEG SBB WITH SOCGEN`,
`FIRST LEG OF SBB WITH SOCIETE GENERALE CMR`.
Jambes : 94 deals `NEAR`, 98 `FAR`, 6 `FIRST`, 2 `SECOND`, 15 non précisées.

Comptabilisés dans `ABCM_FVOCI.Bond` / `ABCM_FVOCI.Bills` avec les événements d'une acquisition et
d'une cession fermes (`NOMINAL`, `CST_S_SETTLED`, `PREM_DISC`, `REALIZED_CLEAN_PL`) — **et non**
dans le book de pension `ABCM_MM.Plmt.Tkn.Secured`.
**896 125 677 223 XAF réglés sur 214 deals**, du 25/11/2025 au 18/09/2026.
Plus-values de cession constatées : **193 486 200 XAF** (`REALIZED_CLEAN_PL`).

Contreparties : `ECOBANKCM` 68, `CCACM` 64, `SGCM` 53, `BICECCM` 8, `ECOBANKCG` 8, `ECOBANKGQ` 6,
`UBCM` 4, `CDCG` 2, `UBACM` 1, `ECOBANKGA` 1.

**Preuve du caractère roulé** — titre `CM2J00000196`, contrepartie `SGCM`, 9 allers-retours du
09/01 au 06/04/2026, à prix croissant :
9 556 934 932 → 9 560 653 856 → 9 568 321 918 → 9 569 803 918 → 9 594 349 315 → 9 619 754 788 →
9 667 551 370 → 9 668 634 370 → 9 690 325 342 XAF (cumul 86 496 329 809).
Autres : `CM2B00000228`/SGCM 7 rotations, `GA2B00000109`/ECOBANKCM 5, `GQ2J00000057`/CCACM 4.

## 9.6 CORRECTION du constat §8.5 — comptes `475000160` / `476000160`
Test de la devise de tenue contre l'intitulé :

| Compte | Intitulé | Devise | `FCY_AMOUNT` | Verdict |
|---|---|---|---|---|
| `475000100` | position USD | USD | 10 594/10 594 | conforme |
| `476000100` | contre-valeur USD | XAF | 0/10 593 | conforme |
| `475000102` | position EUR | EUR | 10 172/10 172 | conforme |
| `476000102` | contre-valeur EUR | XAF | 0/10 171 | conforme |
| **`475000160`** | **position CALYPSO** | **XAF** | **0/494** | **se comporte en contre-valeur** |
| **`476000160`** | **contre-valeur CALYPSO** | **EUR/USD** | **855/855** | **se comporte en position** |

De plus les deux comptes **n'apparaissent jamais dans la même écriture** (494 contre 855, aucune
commune). Ce ne sont donc pas un couple mais **deux comptes de liaison distincts** :
`476000160` travaille avec les positions EUR/USD et les nostri ; `475000160` avec la BEAC (413),
STONEX (77), l'inter-branches (154) et `625000105`.
→ L'écart de 2 559 762 955 XAF n'a pas la signification qui lui était prêtée.
→ **Ce qui subsiste** : les intitulés des deux comptes sont **inversés** par rapport à leur usage.

## 9.7 Position de change — bouclage confirmé, 2 devises de plus
Couverture complète 2023-2026, modules `FT`+`DE`+`RE`+`RT` :

| Devise | Position | Contre-valeur | Écart |
|---|---:|---:|---:|
| USD | −7 292 487 618 | +7 292 487 618 | **0** |
| EUR | −35 503 790 493 | +35 503 790 493 | **0** |
| GBP (`…106`, dès 03/02/2026) | +610 490 400 | −610 490 400 | **0** |
| ZAR (`…150`, dès 03/11/2023) | +639 456 600 | −639 456 600 | **0** |

## 9.8 Rétrocessions sur rapatriement d'exportation
285 deals, **56 873 780 557 XAF réglés**, du 16/06/2025 au 18/12/2025.
Taux : 70 % (193 deals), 100 % (65), 30 % (7), 30 % **« DOSSIER NON EXECUTE »** (13), **79 % (1)**.
→ Volet **réglementation des changes CEMAC**. Points à instruire : les 13 dossiers non exécutés,
le taux atypique de 79 %, et l'arrêt des commentaires au 18/12/2025 alors que l'activité continue.

**Correction de lecture** : les pourcentages 70/100/30 extraits des commentaires sont des taux de
rétrocession réglementaire, **et non des marges de change** — première lecture erronée, rectifiée.

## 9.9 Marges de change négociées — corroboration du §8.4
Commentaires du type `FX DEAL 05/09/2025 0.15PCT` :

| Marge | Deals | Lignes | Montant (XAF) |
|---|---:|---:|---:|
| 0,10 % | 8 | 140 | 209 950 845 080 |
| 0,12 % | 1 | 16 | 26 238 280 000 |
| **0,15 %** | **52** | **968** | **992 135 618 450** |
| 0,20 % | 8 | 132 | 135 153 380 280 |
| 0,25 % | 1 | 16 | 15 752 807 356 |
| 0,50 % | 1 | 40 | 65 595 700 000 |

Les taux EUR relevés au §8.4 (656,678553 et 656,744149) correspondent à **+0,110 %** et **+0,120 %**
par rapport à 655,957 → cohérent avec les marges documentées. La pratique d'intégration de la marge
au taux de conversion comptable est donc **établie et systématique**.

## 9.10 Découverte technique — les contre-passations sont des montants négatifs
Flexcube corrige par un **débit de montant négatif**, non par une écriture de sens inverse.

| Source | Lignes | `LCY_AMOUNT` négatif |
|---|---:|---:|
| FX | 48 122 | 294 |
| MM | 59 446 | 378 |
| CKEY | 143 953 | 138 |
| KEY | 190 467 | 45 |
| **CLP (Calypso)** | 194 938 | **0** |

Calypso, lui, contre-passe par écriture inverse (« cancel & rebook »). **Conventions opposées** :
à prendre en compte dans tout rapprochement.
→ Le §8.1 a été reformulé : `511800100` compte **24 035 débits positifs (8 612 544 476)** et
**151 débits négatifs (−197 735 893)**, solde net inchangé à **8 414 808 583**.

## 9.11 ⚠⚠ Le compte `511800100` : réponse définitive
La banque indique que Calypso n'impacte jamais ce compte. **Les fichiers le confirment
intégralement** :

| Test | Résultat |
|---|---|
| Lignes `CALYPSOUSR` | **0** |
| Lignes module `DE` | **0** |
| Lignes produit `MNIP` | **0** |
| Présence dans la nouvelle extraction | **absent** (seul `511210100` y figure en classe 511) |
| Dernier mouvement | **16/06/2025** (jour de la migration) |
| Immobilité au 18/09/2026 | **459 jours** |

Ventilation des 24 186 lignes, toutes au débit : `SYSTEM` 23 877 (8 406 983 999 XAF),
`BINEID00087` 154, `CHEICHEID059` 143 (−2 955 393), `ELANGUEID060` 4, `NDJOCKOS0067` 8.

**Le compte n'a pas été soldé à la migration : il a été abandonné.**

### Test décisif — double comptabilisation des courus
Sur les **65 contrats migrés le 16/06/2025** :

| Élément | Montant (XAF) |
|---|---:|
| Courus accumulés sur `511800100` pour ces 65 contrats | **4 121 144 342** |
| Courus **re-comptabilisés par Calypso** en `512800100` le 16/06 (`ACCRUAL_BS`, 55 lignes) | **3 089 462 049** |
| Écart | 1 031 682 293 |

→ Calypso a **reconnu de nouveau 3,09 Md XAF de courus** sur des positions dont les courus étaient
déjà portés, et jamais apurés, en `511800100`. Sauf écriture manuelle hors périmètre, **les mêmes
intérêts courus figurent deux fois à l'actif**.
→ L'écart de 1,03 Md correspond vraisemblablement aux **coupons qui auraient dû apurer le compte**
et ne l'ont jamais fait (Calypso ne reprend que le couru depuis le dernier détachement).

### Comparaison avec l'équivalent Calypso
| Compte | Débits | Crédits | Solde net | Apurement |
|---|---:|---:|---:|---|
| `511800100` (Flexcube MM) | 24 186 | **0** | +8 414 808 583 | **aucun** |
| `512800100` (Calypso) | 21 358 | 20 841 | +23 096 148 281 | normal |

→ **L'anomalie est strictement localisée au module MM de Flexcube**, période 27/09/2023 →
16/06/2025, et **figée depuis**.

---

## État d'avancement (mis à jour)

| Étape | Statut |
|---|---|
| Exploration initiale (4 fichiers) | ✔ terminé |
| Seconde extraction (comptes généraux Calypso) | ✔ terminé |
| Identification des modules `RE` et `RT` | ✔ terminé |
| Exploitation des commentaires libres (22 847 lignes) | ✔ terminé |
| Caractérisation des Sell-Buy-Back | ✔ terminé |
| Réponse sur le compte `511800100` | ✔ tranché — double comptabilisation démontrée |
| Correction des constats §8.1 et §8.5 | ✔ terminé |
| **Rapport d'exploration v2** | ✔ mis à jour (`rapport d'exploration.md`, §11) |
| Retraitement des volumes bruts | ⏳ à faire |
| Quantification du coût de financement implicite des SBB | ⏳ à faire |
| Reconstitution de l'encours par titre | ⏳ bloqué — référentiel deals Calypso manquant |
| Solde réel du compte `511800100` | ⏳ bloqué — extraction tous modules manquante |
| Rapprochement avec la balance générale | ⏳ bloqué — balance non fournie |

## Questions ouvertes (mises à jour)
1. **[PRIORITÉ MAXIMALE]** Solde réel de `511800100` aux dates d'arrêté et existence éventuelle
   d'une écriture d'apurement hors module MM. Double comptabilisation de 3,09 Md à confirmer.
2. **[PRIORITÉ HAUTE]** Doctrine comptable des **Sell-Buy-Back** : conventions-cadres, position du
   commissaire aux comptes, incidence sur les ratios prudentiels.
3. **[PRIORITÉ HAUTE]** Constatation du **résultat de change** : mouvements des comptes 63/73 du
   PCEC, procédure de virement du résultat de réévaluation.
4. Référentiel des **deals Calypso** (couvre 65 % de la période).
5. Paramétrage des comptes `475000160` / `476000160` (intitulés inversés).
6. Habilitations `ADMINUSER1` et justification des 3 076 écritures sans validateur.
7. Conventions de **pension livrée BEAC** et durées contractuelles réelles.
8. Politique de taux appliquée au change clientèle (marge intégrée au taux de conversion).
9. Dossiers de rétrocession **« non exécutés »** et taux atypique de 79 %.
10. Arrêt des commentaires de rétrocession au 18/12/2025.
11. Table de correspondance **IFRS 9 ↔ PCEC** paramétrée dans Calypso.
12. Règle d'affectation entre les comptes `733xxx` et `734xxx`.
13. Nature des **7 doublons** de `MM_CONTRACT`.
14. Justification du **reclassement placement → transaction** lors de la migration.
15. **Balance générale** aux dates d'arrêté.

---

# SESSION 10 — Historique complet du compte 511800100 : le constat est infirmé

**Contexte** : sur demande, la banque a fourni `creance_rattaché.csv` — l'historique intégral du
compte d'intérêts courus, **tous modules confondus**, 32 937 lignes, **16/08/2022 → 31/07/2025**.

**Difficultés techniques de chargement** (résolues) :
- fichier encodé en **CP1252** et non UTF‑8 → 43 octets `0xA0` (espaces insécables) faisaient
  échouer la lecture ; chargement en `cp1252` puis nettoyage des `\xa0` ;
- format de date **`JJ-MMM-AA`** (`16-AUG-22`) différent des autres extractions ;
- montants avec **décimales** (les autres fichiers sont en unités entières).
→ Fonction `cr()` ajoutée à `scripts/load.py`.

## 10.1 ⚠ LE CONSTAT DES SESSIONS 3 ET 9 EST INFIRMÉ

| Contrôle | Résultat |
|---|---|
| Débits | 32 136 lignes — 15 005 402 277,00 XAF |
| **Crédits** | **801 lignes — 15 005 402 277,00 XAF** |
| **SOLDE NET** | **0,00 XAF** |

**Le compte est intégralement apuré.** Les crédits existent, en **module `DE`** — invisibles dans
la première extraction filtrée sur `MODULE='MM'`.

**Origine de l'erreur** : j'avais conclu à l'absence d'apurement à partir d'une extraction ne
contenant que le module MM. L'hypothèse alternative avait bien été posée dès le §8.1 du rapport
(« les coupons sont encaissés hors du module MM ») et c'est l'extraction demandée qui tranche —
en faveur de la banque. Constats §8.1 et §11.10 **retirés** du rapport (conservés barrés, pour la
piste d'audit).

## 10.2 Mécanique réelle d'apurement
Contrepartie des 801 crédits retrouvée dans les autres fichiers : **compte BEAC `099ACO00001`**
(499 débits, 31 309 830 000 XAF) et `472200106` pour les bons. **Les coupons sont bien encaissés.**

```
② chaque jour (MM, automatique)   D 511800100 / C 733400100
③ au détachement du coupon (DE, MANUEL) D 099ACO00001 / C 511800100
```

## 10.3 Profil du compte — sain
| Date | Solde (XAF) |
|---|---:|
| 31/12/2022 | 235 739 034 |
| 31/12/2023 | 662 336 797 |
| 30/06/2024 | 1 975 466 036 |
| 31/12/2024 | 2 455 219 083 |
| **max — 22/05/2025** | **3 298 021 048** |
| 13/06/2025 | 2 927 747 645 |
| **16/06/2025** | **−1 205 231 891** |
| **30/06/2025 (arrêté)** | **−1 205 231 891** |
| 31/07/2025 | **0** |

Le compte monte entre deux coupons et retombe à chaque encaissement : profil attendu.

## 10.4 Contrôle interne sur les apurements — satisfaisant
- auto-validation : **0 / 801** ; sans validateur : **0 / 801**
- 7 saisisseurs (`BINEID00087` 431, `CHEICHEID059` 264, `NDJOCKOS0067` 52, …),
  7 valideurs (`MBATOHID0012` 577, `CELESID0018` 124, `MBOGID000083` 69, …)
- libellés très documentés : contrat + code titre + nominal + couru + taux, ex.
  `099OTAP242490004 GA2B00000109 4000000000 194299723 6.25 %`

**Observation résiduelle** : apurement **entièrement manuel** (801 écritures en 3 ans) alors que le
module MM dispose de `INT_BT_LIQD` (utilisé pour les bons, **jamais pour les obligations**).
Fragilité opérationnelle, aujourd'hui bien contrôlée.

## 10.5 ⚠ NOUVEAU CONSTAT — sur-apurement de 1,2 Md à la migration
Écriture `099001b251670001` du 16/06/2025 (`CHEICHEID059` / `MBATOHID0012`), 55 lignes :

| Élément | Montant (XAF) |
|---|---:|
| Solde au 13/06/2025 | 2 927 747 645 |
| Courus du 16/06 | 36 144 257 |
| **Solde réel à apurer** | **2 963 891 902** |
| **Crédit passé** | **4 169 123 793** |
| **SUR-APUREMENT** | **1 205 231 891** |

**Cause** : l'écriture a crédité, par contrat, le **cumul des courus depuis l'origine**, sans
déduire **les coupons déjà encaissés**.
Exemple `099OTAP232130001` : cumul 353 424 658 ; coupon déjà encaissé 181 572 816 ; solde réel
171 851 842 ; crédité 353 424 658 → **181 572 816 de trop**.
**23 des 55 contrats** concernés, écart cumulé niveau contrat **1 444 094 752 XAF**.

**Double conséquence** :
1. compte d'**actif en solde créditeur** de 1 205 231 891 XAF ;
2. contrepartie = **débit du nostro BEAC** → **BEAC surévalué de 1,2 Md** sur la même période.

**Durée : 45 jours** (16/06 → 30/07/2025), **arrêté semestriel du 30/06/2025 traversé**.
Correction le **31/07/2025** : `099000b252120001` (`NDJOCKOS0067` / `MBATOHID0012`),
libellé **« ACCRUALS LIQUIDATION RELATED TO CALYPSO GO LIVE »**,
D `511800100` 1 205 231 891 / C `099ACO00001` 1 207 226 407.
→ écart de **1 994 516 XAF** entre les deux jambes : une **troisième jambe** existe, non identifiée.

## 10.6 Contrôle positif — exactitude des courus
`099OTAP243480002` : 4 000 000 000 à 6,70 %, 185 jours → attendu 135 890 411, comptabilisé
135 797 500 (écart 0,07 %, convention de jours). Le calcul des courus est exact.
Sur les 55 contrats migrés : 31 sans coupon encaissé, 24 avec un coupon — cohérent avec des titres
acquis en 2024-2025 à coupon annuel. **Aucun indice d'arriéré des États émetteurs.**

## 10.7 Enseignement de méthode (important pour la suite)
**Une extraction filtrée par module peut faire apparaître une anomalie qui n'existe pas.**
Le module `DE` porte les opérations structurantes : apurement des coupons, corrections, migration.

> **Règle retenue** : tout constat sur le solde ou le comportement d'un compte doit être établi sur
> une extraction **du compte, tous modules confondus**.

**Constat à re-confirmer selon cette règle** : le §11.4 (réévaluation de change sans impact
résultat) repose sur l'extraction des comptes `475`/`476`. La contrepartie en compte de résultat
pourrait, comme ici, se trouver dans un module non extrait. → demander l'historique des comptes de
gains et pertes de change (classes 63/73), tous modules.

---

## État d'avancement (mis à jour)

| Étape | Statut |
|---|---|
| Exploration initiale (4 fichiers) | ✔ terminé |
| Seconde extraction (comptes généraux Calypso) | ✔ terminé |
| Troisième extraction (compte 511800100, tous modules) | ✔ terminé |
| **Constat sur les créances rattachées** | ✔ **tranché — constat initial infirmé** |
| Sur-apurement de 1,2 Md à la migration | ✔ établi et quantifié |
| **Rapport d'exploration v3** | ✔ mis à jour (`rapport d'exploration.md`, §12) |
| Re-confirmation du §11.4 sur extraction tous modules | ⏳ à demander |
| Retraitement des volumes bruts | ⏳ à faire |
| Coût de financement implicite des SBB | ⏳ à faire |
| Reconstitution de l'encours par titre | ⏳ bloqué — référentiel deals Calypso manquant |
| Rapprochement avec la balance générale | ⏳ bloqué — balance non fournie |

## Questions ouvertes (mises à jour)
1. **[HAUTE]** États financiers au **30/06/2025** : portaient-ils le solde créditeur de 1,2 Md sur
   un compte d'actif et le nostro BEAC surévalué d'autant ? Rapprochement bancaire BEAC de
   juin-juillet 2025 : pourquoi 45 jours pour détecter un écart de 1,2 Md ?
2. **[HAUTE]** Doctrine comptable des **Sell-Buy-Back** (215 opérations, 896 Md réglés).
3. **[HAUTE]** Constatation du **résultat de change** — demander les comptes 63/73 **tous modules**.
4. Troisième jambe de l'écriture de correction du 31/07/2025 (1 994 516 XAF).
5. Procédure de contrôle de la migration (calcul des courus repris).
6. Référentiel des **deals Calypso** (65 % de la période).
7. Pourquoi `INT_BT_LIQD` n'est-il pas paramétré pour les obligations (apurement manuel) ?
8. Paramétrage des comptes `475000160` / `476000160` (intitulés inversés).
9. Habilitations `ADMINUSER1` et 3 076 écritures sans validateur.
10. Conventions de pension livrée BEAC et durées réelles.
11. Politique de taux du change clientèle (marge intégrée au taux).
12. Dossiers de rétrocession « non exécutés » et taux atypique de 79 %.
13. Table de correspondance IFRS 9 ↔ PCEC dans Calypso.
14. Règle d'affectation entre comptes `733xxx` et `734xxx`.
15. Nature des 7 doublons de `MM_CONTRACT`.
16. Reclassement placement → transaction à la migration.
17. **Balance générale** aux dates d'arrêté.

---

# SESSION 11 — Les 41 comptes de trésorerie, tous modules

`final_key_accounts_Export Worksheet_part_1..6.csv` — **329 884 lignes**, **08/06/2022 →
18/09/2026**, 41 comptes, tous modules. **Encodage UTF‑8 conforme** (consigne suivie).
Chargeur `fkey()` ajouté à `scripts/load.py` (nettoyage des `\xa0` résiduels).
Modules : `DE` 214 511, `MM` 76 720, `FT` 22 654, `RE` 15 415, `RT` 556, **`GL` 28**.

Première extraction permettant de raisonner sur des **soldes** : pour les comptes créés après
juin 2022, le solde d'ouverture est nul, donc le cumul des mouvements **est** le solde.

## 11.1 ⚠⚠ 136,5 Md XAF en comptes de liaison Calypso au 30/06/2026
Les deux comptes ouverts au démarrage de Calypso (1ʳᵉ écriture 16/06/2025, donc ouverture à zéro) :

| Fin de trimestre | `467000186` | `467000188` |
|---|---:|---:|
| 30/06/2025 | +15 491 672 | 0 |
| 30/09/2025 | −5 233 940 957 | 0 |
| 31/12/2025 | −15 685 996 937 | −5 000 000 000 |
| 31/03/2026 | −33 604 411 774 | −93 902 460 379 |
| **30/06/2026** | **−42 058 339 493** | **−94 451 445 974** |
| 18/09/2026 | −48 325 343 347 | −94 549 929 809 |

**Total au 30/06/2026 : −136 509 785 467 XAF**, en dérive monotone.
Un compte de liaison est un compte de passage : il doit revenir à zéro.

Concentration par portefeuille : `ABCM_MM.Plmt.Tkn.Secured` (repo BEAC) **−120,25 Md**,
`ABCM_FVOCI.Bond` −38,01 Md, `ABCM_FI.Sales` −16,29 Md, `ABCM_FVOCI.Bills` −7,20 Md.

Par événement : `NOMINAL` −278,96 Md contre `CST_S_SETTLED` +225,43 Md sur `467000186` ;
`CST_S_SETTLED` −136,85 Md contre `PRINCIPAL_DEPOSIT` +20,00 Md sur `467000188`.

## 11.2 Module `GL` / produit `ZYND` / tag `YEND` = clôture annuelle
28 écritures aux 30/12/2022, 29/12/2023, 31/12/2024 et 31/12/2025 : chaque compte de résultat y est
soldé. Elles donnent **le compte de résultat de l'activité** :

| Exercice | Résultat (XAF) |
|---|---:|
| 2022 (juin-déc.) | 1 480 391 086 |
| 2023 | 6 195 242 929 |
| 2024 | 12 078 561 015 |
| 2025 | 22 330 085 762 |

Produits 2025 : `734400100` 10,86 Md, `733400100` 9,39 Md, `733200100` 1,27 Md, `729000125` 0,65 Md,
`727000102` 0,64 Md. Charges 2025 : `601100100` 0,52 Md, `625000105` 4,7 M.
→ La charge d'intérêt du repo n'apparaît qu'en 2025, cohérent avec le démarrage en novembre 2025.
→ **Aucun compte de gains/pertes de change dans les écritures de clôture.**

## 11.3 ⚠ Réévaluation de change jamais portée au résultat — CONFIRMÉ
Trois tests concordants sur 4 ans et tous modules :
1. couples position/contre-valeur : écart **exactement nul** (USD, EUR, GBP, ZAR) ;
2. aucune écriture touchant `475…`/`476…` ne touche un compte de résultat, hormis des
   **commissions** (`729000125`, `727000102`, `625000105`) ;
3. le module `RE` (15 415 lignes) ne mouvemente que position, contre-valeur et hors bilan.

Réévaluation cumulée non constatée, par exercice (compte de contre-valeur) :

| Exercice | USD | EUR | GBP | ZAR | Total |
|---|---:|---:|---:|---:|---:|
| 2022 | 138 825 565 | 777 910 | — | — | 139 603 474 |
| 2023 | 763 844 332 | −228 900 130 | — | 1 075 572 | 536 019 775 |
| 2024 | 337 605 765 | 295 236 | — | — | 337 901 001 |
| 2025 | 1 603 812 133 | 5 104 | −113 444 | — | 1 603 703 792 |
| 2026 (18/09) | 1 234 454 827 | −24 464 783 | 24 638 501 | 29 385 710 | 1 264 014 255 |
| **CUMUL** | **4 078 542 622** | **−252 286 663** | **24 525 057** | **30 461 282** | **3 881 242 297** |

L'EUR est quasi nul (parité fixe) ; **l'USD est une position ouverte**.
*Réserve* : requête de découverte du plan de comptes (`gl_desc LIKE '%CHANGE%'`) encore à exécuter.

## 11.4 Soldes du portefeuille — extinction propre du dispositif Flexcube
`511410100` = **0**, `512200100` = **0**, `511800100` = **0**, `591400100` = **0**.
Encours Calypso au 18/09/2026 : `512410100` 273,88 Md, `512800100` 23,10 Md, `511210100` 11,01 Md.

## 11.5 Refinancement BEAC — chiffres corrigés
| | Estimation §7 (partielle) | Corrigé |
|---|---:|---:|
| Encours emprunté `552400100` | ~25 Md | **45,00 Md** |
| Collatéral `952100100` | 77,85 Md | **71,85 Md** |
| Sur-collatéralisation | ~53 Md | **26,85 Md** (60 % de l'encours) |

Écriture isolée en 2022 sur `552400100` (3,5 Md au débit et au crédit, net nul), trois ans avant le
démarrage du repo — à qualifier.

## 11.6 Écritures techniques `i099` / `z099` du 10/06/2023
14 comptes du périmètre reçoivent le même jour un montant **négatif** (`i099`) et le même montant
**positif** (`z099`) — effet net nul. Ex. `511410100` ±24 981 550 000, `512200100` ±2 050 000 000,
`511800100` ±780 228 400. Reprise technique de soldes (renumérotation / migration interne).
Effet comptable nul mais à documenter.

## 11.7 Ce qui reste hors d'atteinte
- **3ᵉ jambe** des écritures de migration du `511800100` (écart 1 994 516 XAF) — hors des 41 comptes.
- **Comptes de gains/pertes de change** — codes inconnus, requête de découverte à exécuter.
- **Soldes en balance générale** aux dates d'arrêté — toujours non fournis.

---

## État d'avancement (mis à jour)

| Étape | Statut |
|---|---|
| Exploration initiale (4 fichiers) | ✔ |
| 2ᵉ extraction (comptes généraux Calypso) | ✔ |
| 3ᵉ extraction (compte 511800100) | ✔ |
| **4ᵉ extraction (41 comptes, tous modules)** | ✔ |
| Constat créances rattachées | ✔ infirmé (§12) |
| Réévaluation de change sans impact résultat | ✔ **confirmé** (§13.3) |
| Comptes de liaison Calypso | ✔ **nouveau constat majeur** (§13.1) |
| Compte de résultat par exercice | ✔ établi (§13.2) |
| **Rapport d'exploration v4** | ✔ (`rapport d'exploration.md`, §13) |
| Découverte des comptes de gains/pertes de change | ⏳ requête à exécuter |
| Retraitement des volumes bruts | ⏳ |
| Coût de financement implicite des SBB | ⏳ |
| Référentiel des deals Calypso | ⏳ bloqué |
| Balance générale aux dates d'arrêté | ⏳ bloqué |

## Questions ouvertes — trois priorités
1. **[MAXIMALE]** Les **136,5 Md** des comptes de liaison Calypso figurent-ils au bilan au
   30/06/2026 ? Existe-t-il un état de rapprochement ? L'écart se concentre sur le repo BEAC.
2. **[MAXIMALE]** La **réévaluation de change** (4,08 Md cumulés sur l'USD) est-elle portée au
   résultat par une écriture hors périmètre ? Sinon, incidence sur le résultat, les fonds propres
   et la position de change déclarée à la COBAC.
3. **[HAUTE]** Doctrine comptable des **215 Sell-Buy-Back** (896 Md réglés).
