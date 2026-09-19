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
