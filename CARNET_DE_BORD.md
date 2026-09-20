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

---

# SESSION 12 — Révision : l'historique des 41 comptes est intégral

**Déclencheur** : la banque signale que la quatrième extraction porte l'historique *entier* des
41 comptes. Il fallait le vérifier avant d'en tirer parti.

## 12.1 Vérification de la complétude — trois preuves concordantes
1. **Comptes revenant exactement à zéro** : `511410100`, `512200100`, `511800100`, `591400100`
   → solde net **0,00 XAF** sur toute leur vie. Un historique tronqué ne le permettrait pas.
2. **Concordance avec l'extraction dédiée** : `creance_rattaché.csv` = 32 937 lignes,
   16/08/2022 → 31/07/2025, solde 0,00 — **strictement identique** à ce que porte le fichier des
   41 comptes pour ce compte.
3. **Pas de mur de troncature** : dates de 1ʳᵉ écriture échelonnées (2 au 08/06/2022, 3 au 10/06,
   1 au 13/06, 2 au 05/08, 3 au 16/08…).

→ **Le solde d'ouverture est nul par construction ; le solde est calculable à toute date.**

Au passage, correction d'une erreur de classification : `472200106` et `472200108` sont des
**produits comptabilisés d'avance**, donc des comptes de **passif** — je les avais rangés en actif.

## 12.2 ⚠ CORRECTION — le solde anormal du compte d'emprunt n'est pas un solde d'ouverture
J'avais écrit au §7.3 du rapport que le cumul du `552400100` partant à −5 Md prouvait l'existence
d'un solde d'ouverture non fourni. **C'était faux.** Le compte démarre bien à zéro le 28/09/2022.

Le 07/11/2025, le deal `3186053` produit **trois** écritures au lieu de deux :

| Référence externe | Sens | Montant | Nature |
|---|---|---:|---|
| `CLP3186053_23630317_182512` | C | 5 000 000 000 | tirage |
| `CLP3186053_23630318_182512` | D | 5 000 000 000 | remboursement |
| `CLP3186053_23630318_182513` | D | 5 000 000 000 | **doublon** |

Le mouvement `23630318` est déversé deux fois, sous deux références Flexcube et deux horodatages.
→ résidu débiteur permanent de **5 Md** sur un compte d'emprunt, sur plus de dix mois.

## 12.3 ⚠⚠ CONSTAT NOUVEAU — l'interface Calypso n'est pas idempotente
Recherche systématique : même identifiant de transfert + même compte + même sens + même montant,
sous plusieurs références Flexcube.

| | |
|---|---:|
| Mouvements déversés en double | **178** |
| Montant total dupliqué | **289 631 995 600 XAF** |
| Période | 29/09/2025 → 15/09/2026 |
| Comptes touchés | 36 |

Impacts principaux sur les soldes :
`552400100` **+30,0 Md** · `467000188` −29,7 Md · `952100100`/`995000100` ±16,0 Md ·
`467000186` −14,9 Md · **`099ACO00001` (BEAC) +11,7 Md** · **`512410100` (portefeuille) +3,2 Md**

→ Le **nostro BEAC est surévalué de 11,7 Md** et le **portefeuille de 3,2 Md**. Aucune écriture
d'annulation. C'est aussi une **cause racine** de la dérive des comptes de liaison (§13.1) : les
doublons expliquent 44,6 Md sur les 136,5 Md constatés.

## 12.4 ⚠ CONSTAT NOUVEAU — soldes contraires à la nature comptable aux arrêtés
| Compte | Nature | Arrêté | Solde |
|---|---|---|---:|
| `511800100` créances rattachées | actif | **30/06/2025** | **−1 205 231 891** |
| `472200106` produits perçus d'avance | passif | **30/06/2026** | **+686 724 016** |
| `559000101` dettes rattachées | passif | **30/06/2026** | **+66 000 000** |

Le deuxième est nouveau : un compte de produits perçus d'avance **débiteur** signifie que
l'étalement au résultat a dépassé le produit différé → **686,7 M de produits reconnus sans
contrepartie**. Créditeur jusqu'au 31/12/2025 (−55,7 M), il bascule : +323,9 M au 31/03/2026,
+686,7 M au 30/06/2026.

## 12.5 ⚠ CONSTAT NOUVEAU — les courus dépassent une année de coupons
| Arrêté | Portefeuille | Courus | Ratio | Années d'intérêts |
|---|---:|---:|---:|---:|
| 31/12/2023 | 71 749 600 000 | 662 336 797 | 0,92 % | 0,15 |
| 30/06/2024 | 79 310 970 000 | 1 975 466 036 | 2,49 % | 0,42 |
| 31/12/2024 | 115 432 180 000 | 2 455 219 083 | 2,13 % | 0,35 |
| 30/06/2025 | 135 921 813 333 | 2 185 349 530 | 1,61 % | 0,27 |
| 31/12/2025 | 212 912 553 333 | 10 964 366 724 | 5,15 % | 0,86 |
| **30/06/2026** | **244 098 816 666** | **19 249 608 622** | **7,89 %** | **1,31** |

Rupture nette et datée **après la bascule**. Sur des titres à coupon annuel, 1,31 année de courus
signifie des coupons échus non encaissés ou des courus non apurés.

## 12.6 Répercussions sur le script d'audit
- `data.py` : ajout de `solde(comptes, a_la_date)`, `serie_solde(comptes, frequence)`,
  `soldes_aux_arretes()`, `arretes`, `historique_complet()`, `mouvements_dupliques`,
  et du dictionnaire `NATURE_COMPTE` (débiteur / créditeur / neutre).
- **1.7** réécrit : de « absence de soldes d'ouverture » (anomalie) à « complétude de l'historique
  et calculabilité des soldes » (conforme, avec les éléments de preuve).
- **3.7** nouveau : situation du portefeuille et des courus aux arrêtés, testée en années
  d'intérêts plutôt que par un ratio arbitraire.
- **6.7** nouveau : idempotence de l'interface Calypso (CRITIQUE).
- **9.4** nouveau : soldes contraires à la nature comptable aux arrêtés (CRITIQUE).
- `core.py` : les contrôles conformes affichent désormais leurs chiffres et tableaux — la situation
  du portefeuille aux arrêtés a une valeur informative même sans anomalie.
- Limites du rapport mises à jour.

→ **41 anomalies** (contre 39), dont **7 critiques**.

## 12.7 Enseignement de méthode (complète le §12.7 du rapport)
> **Avant de conclure qu'un solde d'ouverture manque, vérifier que l'extraction ne porte pas déjà
> l'historique intégral.** Un solde anormal n'est pas nécessairement la trace d'une donnée
> absente : il peut être l'anomalie elle-même.

Appliquée ici, cette vérification a transformé une limite supposée en trois constats d'audit.

---

# SESSION 13 — Approfondissement sur retours métier

La banque a apporté 16 commentaires. Plusieurs invalident des constats, d'autres demandent
un approfondissement. Une extraction native de Calypso a également été fournie.

## 13.1 Faux positifs retirés ou reclassés

| Constat | Retour de la banque | Traitement |
|---|---|---|
| Liquidation anticipée | La banque revend des titres pour faire face aux **tensions de liquidité** : c'est le mode de gestion normal du portefeuille | **3.1 réécrit** : seule la liquidation **après échéance** est rapportée |
| Liquidation au pair | Les titres d'État sont **toujours cédés au nominal**, l'acquéreur profitant du coupon couru | **Constat supprimé** |
| Concentration sur 4 souverains | Décision de **politique de risque** : exclusion délibérée du Tchad et de la RCA | **2.8 reclassé CONFORME** ; le contrôle vérifie désormais le respect de l'univers autorisé |
| Peu d'opérateurs nominatifs | L'équipe **Treasury Operations** n'a jamais dépassé 5 personnes | **4.5 reclassé** ; le contrôle porte sur la matrice saisie/validation |
| `ACCESSAFRIK` | Compte de la **plateforme Access Africa** (réseau propriétaire Access Bank), pas un utilisateur | Ajouté aux comptes techniques |

## 13.2 Périmètre resserré
La revue du référentiel porte désormais sur les **416 contrats bookés dans la période**
(sur 596 au total) — les autres relèvent d'exercices déjà audités.

## 13.3 Annulations et rebookings (points 5 et 6)
Sur les contrats bookés et liquidés le même jour dans la période : **ce sont TOUS des
annulations pures** — aucun ne porte d'écriture ultérieure. Ce sont des corrections de saisie.

⚠ **Constat nouveau (3.4)** : l'annulation **ne contre-passe pas les intérêts courus**.
- 47 contrats annulés, dont 40 portant des courus pour **24 483 539 XAF**
- **0 contre-passation** par la liquidation
- Apurements ultérieurs incohérents : **4 contrats jamais apurés**, **20 sur-apurés**
  (fréquemment le double exact du couru enregistré)

## 13.4 Recalcul des courus approfondi (point 8)
Méthode désormais explicitée dans le rapport. **Trois conventions testées** : exact/365,
exact/360 et **exact/exact** (chaque jour rapporté aux 365 ou 366 jours de son année civile).
La période couvre deux années bissextiles ; ignorer la distinction biaise de 0,27 %.
Chaque contrat en écart est **classé par cause** : aucun couru enregistré, contre-passations
partielles, période non représentative, courus au-delà de l'échéance, écart inexpliqué.

## 13.5 Horaires (point 10)
Test restreint aux **comptes du périmètre titres**. Les saisies en soirée (20 h-24 h) sont
compatibles avec une salle de marché et ne sont plus rapportées. Restent **2 dates de saisie
nocturne**, dont une est le jour de la bascule.

## 13.6 Constat 5.3 entièrement décomposé (point 12)
15 chiffres numérotés, 4 tableaux : contrepartie trésorerie de l'écriture, **décomposition
contrat par contrat** (cumul depuis l'origine / déjà encaissé / solde réel / crédité / crédité
en trop), soldes à chaque arrêté, écriture de correction et sa troisième jambe.

## 13.7 Sell-Buy-Back — raisonnement en schéma comptable (points 13-15)

**8.2 — la démonstration par le PCEC.** Comparaison des comptes mouvementés :

| Marqueur d'une pension livrée | Compte | Pensions BEAC | Cessions-rétrocessions |
|---|---|---|---|
| Dette au passif | `552400100` | ✔ | **absent** |
| Charge d'intérêt | `601100100` | ✔ | **absent** |
| Titres affectés en garantie (hors bilan) | `952100100` / `995000100` | ✔ | **absent** |
| Sortie du portefeuille | `512410100` crédité | non | **oui, 457 Md** |

→ La banque applique correctement le schéma de pension à ses opérations BEAC. Elle ne
l'applique pas aux cessions-rétrocessions, qu'elle enregistre en cession ferme.

**8.3 — le book dédié existe et n'est pas utilisé.** `ABCM_BSB.Bond` ne compte que
**8 deals, dont 6 annulés**. Les **215 opérations commentées SBB sont toutes** dans
`ABCM_FVOCI.Bond` (204) et `.Bills` (11). **Zéro dans le book dédié.**

**8.1 — détection indépendante du commentaire.** Signature d'aller-retour dans le référentiel
des deals : même titre, même contrepartie, quantités opposées, rachat sous 120 jours.
- **107 paires détectées**, dont **44 (41 %) NE portent aucun commentaire SBB**
- Cas emblématique : `BondGOCM/CM2K00000060` avec SGCM, **5 aller-retours successifs** de
  500 410 titres exactement, tous les 21 à 30 jours, jamais commentés
→ L'identification par le libellé **manque 41 % des opérations**.
- Concentration : **194 des 200 deals SBB traités par un seul opérateur**

## 13.8 Point 9.2 réécrit pour être accessible (point 16)
Explication en cinq temps : le principe des deux familles de titres (placement = garder,
transaction = revendre vite), la règle (« comme une chaussure gauche avec une chaussure
gauche »), le constat, pourquoi c'est gênant (le régulateur distingue les deux natures de
revenus : l'une récurrente, l'autre volatile), et l'origine (le bilan a suivi la migration,
le compte de résultat ne l'a pas suivi).

## 13.9 ⚠ NOUVELLE SECTION 10 — cohérence Calypso ↔ grand livre (point 7)
`extraction_from_calypso.csv` : **3 480 deals**, 08/07/2022 → 09/09/2026, avec **statut**,
**trader**, **utilisateur de saisie**, contrepartie, quantité et prix.

| Contrôle | Constat |
|---|---|
| **10.1** | **1 355 deals aboutis (42 %) sans aucune écriture comptable** — à départager entre périmètre de comptes et échec de déversement |
| **10.2** | **26 deals non aboutis ont produit de la comptabilité** : 22 annulés, 1 **HYPOTHÉTIQUE**, 3 en attente. 24 sont correctement contre-passés ; **2 laissent un résidu définitif** (82 850 XAF au résultat) dont le deal hypothétique (71 550 XAF de commission + 60 M de hors bilan) |
| **10.3** | 41 deals du grand livre absents du référentiel amont |
| **10.4** | **Saisie sous comptes génériques** (`admin`, `calypso_user`) ; **511 deals sans trader identifié** ; **aucun champ de validation** dans le référentiel |
| **10.5** | Référentiel des opérateurs non normalisé : même personne sous plusieurs libellés, valeurs de remplissage (`NONE`, `0`, `TRADER1`) |

→ **46 anomalies** (contre 41), dont **7 critiques**, sur **10 sections et 58 contrôles**.

---

# SESSION 14 — Relecture critique du rapport d'audit et correction de ses anomalies

Demande : *« relis le rapport d'audit, identifie les anomalies et corrige-les »*. Le rapport
est ici traité comme un livrable à auditer : chaque affirmation du texte a été confrontée aux
chiffres qu'elle accompagne, chaque chiffre à son périmètre, chaque renvoi à son contrôle
cible. Vingt-six corrections ont été apportées. Elles se rangent en cinq familles.

## 14.1 Le texte affirmait ce que les chiffres contredisaient

| Contrôle | Le texte disait | Les données disent |
|---|---|---|
| **1.4** | « L'effet comptable net est nul » | −589 588 XAF subsistent, pour 86,4 Md déplacés |
| **3.7** | « La progression est continue » | Le ratio recule entre le 31/12/2024 et le 30/06/2025 |
| **5.1** | « sur un nombre identique de positions » | 65 à la sortie, 68 à l'entrée |
| **7.2** | « couru passé le jour du tirage puis contre-passé » | Le compte de charge ne porte **aucun** couru, jamais |
| **9.1** | « le résultat double quasiment d'un exercice à l'autre » | ×4,18 puis ×1,95 puis ×1,85 — ×15 au total |
| **9.3** | « l'écart s'accroît d'exercice en exercice » | 10,15 → 15,07 → 13,00 → 15,07 % |
| **9.4** | Le solde du compte d'emprunt vient des doublons (6.7) | Zéro doublon sur ce compte ; c'est une contre-passation orpheline du 21/01/2026 |

## 14.2 Deux erreurs de calcul

**7.2 — l'intérêt des pensions était divisé par deux.** `interet = sum(...) / 2` supposait que
l'extraction portait les deux jambes ; elle n'en porte qu'une. Les taux implicites ressortaient
à 2 % là où le taux BEAC est de 5 à 6 %. Corrigé : le deal 3349072 règle 101 000 000 XAF et non
50 500 000, soit 4,18 % sur 98 jours.

**7.3 — les soldes n'étaient ni datés ni corrigés.** Ils étaient pris à la fin de l'extraction
(18/09/2026) et incluaient les doublons d'interface. Arrêtés au 30/06/2026 et nettoyés :

| | Avant | Après |
|---|---|---|
| Encours emprunté | 45 000 000 000 | **50 000 000 000** |
| Collatéral mobilisé | 71 847 170 000 | **61 847 170 000** |
| Taux de couverture | 160 % | **124 %** |

L'encours corrigé égale **exactement** l'unique opération non dénouée relevée en 7.4. Les deux
contrôles convergent — ce qui n'était pas le cas auparavant.

## 14.3 Des chiffres annoncés hors du périmètre d'audit

L'extraction court jusqu'au 18/09/2026, la période d'audit s'arrête au 30/06/2026. Plusieurs
constats majeurs annonçaient des montants dominés par les mois postérieurs à la clôture.

| Contrôle | Annoncé | Dont période d'audit |
|---|---|---|
| **6.7** doublons d'interface | 178 mouvements / 289,6 Md | **124 mouvements / 76,7 Md** |
| **8.1** cessions-rétrocessions | 215 opérations / 896,1 Md | **80 opérations / 402,4 Md** |
| **8.5** résultat sur financements | 1 045 123 213 XAF | **182 465 990 XAF** |
| **Section 4** contrôle interne | 3 076 écritures sans validateur | **2 557** |

La section 4 étant désormais bornée à la période, le contrôle 4.5 devient **conforme** :
5 opérateurs, ce qui correspond à l'effectif de l'équipe Treasury Operations.

## 14.4 Un constat qui n'en était pas un

**10.3 — « 2 597 Md d'écritures sans deal source ».** Le référentiel des deals s'arrête au
**09/09/2026**, le grand livre court jusqu'au **18/09/2026**. La totalité des 41 deals dits
orphelins se situe dans cet intervalle, et **aucun** à l'intérieur de la fenêtre couverte par
le référentiel. Ce n'était pas une rupture de piste d'audit mais un décalage entre deux
extractions. Gravité ramenée de MOYENNE à FAIBLE, le constat étant reformulé en demande de
ré-extraction.

## 14.5 Périmètres incohérents entre contrôles voisins

- **3.4** portait sur tout l'historique quand **3.2**, qui décrit les mêmes annulations, était
  borné à la période : 47 contrats contre 29. Aligné à 29.
- **3.5** annonçait « deux années bissextiles, 2024 et 2028 » sur une liste écrite en dur ;
  les périodes d'accrual testées ne traversent que **2024**. La mention est calculée.
- **1.3** ne reportait pas au lundi les fériés tombant un week-end : le 26/12/2022 et le
  02/01/2023 ressortaient à tort. Le test est borné à la période et propose une hypothèse de
  rattachement pour chaque date restante (pont, fête musulmane).

## 14.6 Mesures dépourvues de sens remplacées

- **3.3** « Flux bruts sur le compte de règlement : **0 XAF** » — la somme des montants signés
  d'un compte équilibré. Remplacée par ce que le constat démontre réellement : **1 213,8 Md**
  de volume brut pour **−33,8 Md** de flux net, soit un facteur **× 35,9**, et **58,8 %** du
  volume MM de la période.
- **5.2** ne mesurait pas l'écart entre les courus repris par Calypso et le solde réel du
  compte d'origine : **125 570 147 XAF**. Le contrôle passe de conforme à MOYENNE.
- **8.2** énonçait trois marqueurs comptables et en chiffrait quatre : trois marqueurs,
  quatre comptes, l'inscription hors bilan ayant une contrepartie.

## 14.7 Forme

Séparateur décimal français dans tout le rapport, tableaux compris ; `.replace(",", " ")`
appliqué à des phrases entières qui en supprimait la ponctuation ; valeurs manquantes rendues
par une cellule vide et non par « nan » ; tri numérique des codes (2.6 avant 10.2) ; notes de
tableau repliées sur la largeur du rapport.

## 14.8 État du rapport après relecture

**46 anomalies** — 7 critiques, 17 élevées, 19 moyennes, 3 faibles — sur **10 sections et
59 contrôles**. Le nombre total est inchangé, mais trois contrôles ont changé de nature :
4.5 devient conforme, 5.2 devient une anomalie, 10.3 passe de MOYENNE à FAIBLE.

**Règle retenue pour la suite** : *un constat n'est acquis que lorsque son texte, son chiffre
et son périmètre disent la même chose.* Les sept contradictions de 14.1 ont toutes été trouvées
en lisant le paragraphe et le tableau l'un contre l'autre, sans donnée nouvelle.

---

# SESSION 15 — Comprendre Calypso par les titres, puis réconcilier le portefeuille

Trois demandes : ne pas oublier le test de codification des titres ; réconcilier l'analyse du
portefeuille MM et celle du portefeuille Calypso en un seul portefeuille, en distinguant dans
Calypso les titres propres de ceux achetés pour la clientèle ; et, avant tout, tirer six titres
au hasard, suivre manuellement toutes leurs transactions pour comprendre le fonctionnement de
Calypso, puis relire à cette lumière tous les travaux déjà faits sur Calypso.

## 15.1 La méthode : six titres suivis mouvement par mouvement

Tirage aléatoire sur la liste des titres du flux Calypso : `CM1300000849`, `CG1300000862`,
`CM1200001897`, `CM2J00000212`, `GQ1300001641`, `GA2K00000249`. Quatre bons du Trésor à
escompte, deux obligations, dont une présente à la fois au portefeuille propre et au
portefeuille clientèle.

### Le schéma comptable de Calypso, enfin lisible

Chaque deal produit des MOUVEMENTS, chacun équilibré, qui transitent TOUS par un compte de
liaison. Exemple d'une acquisition d'obligation (deal 3175371, 10/11/2025) :

| Événement | Débit | Crédit | Montant |
|---|---|---|---|
| `ACCRUAL_BS` | 512800100 courus | pont 467000186 | 249 315 100 |
| `NOMINAL` | 512410100 portefeuille | pont | 20 000 000 000 |
| `PREM_DISC` | pont | 472200108 régularisation | 1 790 000 000 |
| `CST_S_SETTLED` | pont | 099ACO00001 nostro | 18 459 315 100 |

**Trois enseignements majeurs, qu'aucune analyse antérieure n'avait vus :**

1. **Le portefeuille est tenu AU PAIR.** Les comptes 511/512 portent le NOMINAL, pas le prix
   payé. L'écart — prime ou décote — vit dans les comptes de régularisation 472200106 (bons)
   et 472200108 (obligations). L'encours de 244 Md au 30/06/2026 est donc un nominal.
2. **La décote n'est pas étalée, elle est reprise EN TOTALITÉ à la cession.** Sur le deal
   3175371 : décote de 1 790 000 000 constatée le 10/11, reprise les 18/11 (984 500 000 =
   55 %) et 24/11 (805 500 000 = 45 %), au prorata exact des quantités revendues. Acheté à
   91,05 % du pair, revendu au pair en huit jours. **7 640 766 066 XAF de produit de cette
   seule nature sur la période d'audit.** C'est la même mécanique que le rendement implicite
   de 15 % du contrôle 9.3, vue de l'autre côté.
3. **ÉGALITÉ FONDATRICE : nominal + couru − décote = règlement.** Vérifiée au centime près
   sur 18 des 22 deals de l'échantillon. Les 4 exceptions sont des mouvements déversés deux
   fois — le deal 3433901 porte le `PREM_DISC` 24107305 sous DEUX références Flexcube. Ce
   test retrouve donc seul, et par une voie indépendante, les défauts d'interface des
   contrôles 6.7 et 11.6.

### Le circuit des titres vendus à la clientèle

Traçé sur `GA2K00000249` : `NOM_FULL` transfère du pont 467000186 vers le **pont miroir**
467000243 ; `NOMINAL` sort les titres au hors bilan (938000100 / 998000100) ; `CST_S_SETTLED`
débite le compte du client. Le titre **transite donc par le bilan de la banque** avant d'être
placé.

## 15.2 ⚠ CE QUE CETTE COMPRÉHENSION A INVALIDÉ

### Le solde des comptes de liaison n'est pas un retard d'apurement

Le contrôle 6.4 constatait une « dérive continue » sans cause. Puisqu'un deal intégralement
déversé laisse le pont à ZÉRO, le solde du pont **mesure exactement les mouvements manquants**.

| | Deals | Résidu |
|---|---|---|
| Deals transitant par un pont | 1 208 | — |
| Dont **soldés à zéro** | 945 | 0 |
| Dont **déversement incomplet** (période d'audit) | 201 | −124 704 289 100 |

Trois causes, trois conséquences distinctes : règlement non déversé (la trésorerie est fausse),
jambes de bilan non déversées (le portefeuille est faux), déversement partiel des deux côtés.

**Le cas le plus lourd : le deal 3349072**, pension BEAC de 90 Md tirée le 23/12/2025. Le
remboursement du 31/03/2026 éteint bien la dette (552400100 débité) et constate l'intérêt,
**mais le décaissement n'a jamais été déversé**. Vérifié : aucun mouvement de 90 Md sur le
nostro entre le 30/03 et le 02/04/2026. Le compte BEAC est donc surévalué de 90 101 000 000 XAF
à la clôture. Nouveau contrôle **11.6, CRITIQUE**.

### La politique de risque n'est pas tenue

Le contrôle 2.8 concluait « aucun contrat sur le Tchad et la Centrafrique, la politique est
respectée ». Mais 2.8 ne teste que MM_CONTRACT, **qui ne reçoit plus rien depuis la bascule**.
Le flux Calypso contient :
- `TD2A00000735` (Tchad) — 9 deals, 9 000 000 000 d'acquisitions
- `CF2A00000074`, `CF2J00000158` (Centrafrique) — 10 deals, dont un encours de 11 300 000 XAF
  **au bilan au 31/12/2025**

2.8 est requalifié « sous l'ancien dispositif » et renvoie au nouveau contrôle **11.4**.

### Les cessions-rétrocessions ne vont pas toutes dans le même sens

Le contrôle 8.2 posait que l'endettement était sous-évalué. Le sens de la première jambe dit
autre chose : sur 94 opérations identifiables, **38 (40 %) sont des financements ACCORDÉS** —
la banque acquiert le titre et décaisse. Pour celles-là, ce n'est pas une dette qui manque au
passif mais une **créance à l'actif**, et le titre acquis n'aurait pas dû y entrer. Les deux
populations appellent des retraitements opposés.

## 15.3 La codification des titres (le test demandé)

Depuis la bascule, le libellé de l'écriture est le **seul** signalement d'un titre. Trois tests.

| Test | Résultat |
|---|---|
| Le code existe-t-il ? | **5 titres à code de remplissage** (`XXXXXXXXX1`…`5`), portant **40 000 000 000 XAF** d'encours |
| Code pays et mnémonique concordent-ils ? | **4 titres se contredisent** (`CG2K00000070` codé Congo, libellé `BondGOGA`) + **3 à mnémonique non répertorié** (`GQCM`) |
| Même libellé dans les deux sources ? | **123 titres sur 129 divergent (95 %)** |

Le troisième test est le plus grave. Le grand livre écrit l'échéance en **MM/JJ/AAAA**,
l'extraction Calypso en **JJ/MM/AAAA** :

```
grand livre : BondGOCG/CG2A00000478/XAF/0D/03/01/2026/5.4%
référentiel : BondGOCG/CG2A00000478/XAF/0D/01/03/2026/5.4%
```

Les deux lectures sont plausibles : **l'échéance de ce titre est indéterminable**. Tout
échéancier construit sur ces libellés est faux pour chaque titre dont le jour et le mois sont
inférieurs à 13. Nouveau contrôle **11.3, ELEVEE**.

## 15.4 Le portefeuille réconcilié (la demande centrale)

| Arrêté | Comptes Flexcube | Comptes Calypso | **PORTEFEUILLE PROPRE** | Clientèle (hors bilan) |
|---|---|---|---|---|
| 31/12/2023 | 71 749 600 000 | — | **71 749 600 000** | 0 |
| 30/06/2024 | 79 310 970 000 | — | **79 310 970 000** | 0 |
| 31/12/2024 | 115 432 180 000 | — | **115 432 180 000** | 0 |
| 30/06/2025 | — | 135 921 813 333 | **135 921 813 333** | 30 159 010 000 |
| 31/12/2025 | — | 212 912 553 333 | **212 912 553 333** | 28 635 360 000 |
| 30/06/2026 | — | 244 098 816 666 | **244 098 816 666** | 23 893 110 000 |

**× 3,4 en moins de trois ans.** La bascule est neutre : −14 066 464 XAF d'écart entre la
sortie nette des comptes Flexcube et l'entrée nette dans les comptes Calypso.

La séparation propre / clientèle est **possible au hors bilan mais pas au bilan** : les titres
destinés aux clients transitent par le portefeuille propre sans qu'aucun compte ne les
distingue. Le pont miroir porte **3 104 020 778 XAF** non apurés à la clôture.

## 15.5 Nouvelle section 11 — Le portefeuille de titres comme un tout

| Contrôle | Gravité | Objet |
|---|---|---|
| **11.1** | conforme | Le portefeuille en une seule série, de bout en bout |
| **11.2** | MOYENNE | Les titres de la clientèle transitent par le portefeuille propre |
| **11.3** | ELEVEE | Codification : codes fictifs, pays contradictoires, dates ambiguës |
| **11.4** | ELEVEE | Souverains exclus présents dans le nouveau dispositif |
| **11.5** | ELEVEE | Portefeuille au pair : prime, décote et valeur comptable |
| **11.6** | CRITIQUE | Le solde des ponts mesure les déversements manquants |
| **11.7** | MOYENNE | Schéma comptable reconstitué sur l'échantillon de six titres |

**52 anomalies** — 8 critiques, 20 élevées, 21 moyennes, 3 faibles — sur **11 sections et
66 contrôles**.

**Règle retenue** : *avant d'auditer un système, en reconstituer le schéma comptable sur un
échantillon réel suivi de bout en bout.* Les quatre constats les plus lourds de cette session
— la pension de 90 Md non décaissée, les souverains exclus, les dates d'échéance ambiguës, les
40 Md de titres sans code — sont tous sortis de cette lecture, et aucun n'était visible dans
les agrégats.

---

# SESSION 16 — Le deal 3349072, et ce qu'il a révélé sur toute la section 7

Demande : plus de détail sur la pension de 90 Md dont le décaissement n'a jamais été
comptabilisé. L'examen a confirmé le constat — et invalidé au passage deux contrôles de la
section 7.

## 16.1 ⚠ DÉCOUVERTE : les conditions contractuelles sont dans le libellé

En cherchant la jambe manquante, le libellé complet est apparu :

```
|3349072|23941152|INTEREST|Repo|BEAC|ABCM_MM.Plmt.Tkn.Secured||
Repo-(BondGOGQ/GQ2J00000057/XAF/0D/07/03/2028/7%)12/18/2025/12/26/2025/5.05000
```

Après le titre donné en garantie viennent **la date de départ, la date d'échéance et le taux
du contrat**. Extraction réussie sur **1 026 lignes sur 1 026**, soit les 129 pensions.

**Ce que cela change :**

| | Avant (dates de comptabilisation) | Après (dates contractuelles) |
|---|---|---|
| Durée max d'une pension | **98 jours** | **8 jours** |
| Pensions « longues » | 11 de plus de 4 jours | 52 de plus d'1 jour, max 8 j |
| Charge non rattachée à l'arrêté | 8 244 898 XAF | **63 750 000 XAF** |

Le contrôle 7.1 affirmait qu'une pension avait duré « plusieurs mois ». **C'était faux** :
aucune pension ne dépasse 8 jours contractuellement. Les 98 jours étaient un **retard de
comptabilisation**. 7.1 et 7.2 sont réécrits sur la base contractuelle.

L'intérêt se recalcule exactement : `montant × taux × jours / 360`, vérifié au centime près
sur **127 des 129 pensions**. Les 2 exceptions sont instructives :
- **3854201** : aucun intérêt → opération jamais dénouée (déjà vue en 7.4)
- **4184547** : intérêt **exactement double** → mouvement déversé deux fois (déjà vu en 6.7)

Ce recalcul est donc un **troisième filet de détection indépendant** des mêmes défauts.

## 16.2 Anatomie du deal 3349072

**Contrat** : 90 000 000 000 XAF empruntés à la BEAC du **18/12/2025 au 26/12/2025**, 8 jours,
**5,05 %**. Intérêt contractuel = 90e9 × 5,05 % × 8/360 = **101 000 000** — exactement le
montant comptabilisé.

**Tirage, comptabilisé le 23/12/2025 — correct et complet**
- 19 titres inscrits au hors bilan : 91 333 110 000 (101,5 % de couverture)
- `PRINCIPAL_DEPOSIT` : dette 552400100 créditée 90 Md / pont débité
- `CST_S_SETTLED` : nostro débité 90 Md / pont crédité
- **Pont = 0** ✓

**Remboursement, comptabilisé le 31/03/2026 — amputé**
- `NOMINAL_REV` : les 19 titres libérés ✓
- `PRINCIPAL_DEPOSIT` : dette éteinte ✓
- `INTEREST` : 101 000 000 en charge ✓
- **`CST_S_SETTLED` : ABSENT** ✗

**Effet net** : nostro **+90 000 000 000** au lieu de −101 000 000 attendus. Pont
**−90 101 000 000**. Recherche exhaustive : **aucune écriture de 90 101 000 000 ni de
90 000 000 000 au débit du nostro** entre le 30/03 et le 02/04/2026, ni ailleurs.

### La preuve par la chaîne de refinancement

La pension appartient à une ligne BEAC roulée chaque semaine. Les voisines sont irréprochables :

| Deal | Contrat | Jours | Taux | Montant | Pont | Effet trésorerie | |
|---|---|---|---|---|---|---|---|
| 3339125 | 11→18/12 | 7 | 4,80 | 90 Md | 0 | −84 000 000 | ✓ |
| **3349072** | **18→26/12** | **8** | **5,05** | **90 Md** | **−90 101 000 000** | **+90 000 000 000** | **✗** |
| 3368198 | 26/12→02/01 | 7 | 5,10 | 90 Md | 0 | −89 250 000 | ✓ |

Même montant, même contrepartie, même schéma. Seule celle du milieu est cassée. Ce n'est donc
ni un effet de paramétrage ni une particularité du produit.

### Effets connexes

1. **Au 31/12/2025** : le bilan porte une dette de 90 Md **contractuellement éteinte depuis le
   26/12**, et le nostro la trésorerie correspondante. Le vrai encours à cette date était celui
   du deal 3368198, absent des livres jusqu'au 02/01/2026.
2. **Collatéral immobilisé 95 jours au-delà de l'échéance** : 91 333 110 000 restés au hors
   bilan du 26/12/2025 au 31/03/2026, minorant d'autant la réserve de liquidité mobilisable
   affichée (lien avec 7.3).
3. **Deux des 19 titres gagés sont arrivés à échéance pendant le gage** : `CG2A00000478`
   (01/03/2026, 2 821 000 000) et `CG2A00000486` (28/03/2026, 1 221 940 000). Un titre échu ne
   peut plus servir de garantie.

## 16.3 Nouveaux contrôles

| Contrôle | Gravité | Objet |
|---|---|---|
| **7.5** | ELEVEE | Remboursements comptabilisés après l'échéance contractuelle — 14 pensions > 5 j, retard max **133 jours**, 1 dette éteinte portée au bilan à un arrêté |
| **7.6** | MOYENNE | Recalcul de l'intérêt sur les conditions contractuelles — 127/129 exacts, les 2 écarts révélant un doublon et une opération non dénouée |
| **11.8** | CRITIQUE | Anatomie complète du deal 3349072, avec la comparaison à la chaîne |

**55 anomalies** — 9 critiques, 20 élevées, 23 moyennes, 3 faibles — sur **11 sections et
69 contrôles**.

**Règle retenue** : *une durée ne se lit jamais sur les dates de comptabilisation.* Les 98 jours
du rapport précédent étaient un délai de saisie pris pour un terme. Chercher la donnée
contractuelle — ici, cachée dans le libellé — avant de conclure sur une durée.

---

# SESSION 17 — Revue manuelle des 29 contrats « annulés » : les deux constats étaient faux

Demande : revoir manuellement chaque contrat qualifié de problématique, en tenant compte de la
**date de négociation** — un contrat booké et liquidé le même jour n'a pas forcément été acheté
ce jour-là — et regarder de près les transactions, parce que **pour certains contrats les
intérêts ont bien été contre-passés**.

Les deux remarques étaient fondées. Les contrôles 3.2 et 3.4 sont entièrement réécrits.

## 17.1 ⚠ La date de négociation change la nature de 21 contrats sur 29

Le test retenait `date de booking = date de liquidation` et concluait « annulation ». Or la
détention court depuis la **date de valeur**, elle-même calée sur la négociation.

| | Contrats | Nominal | Nature réelle |
|---|---|---|---|
| Négocié = booké = liquidé | **8** | 35 954 100 000 | vraies annulations de saisie |
| Négocié AVANT le booking | **21** | 47 708 100 000 | **cessions après détention de 1 à 13 jours** |

Exemple : `099OTAP232820001`, négocié le **26/09/2023**, booké et liquidé le **09/10/2023**.
Détention réelle **13 jours**. Couru comptabilisé 7 479 452 XAF =
3 000 000 000 × 7 % × 13/365 = **7 479 452 XAF exactement**. Ce couru que je qualifiais
d'anomalie est parfaitement justifié.

Ces 21 contrats ne sont pas des erreurs de saisie mais des opérations réelles comptabilisées en
retard — ce que le contrôle 2.4 relevait déjà séparément, sans que je fasse le lien.

## 17.2 ⚠ Les contre-passations existaient — en débits négatifs

3.4 annonçait « CONTRE-PASSATIONS PAR LA LIQUIDATION : 0 ». Le test cherchait des **crédits** :

```python
contre_passe = lignes[(lignes.MODULE == "MM") & (lignes.DRCR_IND == "C")]
```

Or Flexcube contre-passe par un **débit de montant NÉGATIF** — ce que documente mon propre
contrôle 1.5. Exemple `099OTAP240640005` :

| Date | Module | Sens | Montant |
|---|---|---|---|
| 2024-03-04 | MM | D | **+4 098 361** |
| 2024-03-04 | MM | D | **−3 278 689** |

**9 des 21 cessions portent une contre-passation, pour 1 036 405 122 XAF sur l'ensemble du
compte.** J'avais écrit le contrôle 1.5 puis violé sa conclusion trois contrôles plus loin.

## 17.3 Le vrai constat : un traitement hétérogène

Une fois les deux corrections faites, il reste une anomalie — plus petite mais réelle.

| Détention | Contrats | Traitement du couru |
|---|---|---|
| 13, 5, 3 jours | 3 | couru intégral conservé |
| 1 jour | 9 | 1 jour conservé (cohérent) |
| 2 à 5 jours | 9 | **ramené à 1 jour** par contre-passation |

La preuve par la paire, deux contrats bookés à un jour d'intervalle :

| Contrat | Contrepartie | Détention | Couru brut | Contre-passé | Net |
|---|---|---|---|---|---|
| `099OTAP240650003` | CONGO | **5 j** | 2 213 115 | **0** | 2 213 115 (5 j) |
| `099OTAP240640005` | CAMEROUN | **5 j** | 4 098 361 | **−3 278 689** | 819 672 (**1 j**) |

Même durée de détention, traitements opposés. Comme le titre d'État est cédé au pair et que
l'acquéreur garde le coupon couru, la contre-passation est la bonne écriture — mais alors elle
est due pour **toutes** les cessions et pour la **totalité** du couru, pas pour 9 sur 21 en
laissant un jour résiduel. Les deux pratiques ne peuvent pas être correctes ensemble.

## 17.4 Le même angle mort corrigé en 3.6

Le contrôle annonçait « 32 136 débits pour 801 crédits ». Les 32 136 mélangeaient 31 892 courus
et **244 contre-passations** de 1 036 405 122 XAF. Le compte se lit désormais en trois
populations.

Balayage des autres contrôles : 3.5 classe déjà les négatifs, et les sections Calypso ne sont pas
concernées — le contrôle 1.5 a établi que ce flux ne porte aucun montant négatif.

## 17.5 État

**55 anomalies** — 9 critiques, 19 élevées, 24 moyennes, 3 faibles — sur 11 sections et
69 contrôles. 3.4 passe de ELEVEE à MOYENNE : le constat est réel mais dix fois plus petit que
ce que j'annonçais.

**Règle retenue** : *avant de qualifier une opération d'anormale, reconstituer sa chronologie
réelle — négociation, valeur, comptabilisation, dénouement — et lire les écritures dans la
convention du système qui les a produites.* Les deux erreurs viennent d'avoir pris une date de
saisie pour une date d'opération, et d'avoir cherché une contre-passation dans la convention
d'un autre système.

---

# SESSION 18 — Contrôle 5.3 : nommer les comptes

Demande : rendre 5.3 plus explicite afin d'identifier clairement les comptes en cause.

Le constat parlait du « compte de créances rattachées », du « compte de règlement » et d'une
« troisième jambe » sans jamais donner de numéro. Un constat comptable doit désigner ses comptes.

## 18.1 Les comptes sont désormais nommés partout

Un paragraphe d'ouverture les pose d'emblée :

- **511800100 CREANCES RATTACHEES - PLACEMENT** — compte d'ACTIF, porte les coupons acquis et
  non encaissés
- **099ACO00001 BANQUE DES ETATS DE L'AFRIQUE CENTRALE** — le NOSTRO, compte de règlement
  auprès de la banque centrale
- un **troisième compte**, intervenant à la correction, absent de toutes les extractions

Les quinze lignes chiffrées, les quatre notes de tableau et les cinq recommandations portent
désormais le numéro du compte concerné.

## 18.2 Un tableau de schéma comptable

Ajouté en tête des tableaux : l'écriture attendue, celle qui a été passée, l'écart compte par
compte, puis la correction — chaque ligne avec compte, libellé, sens et montant.

| Étape | Compte | Sens | Montant |
|---|---|---|---|
| Ce qu'il fallait passer | 511800100 | CRÉDIT | 2 963 891 902 |
| Ce qu'il fallait passer | 099ACO00001 | DÉBIT | 2 963 891 902 |
| Ce qui a été passé | 511800100 | CRÉDIT | 4 169 123 793 |
| Ce qui a été passé | 099ACO00001 | DÉBIT | 4 169 123 793 |
| **ÉCART** | 511800100 | **CRÉDIT EN TROP** | **1 205 231 891** |
| **ÉCART** | 099ACO00001 | **DÉBIT EN TROP** | **1 205 231 891** |
| Correction 31/07/2025 | 511800100 | DÉBIT | 1 205 231 891 |
| Correction 31/07/2025 | 099ACO00001 | CRÉDIT | 1 207 226 407 |
| Correction 31/07/2025 | non identifié | **DÉBIT MANQUANT** | **1 994 516** |

## 18.3 ⚠ Une erreur corrigée au passage

Le texte disait de la troisième jambe qu'« il manque 1 994 516 XAF », sans préciser le sens. En
construisant le tableau, le sens s'impose : la correction porte un débit de 1 205 231 891 sur
511800100 contre un crédit de 1 207 226 407 sur 099ACO00001. **Le crédit excède le débit**, la
jambe manquante est donc un **DÉBIT**. Le sens est maintenant déduit du déséquilibre plutôt
qu'énoncé au hasard, et la recommandation 4 demande d'identifier « le compte qui porte un débit
de 1 994 516 XAF sur l'écriture 099000b252120001 ».

**Règle retenue** : *un constat comptable nomme ses comptes et donne le sens de chaque jambe.*
Construire le schéma en débit/crédit a suffi à faire apparaître le sens de la jambe manquante.

---

# SESSION 19 — Revue manuelle du point 6.7 : trois défauts dans mon propre contrôle

Demande : revue manuelle du contrôle 6.7, les doublons de déversement de l'interface Calypso.
Le constat tient, mais ses chiffres étaient faux et il passait sous silence un fait important.

## 19.1 ⚠ Les chiffres annoncés comptaient les JAMBES, pas les mouvements

Un mouvement Calypso produit deux à quatre jambes d'écriture. Le contrôle groupait par
`DEAL|MOUVEMENT|COMPTE|SENS` et additionnait le montant de chaque groupe — donc le même
mouvement autant de fois qu'il a de jambes, **en additionnant un débit et le crédit qui lui
répond** comme s'il s'agissait de deux anomalies distinctes.

| | Annoncé | Corrigé |
|---|---|---|
| Mouvements dupliqués | 178 | **75** |
| Volume dupliqué | 289 631 995 600 | **138 888 836 088** |
| Dont période d'audit | 124 / 76,7 Md | **53 / 34,7 Md** |

Facteur **2,2** sur un constat classé CRITIQUE. Les 178 restent exacts comme nombre de jambes,
et le tableau par compte — qui mesure l'incidence sur chaque solde — était, lui, correct.

## 19.2 ⚠ Des écritures de CORRECTION étaient comptées comme des doublons

Le mouvement `3670741|24560880` n'a qu'une seule référence d'interface. Ce qui le faisait
détecter, c'étaient deux écritures manuelles ultérieures sur `007ACB00034 SCB FRANKFURT`.
Autrement dit : **la correction était comptée comme l'anomalie qu'elle corrige**.

Les références de l'interface commencent toutes par `099MNIP`. La détection y est désormais
restreinte. Deux faux positifs éliminés.

## 19.3 ⚠ Une source manquait dans `calypso_enrichi`

Le jeu de données Calypso était construit sur `ecritures_calypso`, `comptes_calypso` et
`grand_livre` — **pas** sur `comptes_cles`. Or le compte de règlement `099ACO00001` ne figure
ni au grand livre des 41 comptes clés ni dans l'extraction Calypso : **1 435 de ses jambes ne
vivent que dans l'extraction des comptes clés**, dont 11 à libellé structuré, pour
2 809 785 592 XAF.

C'est ce qui m'a fait conclure à tort que le mouvement `4296327|25801318` n'avait été corrigé
que sur une jambe : la jambe nostro de la correction existait, dans une source que je ne lisais
pas. Source ajoutée.

## 19.4 ✓ Un fait que le rapport passait sous silence : la banque en corrige une partie

**7 des 75 doublons ont fait l'objet d'une contre-passation manuelle.** Le rapport n'en disait
rien et présentait le défaut comme jamais repris.

| Mouvement | Date du doublon | Montant | Correction | Délai | Résidu |
|---|---|---|---|---|---|
| 24421131 | 26/02/2026 | 12 791 289 | 22/05/2026 | **85 j** | **12 791 289** |
| 25597236 | 06/08/2026 | 2 000 000 000 | 27/08/2026 | 21 j | 0 |
| 25816929 | 02/09/2026 | 4 305 000 000 | 15/09/2026 | 13 j | 0 |
| *(4 autres)* | | | | 12 à 15 j | 0 |

Un dispositif de détection existe donc — mais il est **partiel** (7 sur 75), **tardif** (12 à
85 jours, bien au-delà de l'arrêté que le doublon peut traverser) et **manuel** (référence
Flexcube hors interface, saisie `TOKAID000203`, validation `ZOGOID000241`). Le cas `24421131`
n'a été corrigé que sur sa jambe nostro, laissant le pont doublé.

Les écritures de correction sont groupées : `0990028262580001` du 15/09/2026 reprend à elle
seule cinq doublons, sur 38 lignes équilibrées.

## 19.5 L'incidence sur les soldes, enfin datée

Le tableau par compte donnait l'impact sur **toute l'extraction**. Il donne désormais les deux
colonnes, et exclut les mouvements contre-passés.

| Compte | Au 30/06/2026 | Fin d'extraction |
|---|---|---|
| 552400100 emprunt | 5 000 000 000 | 30 000 000 000 |
| 952100100 collatéral | −10 000 000 000 | −16 000 000 000 |
| **099ACO00001 BEAC** | **−665 441 761** | 11 693 426 801 |

Je disais « le nostro BEAC est surévalué de 11,7 Md ». À la date d'arrêté, l'incidence est de
**−665 441 761 XAF** — les 11,7 Md sont un cumul de fin d'extraction, dominé par août 2026.

## 19.6 Vérification des doublons les plus lourds

`4184547|25573388` : deux références `099MNIP26216009H` et `...009N`, même jour, mêmes comptes,
25 Md chacune → dette `552400100` doublée à 50 Md. Doublon avéré.

`4024895|25229148` : deux références le 25/06/2026, 10 Md de collatéral hors bilan chacune →
`952100100` doublé. **Dans la période d'audit**, et c'est ce qui fausse le hors bilan de 10 Md
à l'arrêté.

## 19.7 État

55 anomalies — 9 critiques — sur 11 sections et 69 contrôles. Le constat 6.7 reste CRITIQUE :
un montant divisé par deux ne change pas la nature du défaut, et la correction manuelle et
tardive de 7 cas sur 75 le confirme plutôt qu'elle ne l'atténue.

**Règle retenue** : *compter les anomalies à la maille de l'événement, jamais à celle de
l'écriture.* Et : *une écriture de correction ne doit jamais entrer dans la population des
anomalies qu'elle corrige.*

---

# SESSION 20 — Revue manuelle du point 6.4 : le pont a fonctionné avant de casser

Demande : revue manuelle du contrôle 6.4, les comptes de liaison Calypso non apurés.
Le solde est exact, mais le constat disait deux choses fausses et n'expliquait pas son propre
chiffre.

## 20.1 ✓ D'abord, la vérification de couverture

Leçon de la session 19 : vérifier qu'aucune source ne manque. Les trois comptes de liaison sont
intégralement couverts — 3 723 lignes, identiques dans `grand_livre` et `toutes_ecritures`. Le
solde de **−133 405 764 689 XAF** au 30/06/2026 est confirmé.

## 20.2 ⚠ « Aucun retour à zéro » — faux, et c'est le contraire qui est instructif

Le constat affirmait qu'aucun retour à zéro n'était constaté « depuis l'ouverture de ces
comptes, soit 12 mois ». En reconstituant le solde cumulé jour par jour :

| Compte | Ouverture | Retours à zéro | Dernier retour |
|---|---|---|---|
| 467000186 | 16/06/2025 | **4** | 24/06/2025 |
| 467000188 | 16/06/2025 | **55** | **22/10/2025** |
| 467000243 | 17/07/2025 | **5** | 19/09/2025 |

**64 retours à zéro au total.** Le dispositif a donc bien fonctionné — ce qui écarte
l'hypothèse d'un paramétrage défectueux dès l'origine et rend le constat plus précis, pas
moins grave : ce n'est pas une dérive lente mais une **rupture datable**. Le 467000188 se
soldait normalement pendant quatre mois, puis plus jamais après le 22/10/2025.

C'est cette date qu'il faut rapprocher des évolutions de l'interface.

## 20.3 ⚠ « Un solde qui ne fait que croître » — faux aussi

467000186 : 23 journées de hausse contre 64 de baisse. 467000188 : 29 contre 27. Le solde
**oscille** sans jamais se résorber. Formulation corrigée.

## 20.4 ⚠ L'écart de 8,7 Md entre 6.4 et 11.6 n'était pas expliqué

6.4 annonçait −133 405 764 689 et 11.6 −124 704 289 100 sans que rien ne rapproche les deux.
La décomposition, désormais au rapport :

| Composante | Deals | Montant |
|---|---|---|
| Déversement resté incomplet (11.6) | 201 | −124 704 289 100 |
| **Ouverts à la clôture, soldés après** | **12** | **−8 701 574 995** |
| Réévaluations sans identifiant de deal | — | +99 406 |
| **SOLDE AU 30/06/2026** | | **−133 405 764 689** |

**La réconciliation est exacte au franc près.**

## 20.5 ✓ Les douze deals à cheval : une campagne de régularisation

Population que ni 6.4 ni 11.6 n'isolait. Exemple du deal 3797100 :

| Date | Référence | Compte | Sens | Montant |
|---|---|---|---|---|
| 22/04/2026 | `099MNIP26112005T` | 099ACO00001 | D | 3 000 000 000 |
| 22/04/2026 | `099MNIP26112005T` | 467000186 | C | 3 000 000 000 |
| **14/09/2026** | `099MNIP2625700K0` | 467000186 | **D** | 3 000 000 000 |
| **14/09/2026** | `099MNIP2625700K0` | 099ACO00001 | **C** | 3 000 000 000 |

Un règlement en trésorerie **sans aucune jambe de bilan**, resté ouvert 145 jours, puis annulé
par Calypso — référence d'interface, nouvel identifiant de mouvement, sens inverse : c'est la
convention d'annulation du contrôle 1.5.

**Les douze ont été soldés entre le 10 et le 15 septembre 2026**, soit la même semaine que les
corrections de doublons du contrôle 6.7. Campagne de régularisation, pas dénouement au fil de
l'eau. Durées d'ouverture : **108 à 211 jours**, toutes à cheval sur la clôture du 30/06/2026.

## 20.6 État

55 anomalies — 9 critiques — sur 11 sections et 69 contrôles. 6.4 reste CRITIQUE et gagne en
précision : le défaut a une date de naissance par compte, et son solde est intégralement
expliqué.

**Règle retenue** : *un solde anormal doit être décomposé jusqu'à ce que ses composantes
s'additionnent exactement à lui.* Les 8,7 Md d'écart entre deux de mes contrôles cachaient une
population entière — douze opérations ouvertes six mois et annulées après coup.

---

# SESSION 21 — Revue manuelle du point 5.2 : le mauvais terme de comparaison

Demande : revue manuelle du contrôle 5.2, l'écart entre les intérêts courus repris dans Calypso
et le solde du compte d'origine. Le contrôle annonçait **125 570 147 XAF**. Le chiffre est faux,
parce que le terme de comparaison l'était.

## 21.1 ⚠ Comparer à un solde de compte n'a pas de sens ici

Le contrôle opposait la reprise Calypso (3 089 462 049) au **solde du compte 511800100** à
apurer (2 963 891 902). Or ce solde contient deux choses de natures différentes : les courus des
positions qui migrent, et des courus résiduels de positions **déjà sorties du portefeuille**.

La seule comparaison qui ait un sens oppose la reprise au couru **porté par les 65 positions
qui ont effectivement migré**.

| | Montant |
|---|---|
| Couru porté par les positions migrées | 2 725 169 325 |
| Couru repris par Calypso | 3 089 462 049 |
| **ÉCART DE REPRISE** | **364 292 724** |

**L'écart réel est de 364 292 724 XAF, près du triple des 125 570 147 annoncés.**

## 21.2 ✓ Ce qui se rapproche parfaitement, et qu'il fallait dire

Le contrôle ne le disait pas : **les 65 positions se rapprochent exactement**. 65 sortent de
Flexcube, 65 entrent dans Calypso, nominal identique de **126 688 763 333 XAF**, et chaque
nominal se retrouve des deux côtés comme multi-ensemble. La reprise du portefeuille est
exhaustive.

**10 positions entrent sans aucun couru — et c'est normal.** Ce sont les bons du Trésor logés
au compte `511210100`, 19 485 000 000 de nominal : des titres **à escompte**, sans coupon, dont
la rémunération vit en compte de régularisation et non en créances rattachées. Le rapport
laissait planer un doute sur ces dix positions.

## 21.3 ⚠ Un second écart, que rien ne relevait

| Composante du solde à apurer | Montant |
|---|---|
| Rattachable aux positions migrées | 2 725 169 325 |
| **NON rattachable** | **238 722 577** |
| Solde du compte (contrôle 5.3) | 2 963 891 902 |

Ces 238 722 577 XAF sont des créances rattachées à des titres **dénoués de longue date**,
jamais apurées, et soldées à la migration sans avoir jamais été encaissées. Le compte portait
un couru résiduel sur **412 contrats déjà sortis du portefeuille**.

Précision de méthode consignée au rapport : le nombre de contrats et le montant non rattachable
ne se recoupent pas exactement, certains de ces contrats portant un solde négatif — effet des
apurements excédentaires antérieurs du contrôle 3.4.

## 21.4 ⚠ Une population parasite dans la mesure de la reprise

Le compte `512800100` reçoit **89 lignes** le jour de la bascule, pas 55 :
- 55 `ACCRUAL_BS` — la reprise, 3 089 462 049
- **34 `TRADE VALUATION/TDWAC_ACCRUAL/`** — 18 072 130, le couru du jour de Calypso lui-même

Le net du compte ce jour-là est donc 3 107 534 179 et non 3 089 462 049. Un lecteur rapprochant
le chiffre du contrôle au solde du compte trouvait 18 M d'écart inexpliqué. Le constat le dit
désormais.

## 21.5 ⚠ Ce que le rapport ne pouvait pas faire, et ne le disait pas

Un rapprochement position par position est **impossible** avec les données disponibles :
- les deux systèmes n'ont **aucun identifiant commun** — Flexcube désigne une position par sa
  référence de contrat, Calypso par le code du titre ;
- **35 des 65 positions partagent leur nominal avec une autre**, sur 9 valeurs distinctes.

J'avais d'abord tenté un appariement 1-1 par nominal trié, qui produisait des écarts par
position de plus de 150 M. **Ces chiffres étaient des artefacts d'appariement** et n'ont pas été
retenus. Le rapport énonce désormais la limite au lieu de la contourner.

## 21.6 État

55 anomalies — 9 critiques, 20 élevées, 23 moyennes, 3 faibles — sur 11 sections et 69 contrôles.
5.2 reste ELEVEE, avec un écart triplé et deux constats nouveaux.

**Règle retenue** : *avant de chiffrer un écart, vérifier que les deux termes portent sur la
même population.* Et : *un appariement qui n'est pas déterministe ne produit pas un constat —
il produit du bruit qu'il faut jeter.*

---

# Session 22 — Deuxième vague d'extractions : les comptes hors des 41

## 22.1 Ce qui a été reçu

Trois fichiers, en CP1252, dates `JJ-MMM-AA` :

| Fichier | Lignes | Période |
|---|---|---|
| `099ACO00001.csv` | 13 165 | 27/09/2023 → 29/06/2026 |
| `32_accounts.csv` | 17 895 | 13/06/2022 → 18/09/2026 |
| `additional key account.csv` | 6 244 | 05/08/2022 → 18/09/2026 |

**Premier réflexe : mesurer ce qui est réellement nouveau.** Dédoublonnage sur
`TRN_REF_NO|AC_NO|DRCR_IND|LCY_AMOUNT|AMOUNT_TAG|STMT_DT` contre les 511 326 clés déjà connues :

- `099ACO00001.csv` — **0 ligne nouvelle**. L'extraction du nostro BEAC était déjà complète
  (18 914 lignes uniques). Le contrôle 11.8 n'est donc pas à reprendre.
- `32_accounts.csv` — 17 895 nouvelles, sur **8 comptes seulement**.
- `additional key account.csv` — 2 770 nouvelles ; le reste recouvrait 466000107, 467000186 et
  467000188.

## 22.2 Le piège du dédoublonnage ligne à ligne

Premier chargement : 265210100 tombait de 5 à 4 lignes. Le recouvrement entre les deux fichiers
porte sur des **comptes entiers**, pas sur des lignes isolées — et une écriture peut légitimement
porter deux jambes identiques sur le même compte (quatre titres nantis le même jour, dont deux de
même nominal).

**Règle retenue** : *quand deux sources se recouvrent par compte, on retient pour chaque compte
la source qui en porte le plus de lignes. On ne dédoublonne jamais ligne à ligne un fichier
comptable : la multiplicité y est porteuse de sens.*

## 22.3 Ce que les comptes vides disent

24 des 34 comptes demandés sont revenus **sans un seul mouvement**. C'est un résultat, pas une
absence de résultat :

- toute la série PCEC de la **pension livrée** (5213, 5216, 5310, 5320, 5380, 5390, 5221-5224,
  7020, 6062, 7062) ;
- les **provisions** du portefeuille de placement (5914x, 5915) ;
- le **hors-bilan du marché gris** (953, 954, 955) ;
- `467000187 ATTENTE OPERATION TRESO CALYPSO` — ouvert, jamais servi.

## 22.4 Correction que je me suis faite à moi-même

J'ai d'abord écrit, en 12.2, que « la banque n'a enregistré ni une dette de pension ni un franc
de charge d'intérêt ». **C'était faux.** Vérification sur le grand livre des 41 :

| Compte | Lignes | Mouvements bruts |
|---|---|---|
| 552400100 EMPRUNT AU JR LE JR | 164 | 8 253 000 000 000 |
| 601100100 INT. OPS MARCHÉ MONÉTAIRE | 195 | 8 950 081 952 |
| 952100100 / 995000100 hors-bilan garantie | 1 849 | 10 039 318 740 000 |

La banque **enregistre** ses refinancements BEAC et **suit** son collatéral — mais sur les
comptes de l'**emprunt interbancaire au jour le jour**, pas sur ceux de la pension. Le constat
est un **classement**, non une omission ; gravité ramenée de CRITIQUE à ELEVEE. Seules les
cessions-rétrocessions du 8.2 restent sans aucun enregistrement.

Même correction en 12.4 : j'avais écrit que le nantissement n'était pas suivi. Il l'est, en
continu, au hors-bilan. Les 6,2 Md du 31/12/2025 sur 265210100 font **double emploi**.

**Règle retenue** : *avant d'écrire qu'un traitement est absent, chercher où il est fait
autrement. Un compte vide ne prouve l'absence d'une opération que si aucun autre compte ne la
porte.*

## 22.5 Ce que la deuxième vague a permis de clore

**Le contrôle 5.3 est fermé.** La troisième jambe manquante de l'écriture de correction
`099000b252120001` est un **DÉBIT de 1 994 516 XAF sur 622000100 COMM ET FRAIS SUR TITRES**,
même référence, même jour, même opérateur, libellé *DIFF/ACCRUALS LIQUIDATION RELATED TO
CALYPSO GO LIVE*. 1 205 231 891 + 1 994 516 = 1 207 226 407 : l'écriture s'équilibre.

Le constat ne s'affaiblit pas — il se déplace : le reliquat n'a pas été analysé, il a été
**éteint en charges**.

## 22.6 Les six constats nouveaux

| Code | Gravité | Ce qui est établi |
|---|---|---|
| 12.1 | ELEVEE | `622000100` sert de fourre-tout : 261 écritures, dont 146 étrangères à son objet ; 1 470 811 156 XAF de **crédits sur un compte de charge** (compensation interdite) ; 626 M de décotes mal imputées ; 29 écritures de ≤ 100 XAF |
| 12.2 | ELEVEE | Les pensions BEAC sont comptabilisées en emprunts au jour le jour ; 13 des 14 comptes PCEC de pension sont vides |
| 12.3 | ELEVEE | `466000107` : 32,1 Md de mouvements bruts, dont 27,2 Md d'annulation-réenregistrement d'intérêts titres en mars-avril 2024 ; solde de 1 075 474 620 XAF au 30/06/2026, dont une seule écriture *« Rclss COMPTE INTER BRANCHES »* du 31/12/2025 |
| 12.4 | MOYENNE | 6,2 Md nantis le jour de l'arrêté sur un compte de classe 2 autrement inutilisé, repris 167 jours plus tard dans l'écriture d'apurement SCB |
| 12.5 | **CRITIQUE** | Portefeuille SCB de 27,2 Md : reçu en **titres**, porté au **nostro BEAC** pendant 189 jours, **traversant l'arrêté du 31/12/2025** |
| 12.6 | MOYENNE | 26 comptes dormants ; **aucune dépréciation** sur le portefeuille en trois exercices ; comptes restant à extraire |

## 22.7 Le 12.5, trouvé en tirant un fil

Le compte `454000101 COMPTE DE CONVERSION BONS DE TRESOR` ne porte que **deux lignes**. C'est ce
qui a attiré l'attention : un compte de conversion servi cinq mois et demi après la bascule.

En remontant les références :

| Date | Écriture | Débit | Crédit |
|---|---|---|---|
| 05/12/2025 | `0999001100074302` — user `MIGRATION`, sans libellé | 454000101 : 27,2 Md | — |
| 09/12/2025 | `0990004253430001` — *Securities received from SCB to be booked manually* | **099ACO00001 : 27,2 Md** | 454000101 : 27,2 Md |
| 16/06/2026 | `0990023261670001` — entrée en portefeuille, 7 titres | 511210100 : 33,4 Md | 099ACO00001 : 27,2 Md |

La jambe du 09/12/2025 **débite le nostro BEAC** alors que la banque a reçu des titres, non de la
trésorerie. Au 31/12/2025, le nostro publié comprend 27,2 Md qui n'existent pas, et le
portefeuille ne comprend pas les titres correspondants. **Le bilan est faux des deux côtés.**

C'est la troisième fois que le nostro BEAC porte une surévaluation non détectée par le
rapprochement bancaire — après 5.3 (1,2 Md, 45 jours) et 11.8 (90,1 Md).

## 22.8 Ce qui reste à extraire

Le plan de comptes révèle trois comptes que les libellés désignent mais qu'aucune extraction ne
couvre :

- **`511800101 CREANCES RATTACHEES - MANUELLES`** — cité en toutes lettres dans 466000107
  (*« Reversal of 511800101 in 466000107 »*). Un **second compte de courus, réservé aux écritures
  manuelles**, vit en parallèle de 511800100. Les contrôles 5.3 et 11.7 reposent donc sur une vue
  partielle.
- `511801100 SCB CREANCES RATTACHEES - PLACEMENT` — courus du portefeuille repris de SCB.
- `601200100` / `601200101 INT. SUR OPS MARCHE MONETAIRE - BEAC` — la charge d'intérêt face à la
  banque centrale.

## 22.9 État

**61 anomalies — 10 critiques, 23 élevées, 25 moyennes, 3 faibles — sur 12 sections et
75 contrôles.**
