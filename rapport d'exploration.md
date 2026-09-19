# Rapport d'exploration — Données du Département de la Trésorerie

**Mission** : audit des activités du Département de la Trésorerie (gestion des investissements sur
les marchés financiers et opérations de change).
**Période d'audit** : 27/09/2023 → 30/06/2026.
**Périmètre des données** : 11 fichiers CSV extraits du core banking Flexcube (97 Mo, 492 973 lignes
d'écritures + 603 lignes de référentiel contrats).
**Méthode** : exploration en Python 3 / pandas 3.0.6 en ligne de commande. Tous les numéros de
compte, références et identifiants sont chargés en **chaînes de caractères** afin de préserver les
zéros de tête et d'éviter toute conversion numérique parasite.
**Référentiel comptable applicable** : Plan Comptable des Établissements de Crédit (PCEC) de la
CEMAC — COBAC.

> Ce document est un **rapport d'exploration** : il décrit ce que contiennent les données, comment
> le métier y est codifié, et signale les points qui méritent investigation. Il ne constitue pas
> encore un rapport d'audit : les constats listés en §8 sont des **pistes à corroborer** auprès de
> la banque avant toute conclusion.

---

## 1. Inventaire et architecture des données

### 1.1 Les cinq jeux de données

| Jeu de données | Fichier(s) | Lignes | Période couverte | Nature |
|---|---|---:|---|---|
| **Référentiel contrats MM** | `MM_CONTRACT.csv` | 603 | trade 30/06/2022 → 12/06/2025 | Caractéristiques des contrats (nominal, taux, échéance, contrepartie) |
| **Écritures Money Market** | `money_market_transactions.csv` | 59 446 | 27/09/2023 → **16/06/2025** | Comptabilité du module MM de Flexcube |
| **Écritures Calypso** | `calypso_transactions_…part_1..4.csv` | 194 938 | **16/06/2025** → 18/09/2026 | Déversement de Calypso dans le grand livre |
| **Écritures de change clientèle** | `FX_TRANSACTIONS.csv` | 48 122 | 27/09/2023 → 18/09/2026 | Transferts et change clientèle (module FT) |
| **Historique des comptes clés** | `transaction_history_of_key_account_…part_1..4.csv` | 190 467 | 27/09/2023 → 18/09/2026 | Tous les mouvements des nostri, du compte BEAC et du compte courtier |

Les fichiers `part_N` sont bien des **découpages d'un même export** (mêmes en-têtes, même encodage
UTF‑8 avec BOM, continuité chronologique) ; ils ont été rechargés par concaténation.

### 1.2 Une structure commune à toutes les écritures
Les quatre sources de mouvements partagent **exactement les mêmes 17 colonnes**. Il s'agit d'un
export d'une vue d'écritures Flexcube (type `ACVW_ALL_AC_ENTRIES`). Chaque ligne est **une jambe**
d'écriture (un débit ou un crédit), et non une opération complète.

| Colonne | Signification | Observations |
|---|---|---|
| `DESCRIPTION` | Libellé libre | Vide en MM ; **porteur de toute l'information deal en Calypso** (cf. §4.2) |
| `TRN_REF_NO` | Référence de transaction Flexcube | 16 caractères, codifiée (cf. §1.3) |
| `AC_NO` | Compte mouvementé | Soit un **compte général** (9 chiffres), soit un **compte client / nostro** |
| `AC_CCY` | Devise du compte | XAF, EUR, USD, GBP, ZAR |
| `FCY_AMOUNT` | Montant en devise | Renseigné uniquement si le compte est en devise |
| `LCY_AMOUNT` | Montant en monnaie locale (XAF) | Toujours renseigné — **base de toutes les analyses** |
| `TRN_DT` | Date comptable | |
| `DRCR_IND` | Sens : `D` = débit, `C` = crédit | |
| `USER_ID` / `AUTH_ID` | Saisisseur / valideur | Support du contrôle **« 4 yeux »** |
| `AMOUNT_TAG` | Étiquette de montant = **nature de l'événement comptable** | Clé de lecture des schémas |
| `STMT_DT` | Horodatage complet (date + heure) | Permet les tests d'heures ouvrables |
| `AC_NATURAL_GL` | Compte général de rattachement | Renseigné quand `AC_NO` est un compte client |
| `PRODUCT` | Code produit Flexcube (4 caractères) | |
| `AC_GL_DESC` | Libellé du compte | |
| `MODULE` | Module d'origine | `MM`, `FT`, `DE`, `RE`, `IC`, `RT`, `LC`, `CL` |
| `EXTERNAL_REF_NO` | Référence du système externe | **Clé de rapprochement avec Calypso** |

### 1.3 Codification des références — décodée et vérifiée

```
099   OTAP   23   280   0004
└─┬┘  └─┬─┘  └┬┘  └─┬┘  └─┬─┘
  │      │     │     │      └── séquence du jour (4 car., alphanumérique : 0-9, a-z, A-Z)
  │      │     │     └───────── quantième julien (jour de l'année, 001-366)
  │      │     └─────────────── année sur 2 chiffres
  │      └───────────────────── code PRODUIT (4 caractères)
  └──────────────────────────── code AGENCE — 099 = siège
```

**Vérification effectuée** : sur les 603 contrats du référentiel, le couple agence+produit extrait
de la référence correspond aux colonnes `BRANCH`+`PRODUCT` dans **100 %** des cas, et la date
reconstituée à partir du quantième julien est égale à `BOOKING_DATE` dans **100 %** des cas.
La codification est donc établie avec certitude et peut servir de contrôle de cohérence.

### 1.4 Articulation des quatre sources (absence de double comptage)
Un rapprochement ligne à ligne (clé = référence + compte + sens + tag + montant + horodatage)
montre que les sources sont **complémentaires et non redondantes** :

| Périmètre | Lignes |
|---|---:|
| Écritures présentes **uniquement** dans Calypso | 192 037 |
| Écritures présentes **uniquement** dans les comptes clés | 180 180 |
| Écritures présentes **uniquement** dans MM | 58 368 |
| Écritures présentes **uniquement** dans FX | 43 223 |
| Communes **FX ↔ comptes clés** | 4 899 |
| Communes **Calypso ↔ comptes clés** | 2 901 |
| Communes **MM ↔ comptes clés** | 994 |

Le fichier des comptes clés est donc **transversal** : il contient les jambes qui touchent les
nostri et le compte BEAC, quel que soit le module d'origine. Toute consolidation doit dédoublonner
sur cette clé.

---

## 2. Le métier de la trésorerie tel qu'il apparaît dans les données

L'exploration fait apparaître **cinq activités distinctes** :

1. **Portefeuille de titres souverains CEMAC** — obligations (OTA) et bons du trésor (BTA) émis par
   les États du Cameroun, du Gabon, du Congo et de Guinée Équatoriale. C'est le cœur historique.
2. **Refinancement auprès de la BEAC** — pensions livrées (repo) garanties par les titres du
   portefeuille. Activité **apparue en novembre 2025** dans Calypso, absente auparavant.
3. **Change au comptant et à terme** pour compte propre — via Calypso, contreparties bancaires
   et courtier (STONEX).
4. **Change et transferts clientèle** — module FT de Flexcube, produits `CSTF`, `CSBU`, `IN03`.
5. **Vente de titres à la clientèle** (activité de distribution) — book `ABCM_FI.Sales`, avec
   comptabilisation hors bilan en valeurs gérées pour compte de tiers.

### 2.1 Deux systèmes successifs, une date de bascule unique
Le basculement de Flexcube MM vers Calypso s'est opéré le **16 juin 2025**, sans recouvrement :

```
27/09/2023 ────────── Flexcube module MM ──────────► 16/06/2025 ──────── Calypso ────────► 18/09/2026
   (contrats + écritures dans Flexcube)          BASCULE        (deals dans Calypso,
                                                                 écritures GL seules dans Flexcube)
```

Le référentiel `MM_CONTRACT` s'arrête d'ailleurs au 12/06/2025 pour les dates de trade, ce qui est
parfaitement cohérent : **aucun deal n'est plus créé dans Flexcube après la bascule**.

---

## 3. Le portefeuille sous Flexcube (module MM)

### 3.1 Catalogue de produits

| Produit | Lecture retenue | Contrats | Nominal cumulé (XAF) |
|---|---|---:|---:|
| `OTAP` | **O**bligations du **T**résor **A**ssimilables — **P**lacement | 488 | 992 642 023 333 |
| `TBTR` | Bons / titres du **T**résor — **TR**ansaction | 111 | 194 677 000 000 |
| `BTTR` | **B**ons du **T**résor — **TR**ansaction | 2 | 4 000 000 000 |
| `MTPD` | Placement à terme (dépôt) | 2 | 540 000 000 |

100 % des contrats sont en **XAF**, sur l'agence **099** (siège), avec `PRODUCT_TYPE = L`
(*Lending* : la banque est **prêteuse / souscriptrice**, jamais emprunteuse dans ce module).

### 3.2 Contreparties : exclusivement des souverains CEMAC

| Code contrepartie | Contrepartie | Contrats | Nominal (XAF) | Part |
|---|---|---:|---:|---:|
| `040730818` | ÉTAT DU CAMEROUN | 232 | 645 587 510 000 | 54,2 % |
| `040730820` | ÉTAT DU GABON | 200 | 365 704 623 333 | 30,7 % |
| `040730819` | ÉTAT DU CONGO | 122 | 142 113 450 000 | 11,9 % |
| `040730821` | ÉTAT DE GUINÉE ÉQUATORIALE | 49 | 38 453 440 000 | 3,2 % |

Aucune diversification hors souverains CEMAC sur toute l'histoire du module.

### 3.3 Plan de comptes mobilisé (PCEC)

| Compte | Libellé | Rôle |
|---|---|---|
| `511410100` | Obligations du Trésor assimilables — placement | Nominal des OTA |
| `511210100` | Bons du Trésor (BTA) — placement | Nominal des BTA (Calypso) |
| `512200100` | Bons du Trésor — transaction | Nominal des bons (MM) |
| `512410100` | Obligations du Trésor assimilables — transactions | Nominal des obligations (Calypso) |
| `511800100` | **Créances rattachées — placement** | Intérêts courus sur titres de placement |
| `512800100` | **Créances rattachées — transaction** | Intérêts courus sur titres de transaction |
| `472200106` | Produits perçus d'avance sur bons du Trésor | Décote des BTA, étalée |
| `472200108` | Autres produits comptabilisés d'avance | Prime / décote des obligations |
| `733200100` / `733400100` | Revenus de bons du Trésor / d'obligations | Produits d'intérêt |
| `734200100` / `734400100` | Idem — **second jeu de comptes** | Utilisé par Calypso (cf. §8.11) |
| `591400100` | Provision pour dépréciation des obligations et bons assimilés | Dépréciation |
| `099ACO00001` | Banque des États de l'Afrique Centrale | **Compte de règlement espèces** |

### 3.4 Schémas comptables du module MM (reconstitués depuis les données)

L'étiquette `AMOUNT_TAG` identifie sans ambiguïté l'événement. Les schémas ci-dessous ont été
obtenus en regroupant les jambes par référence, date et étiquette ; ils sont **stables à plus de
99 %** (les rares exceptions sont des regroupements d'écritures de fin de journée).

| Événement (`AMOUNT_TAG`) | Occurrences | Schéma — obligations (OTAP) |
|---|---:|---|
| `PRINCIPAL` — acquisition | 840 | **D** `511410100` / **C** `099ACO00001` |
| `INT_BT_ACCR` — couru quotidien | 57 446 | **D** `511800100` / **C** `733400100` |
| `PRINCIPAL_LIQD` — liquidation du nominal | 894 | **D** `099ACO00001` / **C** `511410100` |
| `INT_BT_LIQD` — encaissement d'intérêt (bons) | 152 | **D** `099ACO00001` / **C** `472200106` |
| `INT_BT_DADJ` — ajustement de décote | 102 | **D** `472200106` / **C** `099ACO00001` |
| `INT_OB_ACCR` — couru (bons transaction) | 12 | **D** `512800100` / **C** `733200100` |

**Distinction importante entre obligations et bons du Trésor.** Les bons sont des titres à
**revenu précompté** : la décote encaissée à la souscription est portée au compte de régularisation
`472200106` (produit perçu d'avance), puis **reprise au résultat au fil du temps** par
**D `472200106` / C `733200100`**. Les obligations, à coupon, suivent la logique classique
d'intérêts courus. Ce traitement différencié est conforme au PCEC.

### 3.5 Cycle de vie d'un titre sous Flexcube

```
  ① TRADE_DATE / VALUE_DATE     ┌──────────────────────────────────────────────┐
     Acquisition                │ D 511410100 (portefeuille)                   │
     tag PRINCIPAL              │ C 099ACO00001 (décaissement BEAC)            │
                                └──────────────────────────────────────────────┘
  ② chaque jour ouvré           ┌──────────────────────────────────────────────┐
     Couru d'intérêts           │ D 511800100 (créances rattachées)            │
     tag INT_BT_ACCR            │ C 733400100 (produits)                       │
                                │ [bons : D 472200106 / C 733200100]           │
                                └──────────────────────────────────────────────┘
  ③ MATURITY_DATE               ┌──────────────────────────────────────────────┐
     Remboursement              │ D 099ACO00001 (encaissement BEAC)            │
     tag PRINCIPAL_LIQD         │ C 511410100 (sortie du portefeuille)         │
                                └──────────────────────────────────────────────┘
```

**Intégrité de la partie double vérifiée** : 29 723 débits pour 29 723 crédits, somme des débits
moins crédits **égale à zéro**, et **aucune** des 24 504 écritures (regroupées par référence, date
et étiquette) n'est déséquilibrée.

### 3.6 La pratique de « liquidation / réouverture »

**C'est le point de compréhension le plus important du module MM.** Sur 447 liquidations
observées, seules **30 (6,7 %)** interviennent à l'échéance contractuelle :

| Moment de la liquidation | Nombre | Montant (XAF) |
|---|---:|---:|
| **À l'échéance contractuelle** | 30 | 40 383 600 000 |
| Anticipée de moins d'un mois | 17 | 36 624 800 000 |
| Anticipée de 1 à 12 mois | 124 | 225 539 360 000 |
| **Anticipée de plus d'un an** | 271 | 735 156 163 333 |
| Après l'échéance | 5 | 7 496 000 000 |

Deux caractéristiques éclairent ce phénomène :
- le montant liquidé est **toujours strictement égal au nominal contractuel** (0 écart sur 447) —
  ce qui exclut une cession à la valeur de marché ;
- sur les 331 liquidations anticipées hors migration, **256 (77 %) s'accompagnent le jour même
  d'une nouvelle acquisition sur la même contrepartie**.

**Interprétation** : Flexcube ne permettant pas le remboursement partiel d'un contrat MM, la
trésorerie procède par **clôture intégrale puis réouverture du solde**. On observe même **29 contrats
créés et liquidés le jour même** (83,7 Md XAF), dont certains à plus de 1 380 jours de leur échéance.

**Conséquence méthodologique majeure** : les **volumes bruts du module MM ne sont pas des flux
économiques**. Le compte BEAC affiche 2 062 Md XAF de mouvements bruts pour un portefeuille dont
l'encours réel est d'environ 127 Md XAF. Toute analyse de volumétrie, de rotation du portefeuille
ou de flux de trésorerie **doit être menée en net**, après neutralisation des couples
liquidation/réouverture du même jour.

---

## 4. Le portefeuille sous Calypso

### 4.1 Confirmation du mode d'interfaçage
Le fonctionnement décrit par la banque est **intégralement confirmé** par les données : Calypso ne
déverse que de la comptabilité.

| Caractéristique | Valeur | Taux |
|---|---|---|
| `MODULE` | `DE` (*Direct Entry* — écriture directe au grand livre) | 100 % |
| `PRODUCT` | `MNIP` (produit technique d'interface) | 100 % |
| `USER_ID` = `AUTH_ID` | `CALYPSOUSR` | 100 % |
| `AMOUNT_TAG` | `TXN_AMT` (montant de transaction, générique) | 100 % |

**Aucun contrat n'est créé dans Flexcube** après la bascule : la table `MM_CONTRACT` n'est plus
alimentée. Il en découle deux conséquences d'audit importantes :
- l'étiquette `AMOUNT_TAG`, qui portait la nature de l'événement sous MM, **perd toute valeur
  informative** sous Calypso : l'information est déportée dans `DESCRIPTION` ;
- **le référentiel des deals Calypso n'a pas été fourni**. Nominal, taux, échéance et contrepartie
  des 1 985 deals ne sont connus qu'indirectement, via le libellé des écritures.

### 4.2 Décodage du champ `DESCRIPTION`
Quatre formats coexistent, identifiables au nombre de séparateurs `|` :

**Format A — écritures de flux liées à un deal (25 534 lignes)**
```
|2693841|22741787|ACCRUAL_BS|Bond|GOGA|ABCM_FVOCI.Bond|GA000002048-7|BondGOGA/GA000002048-7/XAF/0D/03/29/2027/6%|
 └──┬──┘ └───┬──┘ └────┬───┘ └─┬┘ └┬─┘ └──────┬──────┘ └─────┬─────┘ └───────────────┬──────────────────────┘
 Trade Id  Transfer Id Événement Type Émetteur  Book       Code titre   Type/Émetteur/Code/Devise/…/Échéance/Taux
```
**Format B (22 718)** : `VALUATION|<ÉVÉNEMENT>|<BOOK>|<CODE TITRE>|` — valorisation par titre
**Format C (141 034)** : `VALUATION|<ÉVÉNEMENT>|<BOOK>` — valorisation agrégée
**Format D (5 652)** : `TRADE VALUATION/<ÉVÉNEMENT>/<BOOK>/`

Le champ `EXTERNAL_REF_NO` suit le format **`CLP<TradeId>_<TransferId>_<HHMMSS>`**, est renseigné à
**100 %**, et ses identifiants sont **identiques à 100 %** à ceux du libellé (25 534 vérifications).
**C'est donc la clé de rapprochement Flexcube ↔ Calypso**, et le seul moyen de reconstituer un deal.

→ **1 985 deals** et **95 139 mouvements** distincts sur la période.

### 4.3 Les portefeuilles (« books ») Calypso

| Book | Écritures | Activité |
|---|---:|---|
| `ABCM_FVOCI.Bond` | 169 896 | Obligations en juste valeur par capitaux propres |
| `ABCM_FX.Trading.Spot` | 8 482 | Change au comptant (compte propre) |
| `ABCM_MM.Plmt.Tkn.Secured` | 6 886 | **Pension livrée / repo** (placement *reçu*, garanti) |
| `ABCM_FVOCI.Bills` | 4 628 | Bons du Trésor en juste valeur par capitaux propres |
| `ABCM_FX.Trading.Fwd` | 2 960 | Change à terme |
| `ABCM_MM.FundTransfer` | 1 128 | Transferts de trésorerie entre nostri |
| `ABCM_FI.Sales` | 946 | Vente de titres à la clientèle |
| `ABCM_BSB.Bond` | 12 | Buy-Sell-Back obligataire |

**Point d'attention comptable.** La nomenclature `FVOCI` relève d'**IFRS 9**, alors que les comptes
mouvementés relèvent du **PCEC CEMAC** (classes 51 « titres de placement / de transaction »). Il
existe donc, dans le paramétrage Calypso, une **table de correspondance IFRS → PCEC** qui n'est pas
documentée dans les fichiers fournis. Son obtention est nécessaire pour valider le classement
comptable des titres — d'autant que des titres qualifiés de « FVOCI » (assimilables à des titres de
placement) sont enregistrés en `512410100`, compte de **titres de transaction**.

### 4.4 Élargissement des contreparties
Alors que Flexcube MM ne connaissait que 4 souverains, Calypso fait apparaître 25 émetteurs /
contreparties. La codification est lisible : `GO`+ pays = gouvernement (`GOCM` Cameroun, `GOGA`
Gabon, `GOCG` Congo, `GOGQ` Guinée Équatoriale), `BEAC` = banque centrale, puis les banques de la
place (`SGCM`, `ECOBANKCM`, `UBACM`, `BICECCM`, `BGFICM`, `SCBCM`, `ACCESS CAMEROON`,
`ACCESS NIGERIA`…) et `STONEXGB` (courtier de change).

| Contrepartie principale | Écritures |
|---|---:|
| `BEAC` | 13 490 |
| `ACCESS NIGERIA` | 3 320 |
| `ACCESS CAMEROON` | 1 880 |
| `STONEXGB` | 1 390 |
| `SGCM` (Société Générale Cameroun) | 880 |

### 4.5 Nomenclature des événements Calypso

| Événement | Occurrences | Sens métier |
|---|---:|---|
| `ACCRUAL` | 80 216 | Intérêts courus |
| `PREM_DISC_YIELD` | 79 890 | Étalement de prime/décote au **taux d'intérêt effectif** |
| `CST_S_SETTLED` | 8 286 | **Règlement espèces** de l'opération |
| `NOMINAL` | 4 142 | Nominal du titre (entrée en portefeuille ou en garantie) |
| `PREM_DISC_AM` | 3 646 | Étalement de prime/décote **linéaire** (bons) |
| `COT` / `COT_REV` | 3 348 / 3 372 | Engagement de change hors bilan et sa contre-passation |
| `NOMINAL_REV` | 2 666 | Restitution du collatéral |
| `TDWAC_*` | 5 488 | Couru et accrétion en **coût moyen pondéré à la date de négociation** |
| `PRINCIPAL_DEPOSIT` | 522 | Principal du repo |
| `ACCRUAL_BS` / `ACCRUAL_REAL` | 1 050 / 650 | Couru repris au bilan / réalisé à la cession |
| `REALIZED_CLEAN_PL` / `REALIZED_PD_PL` | 300 / 62 | **Plus ou moins-values réalisées** |
| `POSITION_VALUATION` | 164 | Valorisation de la position (dotation/reprise de provision) |
| `INTEREST` | 258 | Intérêts du repo |
| `COUPON_CLIP` | 8 | **Détachement de coupon** |
| `CM.FISales.BRK_COM`, `TRANSACTION_FEE`, `CM.FXPurchase_Fee` | 106 | Commissions |

> **Mise en garde méthodologique essentielle.** Pour `ACCRUAL` et `PREM_DISC_YIELD`, les débits et
> les crédits sont quasi symétriques (20 155 contre 19 836 pour le schéma principal). Calypso
> pratique le **« cancel & rebook »** : chaque jour il contre-passe intégralement le couru de la
> veille, puis repasse le couru cumulé à date. **Les volumes bruts sont donc doublés** : les
> 3 816 Md XAF d'`ACCRUAL` affichés ne représentent en aucun cas une charge ou un produit réel.
> Toute analyse doit être conduite **en net**.

### 4.6 Schémas comptables Calypso

**Obligations (`ABCM_FVOCI.Bond`)**
```
Achat            NOMINAL          D 512410100 (titres)     / C 467000186 (compte de liaison)
                 PREM_DISC        D 467000186              / C 472200108 (prime/décote)
Règlement        CST_S_SETTLED    D 467000186              / C 099ACO00001 (BEAC)
Couru quotidien  ACCRUAL          D 512800100 (courus)     / C 733400100 (produits)   [+ contre-passation]
Étalement TIE    PREM_DISC_YIELD  D 472200108              / C 733400100 ou 734400100 [+ contre-passation]
Dépréciation     POSITION_VALUATION D 734400100            / C 591400100 (provision)
Coupon           COUPON_CLIP      D 467000186              / C 512800100
Cession          REALIZED_CLEAN_PL D 472200108             / C 734400100 (résultat de cession)
```

**Bons du Trésor (`ABCM_FVOCI.Bills`)** : logique identique via `511210100` / `472200106` /
`733200100`, avec **étalement linéaire** (`PREM_DISC_AM`) et non au TIE.

**Pension livrée / repo (`ABCM_MM.Plmt.Tkn.Secured`)** — *la banque emprunte auprès de la BEAC* :
```
Mise en garantie NOMINAL           D 995000100 / C 952100100  (hors bilan : titres affectés)
Tirage           PRINCIPAL_DEPOSIT D 467000188 / C 552400100  (emprunt au jour le jour)
Encaissement     CST_S_SETTLED     D 099ACO00001 / C 467000188
Couru            ACCRUAL           D 601100100 / C 559000101  (charge d'intérêt) [+ contre-passation]
Échéance         INTEREST          D 601100100 / C 467000188
Restitution      NOMINAL_REV       D 952100100 / C 995000100
```

**Change au comptant (`ABCM_FX.Trading.Spot`)**
```
Engagement       COT               D 971400100 (devises vendues non livrées)
                                   / C 971200100 (devises achetées non reçues)
Dénouement       COT_REV           contre-passation de l'engagement
Règlement        CST_S_SETTLED     D <nostro devise> / C 476000102 (contre-valeur)
                                   D 475000102 (position de change) / C 476000160
```
Mécanisme PCEC classique : toute opération en devise transite par le couple
**`475xxx` (position de change, tenue en devise)** / **`476xxx` (contre-valeur, tenue en XAF)**,
l'écart entre les deux constituant le **résultat de change**.

**Change à terme (`ABCM_FX.Trading.Fwd`)** : même logique, avec `972400100` (devises vendues à terme
non livrées) et `979000100` (compte d'ajustement devises hors bilan).

**Vente de titres à la clientèle (`ABCM_FI.Sales`)**
```
NOMINAL        D 998000100 / C 938000100    (hors bilan : valeurs gérées pour compte de tiers)
CST_S_SETTLED  D <compte client> / C 467000243 (liaison miroir), via 452600001 (inter-branches)
BRK_COM        D 467000243 / C 725000100    (commission de courtage)
```

### 4.7 Cycle de vie complet — exemple documenté
**Deal 2693865**, titre `BondGOCM/CM2L00000028/XAF/0D/06/18/2027/6%` (obligation de l'État du
Cameroun, 6 %, échéance 18/06/2027), nominal 1 530 000 000 XAF :

| Date | Événement | Écriture | Montant (XAF) |
|---|---|---|---:|
| 16/06/2025 | `NOMINAL` | D `512410100` / C `467000186` | 1 530 000 000 |
| 16/06/2025 | `ACCRUAL_BS` | D `512800100` / C `467000186` | 91 296 986 |
| 16/06/2025 | `CST_S_SETTLED` | D `467000186` / C `099ACO00001` | 1 621 296 986 |
| 18/06/2025 | `COUPON_CLIP` | D `467000186` / C `512800100` | 91 800 000 |
| 30/07/2025 | `COUPON_CLIP` (dénouement) | D `512800100` / C `467000186` | 91 800 000 |
| quotidien | `ACCRUAL` + `PREM_DISC_YIELD` | courus et étalement, avec contre-passation | — |
| 08/06/2026 | `REALIZED_CLEAN_PL` | D `734400100` / C `472200108` | 1 740 000 |

On vérifie que le règlement (1 621 296 986) est bien égal au **nominal + coupon couru**
(1 530 000 000 + 91 296 986) : la banque règle au **prix pied de coupon augmenté du couru**, ce qui
est la pratique de marché correcte.

---

## 5. La migration Flexcube → Calypso du 16 juin 2025

La migration s'est opérée par **liquidation technique intégrale** du portefeuille dans Flexcube,
puis **réintroduction des positions dans Calypso**, le même jour.

### 5.1 Rapprochement effectué

| Système | Compte | Nombre | Montant (XAF) |
|---|---|---:|---:|
| **Flexcube MM — sortie** | C `511410100` (obligations) | 55 | 107 203 763 333 |
| | C `512200100` (bons) | 10 | 19 485 000 000 |
| | **Total liquidé** | **65** | **126 688 763 333** |
| **Calypso — entrée** | D `512410100` (obligations) | 55 | 107 203 763 333 |
| | D `511210100` (bons) | 10 | 19 486 515 439 |
| | **Total réintroduit** | **65** | **126 690 278 772** |
| | **Écart** | **0** | **1 515 439** |

**Le rapprochement est concluant** : même nombre de positions (65), écart de 1 515 439 XAF, soit
**0,0012 %**, intégralement expliqué par une écriture d'accrétion (`734200100`) passée le même jour
et sans lien avec la migration.

Les intérêts courus ont par ailleurs été repris pour **3 089 462 049 XAF** via l'événement
`ACCRUAL_BS` au compte `512800100`.

### 5.2 Ce que la migration ne traite pas
La migration fait basculer les positions du compte `511410100` (titres de **placement**) vers
`512410100` (titres de **transaction**) et les courus de `511800100` vers `512800100`. Deux
questions en découlent :
- **le changement de catégorie comptable** (placement → transaction) est-il un reclassement
  volontaire et documenté, ou un simple effet du paramétrage Calypso ? Ce point est significatif
  car les règles d'évaluation diffèrent entre les deux catégories du PCEC ;
- **le compte `511800100` n'a pas été soldé** lors de la migration (cf. §8.1).

---

## 6. Les opérations de change

### 6.1 Deux populations distinctes
- **Change clientèle** (`FX_TRANSACTIONS.csv`, module `FT`) : produits `CSTF` (26 832 lignes),
  `CSBU` (11 744), `IN03` (9 530). Contreparties = clientèle entreprise (Orange, MTN, UCB, Nestlé,
  Olam…). Étiquettes `TFR_AMT`, `AMT_EQUIV`, plus les commissions (`*_HBEAC`, `*_RBEAC`) et les
  taxes (`TDTVA*_AMT`).
- **Change pour compte propre** (Calypso, books `ABCM_FX.Trading.Spot` et `.Fwd`) : contreparties
  bancaires et courtier STONEX.

### 6.2 Test de conformité à la parité fixe EUR/XAF
Le franc CFA est arrimé à l'euro à la parité fixe **1 EUR = 655,957 XAF**. Le test porte sur les
25 292 lignes en EUR comportant un montant en devise :

| Résultat | Lignes | Part |
|---|---:|---:|
| Taux implicite **exactement égal à 655,957** | 25 152 | **99,45 %** |
| Écart supérieur à 0,01 % | 140 | 0,55 % |

Les 140 écarts se répartissent en quatre catégories :

| Catégorie | Lignes | Montant XAF | Lecture |
|---|---:|---:|---|
| **Taux > parité** (656,04 à 657,99) | 39 | 23 886 700 000 | Marge commerciale intégrée au taux |
| **Taux < parité** (560 à 655,9) | 17 | 316 962 500 | Taux erronés, dont 577,28 (taux USD appliqué à l'EUR) |
| **Montant devise = montant XAF** (taux ≈ 1) | 80 | 9 351 118 | Conversion non appliquée |
| Taux aberrant (19,6 ; 130,6) | 4 | 1 286 145 | Erreurs manifestes |

Les cas les plus matériels sont détaillés au §8.4.

### 6.3 Taux USD/XAF
L'USD n'étant pas arrimé, le test approprié est l'écart au **taux médian du jour**. La trajectoire
médiane mensuelle est économiquement cohérente (635 XAF/USD en septembre 2023, ~605 en 2024,
~560-570 en 2026), reflétant l'appréciation de l'euro face au dollar. Elle ne révèle aucune rupture
suspecte.

*Réserve méthodologique* : le taux implicite calculé sur les lignes de **commission** ou de **taxe**
n'a pas de sens (montant XAF rapporté à un montant devise de principal). Les valeurs extrêmes
observées (jusqu'à 6 408) relèvent de cet artefact et non d'une anomalie de change. Un test USD
fiable devra être restreint aux étiquettes de principal (`TFR_AMT`, `AMT_EQUIV`, `TXN_AMT`).

### 6.4 Cohérence des comptes de position de change
Sur la période Calypso, les couples position / contre-valeur se compensent **exactement** :

| Couple | Position (`475…`) | Contre-valeur (`476…`) | Écart |
|---|---:|---:|---:|
| USD | −35 707 313 272 | +35 707 313 272 | **0** |
| EUR | −128 076 393 642 | +128 076 393 642 | **0** |
| Hors bilan comptant (`971…`) | +3 065 792 105 | −3 065 792 105 | **0** |
| Hors bilan terme (`972…` / `979…`) | −1 325 018 012 | +1 325 018 012 | **0** |
| **« Calypso » (`475000160` / `476000160`)** | **+167 668 487 881** | **−165 108 724 926** | **+2 559 762 955** |

Le dernier couple ne se compense pas : **2 559 762 955 XAF d'écart** (cf. §8.5).

---

## 7. Le refinancement auprès de la BEAC (pensions livrées)

Activité **apparue le 7 novembre 2025** — absente de toute la période Flexcube.

### 7.1 Volumétrie
- **128 opérations** de pension livrée, **5 506 Md XAF tirés** au total sur 11 mois.
- Encours net à la fin de l'extraction (14/09/2026) : **20 Md XAF** comptabilisés, soit
  **25 Md XAF** après correction du solde d'ouverture manquant (cf. §7.3).
- Charge d'intérêt nette : de 58 M à 441 M XAF par mois, soit environ **2,65 Md XAF** cumulés.
- Collatéral mobilisé net (`952100100`) : **77 847 170 000 XAF**.

### 7.2 Évolution de l'encours (retraité du solde d'ouverture de +5 Md)

| Fin de mois | Encours emprunté (XAF) |
|---|---:|
| 11/2025 | 65 000 000 000 |
| 12/2025 | 90 000 000 000 |
| 01/2026 | **170 000 000 000** |
| 02/2026 | 165 000 000 000 |
| 03/2026 | 0 |
| 04/2026 | 60 000 000 000 |
| 05/2026 | 50 000 000 000 |
| 06/2026 | 50 000 000 000 |
| 07/2026 | 50 000 000 000 |
| 08/2026 | 45 000 000 000 |
| 09/2026 | 25 000 000 000 |

### 7.3 Durée réelle des opérations
Le compte utilisé est le `552400100` — **« emprunt au jour le jour, banques non associées »**.
La durée réelle observée (écart entre le tirage et le remboursement) est la suivante :

| Durée (jours calendaires) | Opérations |
|---|---:|
| 0 (même jour) | 99 |
| 1 | 11 |
| 2 à 3 | 7 |
| **6 à 7** | **10** |
| **98** | **1** |
| non remboursée à la fin de l'extraction | 1 (50 Md, tirée le 11/05/2026) |

**11 opérations, représentant 832 Md XAF tirés, ont une durée supérieure à une semaine calendaire**
alors qu'elles sont logées dans un compte d'emprunt au jour le jour (cf. §8.6).

---

## 8. Constats d'exploration et pistes d'audit

> Les constats ci-dessous sont **étayés par les données** mais reposent sur les seuls fichiers
> fournis. Ils doivent être **confirmés auprès de la banque** — notamment parce qu'aucun fichier ne
> contient de **solde d'ouverture** (cf. §9).

### 8.1 — PRIORITÉ HAUTE — Le compte d'intérêts courus sur placements n'est jamais apuré
Sur l'ensemble des quatre fichiers et des 21 mois du module MM, le compte **`511800100` « créances
rattachées — placement »** enregistre **24 186 débits et aucun crédit**, pour un cumul de
**8 414 808 583 XAF**. Le compte de produits `733400100` est crédité du même montant exact.

Autrement dit : **aucun encaissement de coupon sur obligations n'apparaît dans le module MM**,
ni aucune reprise de couru lors des liquidations, ni aucun solde lors de la migration du 16/06/2025
(qui a réintroduit les courus dans un **autre** compte, le `512800100`).

Deux hypothèses à instruire :
- les coupons sont encaissés **hors du module MM** (écriture manuelle en module `DE`) — auquel cas
  il faut obtenir ces écritures et rapprocher ;
- le compte porte une **créance non apurée**, ce qui conduirait à une **surévaluation simultanée de
  l'actif et du produit net bancaire**.

*Éléments à demander* : balance générale détaillée du compte `511800100` aux dates de clôture,
échéancier des coupons attendus, justification du solde.

### 8.2 — PRIORITÉ HAUTE — Les volumes bruts du module MM ne sont pas des flux économiques
Comme établi au §3.6, la pratique de liquidation/réouverture gonfle massivement les volumes :
2 062 Md XAF de mouvements bruts sur le compte BEAC pour un portefeuille de ~127 Md.
**Toute analyse de flux, de rotation ou de performance menée sur les volumes bruts serait erronée.**
Il convient de construire un jeu de données retraité, neutralisant les 256 couples
liquidation/réouverture identifiés, avant toute conclusion quantitative.

### 8.3 — 29 contrats créés et liquidés le jour même
83 662 200 000 XAF sur 29 contrats, dont certains à plus de 1 380 jours de leur échéance.
Répartition : `BINEID00087` (16 contrats, 51,6 Md), `CHEICHEID059` (7 contrats, 12,2 Md),
`NDJOCKOS0067` (6 contrats, 19,95 Md). Il convient de vérifier s'il s'agit de **corrections de
saisie** (et dans ce cas, d'examiner la piste d'audit et le taux d'erreur du service) ou d'opérations
d'une autre nature.

### 8.4 — Écritures en EUR passées hors de la parité fixe
Les cas les plus matériels, à documenter :

| Date | Référence | Compte | Devise | Taux appliqué | Montant XAF | Saisie / Validation |
|---|---|---|---|---:|---:|---|
| 18/09/2026 | `099IN03262610001` | SG Paris | 3 200 000 EUR | 656,678553 | 2 101 371 369 | HARRY000079 / GHISID000239 |
| 17/09/2026 | `099IN03262600004` | SG Paris | 2 500 000 EUR | 656,678553 | 1 641 696 382 | TSAGUEOS0065 / GHISID000239 |
| 15/09/2026 | `099IN03262580001` | SG Paris | 1 800 000 EUR | 656,678553 | 1 182 021 395 | HARRY000079 / GHISID000239 |
| 14/09/2026 | `099000t262570001` | SG Paris | 1 750 000 EUR | 656,744149 | 1 149 302 260 | NDIRID000254 / ZOGOID000241 |
| 14/09/2026 | `099001d262570001` | SG Paris | 1 500 000 EUR | 656,744149 | 985 116 223 | NDIRID000254 / ZOGOID000241 |
| 10/06/2026 | `099CSBU261610004` | SCB Germany | 61 065,80 EUR | **577,280000** | 35 252 065 | NDJOCKOS0067 / GHISID000239 |
| 05/06/2026 | `0990021261560001` | SG Paris | 138 389,76 EUR | **560,000003** | 77 498 266 | NDIRID000254 / ZOGOID000241 |
| 29/04/2024 | `099000b241200001` | SG Paris | 3 495,21 EUR | **740,409875** | 2 587 888 | BINEID00087 / MBATOHID0012 |
| 30/03/2026 | `099001q260890001` | SG Paris | 1 760 000 EUR | **1,000000** | 1 760 000 | NDIRID000254 / NOUKID000192 |

Trois problématiques distinctes :
- les taux à **656,68 / 656,74** (0,11 % au-dessus de la parité) traduisent une **marge commerciale
  intégrée au taux de conversion comptable**. En régime de parité fixe, la conversion comptable doit
  se faire à 655,957 et la marge être comptabilisée **en commission**. À confirmer avec la banque ;
- les taux **577,28** et **560,00** sur des comptes EUR correspondent à des **taux USD appliqués à
  des montants en euros** — erreur de paramétrage ou de saisie ;
- les **80 lignes à taux 1,000** (le montant en devise est repris tel quel en XAF) concernent des
  mouvements de nostri EUR. Sur le seul dossier `099001q260890001`, 4,5 M EUR sont comptabilisés
  pour 4,5 M XAF au lieu d'environ 3 Md XAF. À déterminer s'il s'agit d'un défaut d'extraction ou
  d'une comptabilisation réelle.

### 8.5 — Écart de 2,56 Md XAF entre position de change Calypso et sa contre-valeur
Alors que tous les autres couples position/contre-valeur se compensent exactement à l'unité près,
le couple `475000160` / `476000160` présente un écart de **2 559 762 955 XAF** sur la période
(167 668 487 881 contre 165 108 724 926), avec un nombre de lignes différent (494 contre 855).
En principe, cet écart représente le **résultat de change**, qui doit être viré en compte de
résultat. Or aucun compte de gains/pertes de change n'apparaît dans les écritures Calypso.
*À instruire* : le résultat de change est-il constaté, et par quelle écriture ?

### 8.6 — Opérations de pension livrée logées dans un compte d'emprunt au jour le jour
11 opérations (832 Md XAF tirés) ont une durée effective de 6 à 98 jours alors qu'elles sont
comptabilisées au compte `552400100` « emprunt **au jour le jour** ». Le cas le plus marquant :

> **Deal 3349072** — 90 000 000 000 XAF tirés le **23/12/2025**, garantis par 90,83 Md de titres,
> **remboursés le 31/03/2026** (98 jours). La charge d'intérêt a été **courue une seule fois**
> (75 750 000 XAF le 23/12), **contre-passée dès le lendemain**, puis **plus aucun couru pendant
> 97 jours**, avant un règlement unique de 101 000 000 XAF à dénouement.

Deux conséquences potentielles :
- **classement comptable** : un emprunt de 98 jours n'a pas sa place dans un compte d'emprunt au
  jour le jour, ce qui **fausse l'échéancier de liquidité** et les ratios prudentiels COBAC ;
- **rattachement des charges** : l'absence de couru quotidien conduit à une **sous-évaluation de la
  charge d'intérêt** à l'arrêté du 31/12/2025 et à celui du 31/03/2026.

### 8.7 — Collatéral mobilisé sans contrepartie d'encours apparente
Le collatéral net mobilisé (`952100100`) s'élève à **77,85 Md XAF** alors que l'encours emprunté en
fin de période n'est que de **25 Md XAF**. L'écart d'environ **53 Md XAF** correspond soit à une
sur-collatéralisation, soit à des **titres restés affectés en garantie après le dénouement** de
l'opération. À rapprocher des états de la BEAC.

### 8.8 — 3 076 écritures manuelles sans validateur, pour 1 231 Md XAF
3 076 lignes du fichier des comptes clés présentent un champ `AUTH_ID` **vide**, pour un montant
cumulé de **1 230 913 133 539 XAF**. Elles sont toutes passées par `ADMINUSER1` en module `DE`
(écriture directe), et s'étalent de façon continue sur toute la période (octobre 2023 à
septembre 2026). Il s'agit du constat de **contrôle interne le plus significatif** de l'exploration.

### 8.9 — Séparation des tâches : constat nuancé
Sur l'ensemble des 492 973 lignes, 408 281 (82,8 %) présentent `USER_ID` = `AUTH_ID`. Mais
l'analyse détaillée est plus rassurante qu'il n'y paraît :

| Population | Auto-validation |
|---|---|
| **Utilisateurs nominatifs** (humains) | **2 lignes seulement** (compte `MIGRATION`, 717 865 477 XAF) |
| Comptes techniques (`SYSTEM`, `CALYPSOUSR`, `ADMINUSER1`, `FLEXSWITCH`, `PRIMUSUSR`, `*EOD`…) | la totalité du reste |

**Le contrôle « 4 yeux » est donc respecté par les opérateurs humains.** En revanche, il est
**structurellement neutralisé pour les comptes techniques**, et en particulier :
- **`CALYPSOUSR`** : 194 938 écritures, soit **l'intégralité du flux Calypso**. Le contrôle de
  validation doit impérativement être recherché **dans Calypso**, hors du périmètre des fichiers
  fournis ;
- **`ADMINUSER1`** : 147 884 écritures auto-validées, plus les 3 076 sans validateur du §8.8.

### 8.10 — Concentration du portefeuille
100 % du portefeuille MM historique est exposé à quatre souverains CEMAC, dont **54,2 % sur le seul
État du Cameroun**. Calypso élargit le spectre aux contreparties bancaires, mais l'exposition
souveraine reste dominante. Point à traiter sous l'angle du **risque de concentration** et des
limites internes (dont l'existence et le respect restent à vérifier).

### 8.11 — Qualité des données : anomalies mineures
- **7 références de contrat en doublon exact** dans `MM_CONTRACT.csv` (lignes strictement identiques
  sur les 16 colonnes) : `099BTTR241940001`, `099OTAP222690002`, `099OTAP222690004`,
  `099OTAP241240006`, `099TBTR223430001`, `099TBTR233110001`, `099TBTR233390001`. Soit 596 contrats
  réels pour 603 lignes. **Risque de double comptage de 8,0 Md XAF** si le fichier est utilisé tel
  quel.
- **84 lignes en doublon** dans le fichier MM, **1 493** dans le fichier des comptes clés (même
  référence, compte, sens, tag, montant et horodatage à la seconde). À qualifier : écritures
  légitimement identiques, ou artefacts d'extraction ?
- **2 références non conformes** au format sur 16 caractères : `191701` et `291807`, passées par
  l'utilisateur `MIGRATION` le 05/12/2025 sur les nostri SCB Frankfurt et SCB New-York.
- **Deux jeux de comptes de produits** coexistent (`733400100` / `734400100` et `733200100` /
  `734200100`), tous deux alimentés par Calypso. La règle d'affectation entre les deux n'est pas
  déductible des données et doit être obtenue.

### 8.12 — Intégrité globale : très satisfaisante
Il faut souligner les points positifs, qui sont nombreux et significatifs :
- **partie double parfaite** dans le module MM (0 écriture déséquilibrée sur 24 504) ;
- **aucune écriture passée un week-end** sur les 492 973 lignes ;
- les **18 jours ouvrés sans aucune écriture** correspondent **tous** à des jours fériés camerounais
  (Noël, Jour de l'An, Fête du Travail, Assomption, Fête de la Jeunesse des 10-11 février, Fête
  Nationale du 20 mai, Ascension, Vendredi Saint) — **aucun trou calendaire inexpliqué** ;
- **migration Flexcube → Calypso rapprochée à 0,0012 %** ;
- **99,45 % des écritures en EUR** respectent exactement la parité fixe ;
- les couples position de change / contre-valeur se compensent **exactement** pour l'USD, l'EUR et
  les engagements hors bilan.

---

## 9. Limites de l'exploration et données à obtenir

### 9.1 Limites du périmètre fourni
1. **Aucun solde d'ouverture.** Les fichiers ne contiennent que des **mouvements**. Ceci est
   démontré par le compte `552400100`, dont le cumul des mouvements part immédiatement à
   −5 000 000 000 XAF dès la première écriture du 07/11/2025 : une opération tirée avant le début de
   l'extraction y est remboursée. **Aucune analyse de solde n'est fiable** sans ancrage sur une
   balance générale.
2. **Le référentiel des deals Calypso est absent.** C'est l'équivalent de `MM_CONTRACT` pour la
   période 06/2025 → 09/2026, soit **65 % de la période d'audit**. Nominal, taux, échéance,
   contrepartie et sens des 1 985 deals ne sont connus qu'indirectement.
3. **L'extraction déborde la période d'audit** : 65 018 lignes sont postérieures au 30/06/2026
   (Calypso 37 566, comptes clés 19 026, change 8 426). Elles constituent une matière utile pour
   l'examen des **événements postérieurs à la clôture**, mais doivent être exclues des totaux de la
   période.
4. **Absence de données de marché** : aucun cours de valorisation, aucune courbe de taux, ce qui
   interdit tout recalcul indépendant des valorisations et des dépréciations.

### 9.2 Documents et fichiers à demander

| # | Élément demandé | Finalité |
|---|---|---|
| 1 | Balance générale détaillée aux 31/12/2023, 31/12/2024, 31/12/2025 et 30/06/2026 | Ancrer les soldes ; instruire le §8.1 |
| 2 | Référentiel des deals Calypso (nominal, taux, échéance, contrepartie, sens) | Couvrir 65 % de la période |
| 3 | Table de correspondance IFRS 9 ↔ PCEC paramétrée dans Calypso | Valider le classement comptable (§4.3) |
| 4 | Écritures d'encaissement des coupons sur obligations (module `DE`) | Instruire le §8.1 |
| 5 | Justification du solde du compte `511800100` | Instruire le §8.1 |
| 6 | Procédure de validation (4 yeux) dans Calypso et habilitations `CALYPSOUSR` | Instruire le §8.9 |
| 7 | Habilitations et journal d'activité de `ADMINUSER1` | Instruire les §8.8 et §8.9 |
| 8 | Politique de taux de change appliquée aux opérations clientèle en EUR | Instruire le §8.4 |
| 9 | États de collatéral BEAC et conventions de pension livrée | Instruire les §8.6 et §8.7 |
| 10 | Limites internes de contrepartie et de concentration + suivi de leur respect | Instruire le §8.10 |
| 11 | Note sur la migration du 16/06/2025 (reclassement placement → transaction) | Instruire le §5.2 |
| 12 | Règle d'affectation entre les comptes `733xxx` et `734xxx` | Instruire le §8.11 |

---

## 10. Synthèse

L'exploration permet d'établir une compréhension **solide et vérifiée** du dispositif :
la codification des références est décodée à 100 %, les schémas comptables des deux systèmes sont
reconstitués et confirmés par les volumes, le cycle de vie d'un titre est documenté de l'acquisition
à la liquidation dans les deux environnements, et la migration du 16 juin 2025 est rapprochée à
0,0012 % près.

La qualité intrinsèque des données est bonne : partie double parfaite, aucun trou calendaire
inexpliqué, aucune écriture le week-end, parité fixe EUR respectée à 99,45 %.

Trois enseignements structurent la suite des travaux :

1. **Une clé de lecture indispensable** : sous Flexcube, la pratique de liquidation/réouverture rend
   les volumes bruts dépourvus de signification économique ; sous Calypso, le « cancel & rebook »
   quotidien double les flux de courus. **Tout travail quantitatif doit être mené sur des données
   retraitées.**

2. **Trois pistes d'audit prioritaires** : le compte d'intérêts courus `511800100` jamais apuré
   (8,41 Md XAF), les 3 076 écritures manuelles sans validateur (1 231 Md XAF), et les opérations de
   pension livrée de 6 à 98 jours logées en emprunt au jour le jour (832 Md XAF) avec un
   rattachement des charges défaillant.

3. **Une zone d'ombre à lever d'urgence** : l'absence du référentiel des deals Calypso prive l'audit
   de toute donnée contractuelle sur 65 % de la période. Son obtention conditionne la profondeur des
   travaux sur l'exercice 2025-2026.

---

*Rapport d'exploration établi à partir des données extraites du core banking.
Le détail chronologique des travaux, des requêtes exécutées et des vérifications figure dans le
document `CARNET_DE_BORD.md`.*
