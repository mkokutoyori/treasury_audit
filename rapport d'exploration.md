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

> **Version 5** — intègre la révision du §14 (historique intégral des comptes) ainsi que
> la seconde extraction (comptes généraux Calypso, §11), la troisième
> (historique du compte `511800100`, §12) et la quatrième (**41 comptes de trésorerie, tous
> modules, §13**), fournies en cours de mission. Les constats revus
> ou retirés sont signalés comme tels et conservés dans le corps du rapport, afin de préserver la
> piste d'audit.
>
> ⚠ **Le constat initial du §8.1, repris et amplifié au §11.10, est RETIRÉ.** Il reposait sur une
> extraction limitée au module MM. Voir le **§12**, qui le remplace.
>
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
| **Historique des comptes généraux Calypso** | `calypson_key_account_…part_1..3.csv` | 143 953 | 27/09/2023 → 18/09/2026 | Mouvements des comptes généraux utilisés par Calypso (position de change, comptes de liaison, courus, régularisation) — *seconde extraction, cf. §11* |
| **Historique du compte d'intérêts courus** | `creance_rattaché.csv` | 32 937 | 16/08/2022 → 31/07/2025 | Historique **complet, tous modules**, du compte `511800100` — *troisième extraction, cf. §12* |
| **Comptes de trésorerie, tous modules** | `final_key_accounts_…part_1..6.csv` | 329 884 | 08/06/2022 → 18/09/2026 | **41 comptes généraux** de la trésorerie, tous modules — *quatrième extraction, cf. §13* |

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

Le dernier couple ne se compense pas. La seconde extraction en a établi la cause, qui n'est **pas**
un résultat de change non constaté : ces deux comptes **ne forment pas un couple** position /
contre-valeur. Voir la **correction au §11.6**.

---

## 7. Le refinancement auprès de la BEAC (pensions livrées)

Activité **apparue le 7 novembre 2025** — absente de toute la période Flexcube.

### 7.1 Volumétrie
- **128 opérations** de pension livrée, **5 506 Md XAF tirés** au total sur 11 mois.
- Encours net à la fin de l'extraction (14/09/2026) : **20 Md XAF** comptabilisés, soit
  **45 Md XAF** — chiffre corrigé au §13.5 sur l'historique intégral.
- Charge d'intérêt nette : de 58 M à 441 M XAF par mois, soit environ **2,65 Md XAF** cumulés.
- Collatéral mobilisé net (`952100100`) : **77 847 170 000 XAF**.

### 7.2 Évolution de l'encours

> ⚠ **Les chiffres de ce paragraphe, établis sur une extraction partielle, sont corrigés au
> §13.5. Le retraitement « solde d'ouverture de +5 Md » qui y figurait est ERRONÉ : voir §14.**

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

### 8.1 — ~~Le compte d'intérêts courus sur placements n'est jamais apuré~~ — **CONSTAT RETIRÉ**
> **Ce constat est retiré.** Il reposait sur une extraction du compte `511800100` **limitée au
> module MM**, dans laquelle les écritures d'apurement — passées en module `DE` — étaient invisibles.
> L'extraction complète du compte, obtenue depuis, montre **801 crédits pour 15 005 402 277 XAF**
> et un **solde net strictement nul**. Les coupons sont bien encaissés, en trésorerie, sur le compte
> BEAC.
>
> Le **§12** remplace intégralement le présent constat et expose ce que l'historique complet révèle
> réellement — notamment un **sur-apurement de 1 205 231 891 XAF à la migration**, non corrigé
> pendant 45 jours et traversant l'arrêté semestriel du 30/06/2025.

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

### 8.5 — ~~Écart de 2,56 Md XAF entre position de change Calypso et sa contre-valeur~~ — **CONSTAT REVU**
> **Ce constat est corrigé par la seconde exploration.** L'écart de 2 559 762 955 XAF entre
> `475000160` et `476000160` ne traduit pas un résultat de change non constaté : ces deux comptes
> **ne forment pas un couple** position / contre-valeur et n'apparaissent **jamais dans la même
> écriture**. Leur libellé est en revanche **inversé par rapport à leur devise de tenue**.
> Le **§11.6** remplace le présent constat.
>
> La question du **résultat de change** demeure, mais sous un angle différent et bien plus large :
> les écritures de **réévaluation de la position de change ne touchent aucun compte de résultat**
> (voir **§11.4**).

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
1. ~~**Aucun solde d'ouverture.**~~ — **LIMITE LEVÉE, voir §14.** L'extraction des 41 comptes de
   trésorerie couvre l'historique **intégral** de chaque compte : le solde d'ouverture est nul par
   construction et le solde est calculable à toute date.
   Le raisonnement initial était **faux**. J'avais attribué le solde anormal du compte `552400100`
   à une opération tirée avant le début de l'extraction. L'historique complet montre qu'il n'en est
   rien : ce solde provient d'un **déversement en double de l'interface Calypso** (§14.2).
2. **Le référentiel des deals Calypso est absent.** C'est l'équivalent de `MM_CONTRACT` pour la
   période 06/2025 → 09/2026, soit **65 % de la période d'audit**. Nominal, taux, échéance,
   contrepartie et sens des 1 985 deals ne sont connus qu'indirectement.
3. **L'extraction déborde la période d'audit** : 65 018 lignes sont postérieures au 30/06/2026
   (Calypso 37 566, comptes clés 19 026, change 8 426). Elles constituent une matière utile pour
   l'examen des **événements postérieurs à la clôture**, mais doivent être exclues des totaux de la
   période.
4. **Absence de données de marché** : aucun cours de valorisation, aucune courbe de taux, ce qui
   interdit tout recalcul indépendant des valorisations et des dépréciations.
5. **Les extractions filtrées par module peuvent masquer des écritures structurantes.** Le module
   `DE` (écriture directe) porte l'apurement des coupons, les corrections et les écritures de
   migration. Le compte `511800100` en a fourni la démonstration (§12.7) ; les constats reposant
   encore sur des extractions partielles doivent être confirmés selon cette règle.

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
| 13 | ~~Historique complet du compte `511800100`~~ | ✔ **obtenu** — cf. §12 |
| 14 | **États financiers au 30/06/2025** et rapprochement du nostro BEAC de juin-juillet 2025 | **Instruire le §12.5** |
| 15 | Procédure de contrôle de la migration : calcul des courus repris | Instruire le §12.5 |
| 20 | Troisième jambe de l'écriture de correction du 31/07/2025 (1 994 516 XAF) | Instruire le §12.5 |
| 16 | Mouvements des comptes de gains et pertes de change (classes 63/73 PCEC) | Instruire le §11.4 |
| 17 | Conventions-cadres **Sell-Buy-Back** et doctrine comptable retenue | Instruire le §11.5 |
| 18 | Paramétrage des comptes `475000160` / `476000160` (intitulés inversés) | Instruire le §11.6 |
| 19 | Dossiers de rétrocession « non exécutés » et déclarations BEAC associées | Instruire le §11.8 |

---

## 11. Seconde exploration — extraction des comptes généraux Calypso

Une seconde extraction a été fournie (`calypson_key_account_Export Worksheet_part_1..3.csv`,
**143 953 lignes**, 27/09/2023 → 18/09/2026), portant sur les **comptes généraux** mouvementés par
Calypso. Elle a été sollicitée pour instruire le constat du §8.1 (compte d'intérêts courus jamais
apuré). Elle n'apporte pas la réponse attendue sur ce point précis, mais **ouvre quatre chantiers
nouveaux** et **corrige deux constats** de la première exploration.

### 11.1 Ce que la seconde extraction apporte réellement
Sur 143 953 lignes, **30 297 sont inédites** (les autres recoupent les fichiers déjà analysés) :

| Compte | Module | Lignes inédites | Période |
|---|---|---:|---|
| `475000102` / `476000102` (position EUR) | `DE` | 11 641 | 2023-09-27 → 2026-09-18 |
| `475000100` / `476000100` (position USD) | `RE` | 10 856 | 2023-09-27 → 2026-09-18 |
| `475000100` / `476000100` (position USD) | `DE` | 5 289 | 2023-09-29 → 2026-09-18 |
| `475000102` / `476000102` (position EUR) | `RE` | 1 538 | 2023-09-27 → 2026-09-18 |
| Positions EUR/USD | `RT` | 490 | 2023-11-20 → 2026-09-18 |
| `472200106` et divers | `DE` | 483 | 2023-10-09 → 2026-09-15 |

L'apport est donc essentiellement l'**historique complet des comptes de position de change sur
toute la période d'audit**, là où la première extraction ne couvrait que la part issue du module
de transfert (`FT`).

### 11.2 Deux modules jusqu'ici inconnus
**Module `RE` — RÉÉVALUATION** (12 437 lignes, 27/09/2023 → 18/09/2026)
- Étiquette unique : `ACREVALAMT` (*Account Revaluation Amount*)
- Produits : `ACPO` (12 394) et `ACRV` (43) ; référence au format `001ACPO24078`
- Utilisateurs : traitements de fin de journée (`FLEXSWITCH` 6 330, `ASONG0014EOD` 2 371,
  `FOSSO0153EOD` 1 970, `GARBA0105EOD`, `TABOT0086EOD`, `MAYOU0219EOD`)
- Comptes touchés : **uniquement** `475000100`/`476000100` (USD) et `475000102`/`476000102` (EUR)

**Module `RT` — CHANGE AU GUICHET** (490 lignes, 20/11/2023 → 18/09/2026)
- Étiquettes : `OFS_AMT` (474), `TXN_AMT` (16)
- Produits : `FXSA` (400, vente de devises), `FXPW` (82, achat), `FXSW` (2, swap),
  `MGLD`/`MSCC`/`MSGC` (2 chacun)
- Utilisateurs : **caissiers nominatifs** (`LECOMOS00087`, `EMOCKOS00086`, `NGONGOS00101`,
  `EMERSOS00025`, `ZOUGAOS00012`, `TOUKOS000145`) — population distincte de la salle des marchés.

### 11.3 Mécanique de la réévaluation (écriture-type)
```
001ACPO24078   D  475000100  USD   FCY = 0,00        LCY = 1 063 000 XAF
001ACPO24078   C  476000100  XAF                     LCY = 1 063 000 XAF
```
La position en devise (`475…`) est **débitée d'un montant en devise nul** mais d'un montant en XAF
non nul : c'est la **retranslation de la contre-valeur** de la position au nouveau cours, sans
modification de la position en devise elle-même. La contrepartie va au compte de contre-valeur.
Les écritures sont équilibrées (somme des débits moins crédits du module = 99 407 XAF, résidu
provenant d'un autre compte).

### 11.4 — PRIORITÉ HAUTE — La réévaluation de change ne touche aucun compte de résultat
**C'est le constat le plus significatif de la seconde exploration.** Sur les 12 437 écritures de
réévaluation, **aucune ne mouvemente un compte de charge ou de produit**. Les écritures se bouclent
intégralement entre le compte de position (`475…`) et son compte de contre-valeur (`476…`).

Réévaluation nette cumulée sur les 36 mois, au compte de contre-valeur :

| Devise | Compte | Écritures | Réévaluation nette cumulée (XAF) |
|---|---|---:|---:|
| USD | `476000100` | 5 428 | **+3 536 553 336** |
| EUR | `476000102` | 769 | **−253 064 562** |

Évolution mensuelle de la réévaluation USD (extraits) : +273,9 M en 12/2023, −246,3 M en 08/2024,
+636,9 M en 10/2025, +251,3 M en 07/2026 — une volatilité très significative.

**Portée** : en régime de parité fixe, la position en EUR ne génère aucun résultat de change (ce que
confirme le montant quasi nul du compte `476000102` hors quelques mois), mais **la position en USD
est une position ouverte**, dont la réévaluation a produit **plus de 3,5 Md XAF de variation
cumulée sur la période sans qu'aucune de ces variations n'apparaisse en compte de résultat dans les
données fournies**.

Deux lectures possibles, à trancher avec la banque :
- le résultat de change est **viré au résultat par une écriture distincte**, hors du périmètre des
  cinq extractions (le plus probable) — il faut alors obtenir cette écriture et la rapprocher ;
- le résultat de change **n'est pas constaté** et reste logé en compte de bilan, ce qui
  affecterait le résultat et les fonds propres prudentiels.

*Éléments à demander* : mouvements des comptes de gains et pertes de change (classes 63/73 du PCEC)
sur la période, et procédure de virement du résultat de réévaluation.

### 11.5 — PRIORITÉ HAUTE — 215 opérations de Sell-Buy-Back comptabilisées en cession ferme
La seconde extraction a révélé un format de libellé jusqu'ici inexploité : **22 847 lignes portent
un commentaire libre saisi par la salle des marchés**, en dixième position du champ `DESCRIPTION`
(après le libellé du titre). Ce commentaire est une **source de preuve directe sur l'intention
économique** des opérations.

Typologie des commentaires (lignes dédoublonnées) :

| Catégorie | Lignes | Deals | Montant cumulé (XAF) |
|---|---:|---:|---:|
| Alimentation de compte (`/ACC/ACCOUNT FUNDING`) | 4 724 | 509 | 1 051 263 605 798 |
| **FX DEAL avec marge explicite** | 4 554 | 208 | 2 402 811 854 548 |
| Autres | 3 652 | 233 | 3 209 684 175 340 |
| **SBB — Sell-Buy-Back** | 1 675 | 215 | 3 767 467 539 902 |
| Achat | 687 | 85 | 1 173 505 810 996 |
| Vente | 630 | 85 | 339 821 505 362 |

**Les opérations de Sell-Buy-Back (SBB)** sont désignées explicitement par les commentaires
(`NEAR LEG SBB WITH CCA`, `FAR LEG SBB WITH SOCGEN`, `FIRST LEG OF SBB WITH SOCIETE GENERALE CMR`…).
Un SBB est économiquement un **financement garanti**, strictement équivalent à une pension livrée.

Or ces 215 opérations sont comptabilisées **dans les books `ABCM_FVOCI.Bond` et
`ABCM_FVOCI.Bills`**, avec les événements d'une **acquisition et d'une cession fermes**
(`NOMINAL`, `CST_S_SETTLED`, `PREM_DISC`, `REALIZED_CLEAN_PL`) — et **non** dans le book de pension
`ABCM_MM.Plmt.Tkn.Secured`.

| Book | Événement | Lignes | Deals | Montant (XAF) |
|---|---|---:|---:|---:|
| `ABCM_FVOCI.Bond` | `NOMINAL` | 424 | 204 | 1 763 752 140 000 |
| | `CST_S_SETTLED` | 425 | 203 | 1 801 829 031 779 |
| | `ACCRUAL_BS` | 410 | 201 | 45 024 191 670 |
| | `PREM_DISC` | 122 | 57 | 11 254 156 830 |
| | `REALIZED_CLEAN_PL` | 38 | 16 | **193 486 200** |
| `ABCM_FVOCI.Bills` | `NOMINAL` | 22 | 11 | 71 586 000 000 |
| | `CST_S_SETTLED` | 22 | 11 | 69 448 688 664 |

**Montant réglé cumulé : 896 125 677 223 XAF sur 214 deals**, du 25/11/2025 au 18/09/2026.

Contreparties : `ECOBANKCM` (68 deals), `CCACM` (64), `SGCM` (53), `BICECCM` (8), `ECOBANKCG` (8),
`ECOBANKGQ` (6), `UBCM` (4), `CDCG` (2), `UBACM` (1), `ECOBANKGA` (1).

**Le caractère de financement roulé est démontré par la répétition sur un même titre**, avec la
même contrepartie et à un prix croissant à chaque aller-retour :

> Titre `CM2J00000196`, contrepartie `SGCM` — **9 allers-retours entre le 09/01 et le 06/04/2026** :
> 9 556 934 932 → 9 560 653 856 → 9 568 321 918 → 9 569 803 918 → 9 594 349 315 → 9 619 754 788
> → 9 667 551 370 → 9 668 634 370 → 9 690 325 342 XAF.
> Cumul réglé sur ce seul titre : **86 496 329 809 XAF**.

Autres titres fortement mobilisés : `CM2B00000228`/SGCM (7 rotations, 67,8 Md),
`GA2B00000109`/ECOBANKCM (5), `GQ2J00000057`/CCACM (4, 39,5 Md), `CM2K00000037`/BICECCM (4, 32,9 Md),
`CG2A00000692`/CCACM (4, 31,4 Md).

**Conséquences potentielles, à instruire :**
- **sortie et réentrée du bilan** de titres qui ne quittent économiquement jamais le portefeuille,
  au lieu d'un maintien à l'actif assorti d'une dette au passif ;
- **constatation de plus-values de cession** (`REALIZED_CLEAN_PL` : 193 486 200 XAF) qui ne
  devraient pas être reconnues sur une opération de financement ;
- **sous-évaluation de l'endettement** et donc des ratios prudentiels COBAC de liquidité et de
  transformation ;
- **sous-évaluation de l'usage du portefeuille en collatéral**, déjà relevée au §8.7.

*Éléments à demander* : conventions-cadres SBB signées avec les contreparties, doctrine comptable
retenue pour leur enregistrement, et position du commissaire aux comptes sur ce traitement.

### 11.6 — CORRECTION du §8.5 — Les comptes `475000160` / `476000160` sont inversés
La première exploration concluait à un écart de 2 559 762 955 XAF entre une position de change et sa
contre-valeur. **Cette lecture était erronée** : les deux comptes ne forment pas un couple.

| Compte | Intitulé | Devise de tenue | `FCY_AMOUNT` renseigné | Comportement réel |
|---|---|---|---|---|
| `475000100` | USD **compte position de change** | USD | 10 594 / 10 594 | ✔ conforme |
| `476000100` | Cpte de **contre-valeur** pos. chge USD | XAF | 0 / 10 593 | ✔ conforme |
| `475000102` | EUR **compte position de change** | EUR | 10 172 / 10 172 | ✔ conforme |
| `476000102` | Cpte de **contre-valeur** pos. chge EURO | XAF | 0 / 10 171 | ✔ conforme |
| **`475000160`** | **Compte position de change CALYPSO** | **XAF** | **0 / 494** | **se comporte en contre-valeur** |
| **`476000160`** | **Cpte de contre-valeur pos. chge CALYPSO** | **EUR et USD** | **855 / 855** | **se comporte en position** |

**Les deux comptes sont donc intervertis par rapport à leur intitulé.** Le contrôle est sans
ambiguïté : un compte de position est tenu en devise et porte un montant `FCY_AMOUNT`, un compte de
contre-valeur est tenu en XAF et n'en porte jamais.

De plus, ces deux comptes **n'apparaissent jamais dans la même écriture** (494 écritures pour l'un,
855 pour l'autre, aucune commune) :
- `476000160` (tenu en EUR/USD) fonctionne toujours avec `475000102`/`476000102` ou
  `475000100`/`476000100` et les nostri (SG Paris, UBA America, SCB Frankfurt, BGFI Europe, ODDO) ;
- `475000160` (tenu en XAF) fonctionne avec la BEAC (413 lignes), STONEX (77), le compte
  inter-branches (154) et les commissions sur achat de devises (`625000105`).

Il s'agit donc de **deux comptes de liaison distincts** pour le dénouement des opérations de change
Calypso — l'un pour la jambe en devise, l'autre pour la jambe en XAF —, et non d'un couple
position / contre-valeur. L'écart de 2,56 Md n'a pas la signification qui lui était prêtée.

**Ce qui subsiste comme constat** : l'**intitulé des deux comptes est inversé par rapport à leur
usage réel**, ce qui est une anomalie de paramétrage du plan de comptes. Elle induit en erreur toute
lecture de la balance générale et tout contrôle de la position de change fondé sur les libellés.

### 11.7 Position de change : bouclage confirmé sur toute la période
Avec la couverture complète 2023-2026 et tous modules confondus (`FT`, `DE`, `RE`, `RT`), les
couples position / contre-valeur se compensent **exactement** :

| Devise | Position (`475…`) | Contre-valeur (`476…`) | Écart |
|---|---:|---:|---:|
| USD | −7 292 487 618 | +7 292 487 618 | **0** |
| EUR | −35 503 790 493 | +35 503 790 493 | **0** |
| GBP | +610 490 400 | −610 490 400 | **0** |
| ZAR | +639 456 600 | −639 456 600 | **0** |

Deux devises supplémentaires apparaissent : **GBP** (`475000106`/`476000106`, à partir du
03/02/2026) et **ZAR** (`475000150`/`476000150`, à partir du 03/11/2023). Le mécanisme comptable de
la position de change est donc **intègre sur l'ensemble du périmètre**.

### 11.8 Réglementation des changes : rétrocessions sur rapatriement d'exportation
Les commentaires libres documentent **285 opérations de rétrocession** sur rapatriement de recettes
d'exportation, pour **56 873 780 557 XAF réglés**, entre le 16/06/2025 et le 18/12/2025.

| Taux de rétrocession | Deals | Lignes | Observation |
|---|---:|---:|---|
| 70 % | 193 | 2 542 | Cas standard |
| 100 % | 65 | 816 | Rétrocession intégrale |
| 30 % | 7 | 80 | Solde complémentaire |
| 30 % — **« DOSSIER NON EXECUTE »** | **13** | 146 | **Opération non exécutée, solde restitué** |
| 79 % | 1 | 8 | Taux atypique, à justifier |

Ce mécanisme relève de la **réglementation des changes CEMAC** (obligation de rapatriement des
recettes d'exportation et rétrocession). Deux points appellent des travaux :
- les **13 dossiers « non exécutés »** avec restitution du solde de 30 % — vérifier le motif de
  non-exécution et la déclaration à la BEAC ;
- le **taux de 79 %**, qui ne correspond à aucun des taux standard (30/70/100 %).

Il convient par ailleurs de noter que **les commentaires de rétrocession cessent au 18/12/2025**
alors que l'activité de change se poursuit : soit la pratique de documentation a changé, soit le
mécanisme a évolué. À clarifier.

### 11.9 Marges de change négociées — corroboration du §8.4
Les commentaires du type `FX DEAL 05/09/2025 0.15PCT` documentent **explicitement la marge
négociée** sur les opérations de change :

| Marge | Deals | Lignes | Montant (XAF) |
|---|---:|---:|---:|
| 0,10 % | 8 | 140 | 209 950 845 080 |
| 0,12 % | 1 | 16 | 26 238 280 000 |
| **0,15 %** | **52** | **968** | **992 135 618 450** |
| 0,20 % | 8 | 132 | 135 153 380 280 |
| 0,25 % | 1 | 16 | 15 752 807 356 |
| 0,50 % | 1 | 40 | 65 595 700 000 |

Ces marges **corroborent directement le constat du §8.4** : les taux EUR relevés à 656,678553 et
656,744149 représentent respectivement **+0,110 %** et **+0,120 %** par rapport à la parité de
655,957 — ce qui correspond à l'ordre de grandeur des marges documentées. La pratique consistant à
**intégrer la marge commerciale au taux de conversion comptable**, plutôt qu'à la comptabiliser en
commission, est donc **établie et systématique**, et non accidentelle.

*Point de contrôle* : en régime de parité fixe, la conversion comptable doit s'effectuer à 655,957,
la marge devant être enregistrée distinctement en produit de commission. Ce traitement a une
incidence sur la **présentation du produit net bancaire** (marge de change contre commissions) et
sur la **base taxable**.

### 11.10 — ~~Le compte d'intérêts courus a été abandonné en l'état à la migration~~ — **CONSTAT RETIRÉ**
> **Ce constat est retiré**, comme celui du §8.1 qu'il amplifiait. Les tests qui le fondaient
> étaient exacts — Calypso n'impacte effectivement jamais le compte `511800100` (0 ligne
> `CALYPSOUSR`, 0 module `DE` côté Calypso, 0 produit `MNIP`) — mais la **conclusion qui en était
> tirée était fausse** : l'apurement n'est pas assuré par Calypso, il l'est par des **écritures
> manuelles de Flexcube en module `DE`**, qui ne figuraient dans aucune des extractions alors
> disponibles.
>
> En particulier, l'hypothèse d'une **double comptabilisation de 3 089 462 049 XAF est infirmée** :
> l'apurement passé le 16/06/2025 (4 169 123 793 XAF) est **supérieur** au montant re-comptabilisé
> par Calypso, et non redondant avec lui.
>
> Le **§12** expose la situation réelle.

### 11.11 Découverte technique — les contre-passations sont des montants négatifs
La seconde extraction a mis en évidence un mécanisme de Flexcube qui n'avait pas été identifié :
**les corrections d'écritures sont passées par un débit (ou crédit) de montant négatif**, et non par
une écriture de sens inverse.

| Source | Lignes | Dont montant `LCY_AMOUNT` négatif |
|---|---:|---:|
| Change clientèle (`FX`) | 48 122 | 294 |
| Module MM | 59 446 | 378 |
| Comptes généraux Calypso (`CKEY`) | 143 953 | 138 |
| Comptes clés (`KEY`) | 190 467 | 45 |
| Calypso (`CLP`) | 194 938 | **0** |

**Conséquence méthodologique** : toute agrégation qui filtrerait sur `DRCR_IND` sans tenir compte du
signe du montant **surévaluerait les volumes** et pourrait conclure à tort à l'absence de
contre-passations. Les analyses du présent rapport, fondées sur des sommes signées, ne sont pas
affectées ; les formulations du §8.1 ont néanmoins été précisées en conséquence.

À noter que **Calypso ne produit aucun montant négatif** : il contre-passe par une écriture de sens
inverse (mécanisme « cancel & rebook » décrit au §4.5). Les deux systèmes ont donc des conventions
de correction **opposées**, ce dont il faut tenir compte dans tout rapprochement.

---

## 12. Troisième exploration — historique complet du compte `511800100`

La banque a fourni l'historique intégral du compte d'intérêts courus sur titres de placement
(`creance_rattaché.csv`, **32 937 lignes, 16/08/2022 → 31/07/2025**, tous modules confondus).
Le fichier est encodé en **CP1252** et non en UTF‑8, et comporte 43 espaces insécables (`0xA0`)
dans les libellés ; il utilise par ailleurs un format de date `JJ-MMM-AA` différent des autres
extractions. Un chargeur dédié a été ajouté (`scripts/load.py`, fonction `cr()`).

### 12.1 Le constat initial est infirmé : le compte fonctionne normalement

| Contrôle | Résultat |
|---|---|
| Débits | 32 136 lignes — **15 005 402 277,00 XAF** |
| **Crédits** | **801 lignes — 15 005 402 277,00 XAF** |
| **Solde net sur tout l'historique** | **0,00 XAF** |

**Le compte est intégralement apuré.** Les crédits existent bien — ils étaient simplement
**invisibles dans l'extraction précédente, filtrée sur le module MM**, car ils sont passés en
**module `DE` (écriture directe)**.

**Où était l'erreur de raisonnement.** Le premier fichier ne contenait que le module `MM`. J'en
avais conclu à l'absence d'apurement, alors qu'il n'y avait qu'une absence d'apurement *dans ce
module*. J'avais bien posé l'hypothèse alternative dès le §8.1 (« les coupons sont encaissés hors
du module MM ») et demandé l'extraction tous modules — c'est elle qui tranche, et elle tranche en
faveur de la banque.

### 12.2 Comment les coupons sont réellement comptabilisés
La contrepartie des 801 apurements a été retrouvée dans les autres extractions : il s'agit du
**compte BEAC `099ACO00001`** (499 débits pour 31 309 830 000 XAF, plus les mouvements liés aux
bons via `472200106`). **Les coupons sont donc bien encaissés en trésorerie.**

Schéma réel, qui complète le cycle de vie décrit au §3.5 :
```
  ② chaque jour (module MM, automatique)
     D 511800100 / C 733400100                     ← couru quotidien
  ③ au détachement du coupon (module DE, MANUEL)
     D 099ACO00001 (BEAC) / C 511800100            ← encaissement, apurement de la créance
```

### 12.3 Profil du compte — un fonctionnement sain
| Date | Solde (XAF) |
|---|---:|
| 31/12/2022 | 235 739 034 |
| 31/12/2023 | 662 336 797 |
| 30/06/2024 | 1 975 466 036 |
| 31/12/2024 | 2 455 219 083 |
| **Maximum — 22/05/2025** | **3 298 021 048** |
| 13/06/2025 (veille de bascule) | 2 927 747 645 |
| **16/06/2025 (bascule)** | **−1 205 231 891** |
| **30/06/2025 (arrêté semestriel)** | **−1 205 231 891** |
| 31/07/2025 | **0** |

Le compte **oscille normalement** : il monte entre deux coupons et retombe à chaque encaissement.
C'est le profil attendu d'un compte de créances rattachées.

### 12.4 Qualité du contrôle interne sur ces apurements — satisfaisante
Les 801 écritures d'apurement présentent un **contrôle « 4 yeux » sans faille** :

| Contrôle | Résultat |
|---|---|
| Écritures auto-validées (`USER_ID` = `AUTH_ID`) | **0 sur 801** |
| Écritures sans validateur (`AUTH_ID` vide) | **0 sur 801** |
| Saisisseurs distincts | 7 (`BINEID00087` 431, `CHEICHEID059` 264, `NDJOCKOS0067` 52, …) |
| Valideurs distincts | 7 (`MBATOHID0012` 577, `CELESID0018` 124, `MBOGID000083` 69, …) |

Les libellés sont par ailleurs **remarquablement documentés** : ils portent la référence du contrat
MM, le code du titre, le nominal, le montant couru et le taux — par exemple
`099OTAP242490004 GA2B00000109 4000000000 194299723 6.25 %`. C'est une excellente piste d'audit.

**Observation résiduelle** : l'apurement est **entièrement manuel** (801 écritures en trois ans), là
où le module MM de Flexcube dispose d'un événement de liquidation d'intérêts automatique
(`INT_BT_LIQD`), utilisé pour les bons du Trésor mais **jamais pour les obligations**. Ce choix de
paramétrage fait reposer l'apurement sur une intervention humaine récurrente. Il est bien contrôlé
aujourd'hui, mais il constitue un point de fragilité opérationnelle à signaler.

### 12.5 — CONSTAT — Sur-apurement de 1,2 Md XAF à la migration, non corrigé pendant 45 jours

C'est le constat que révèle réellement l'historique complet.

**Le 16/06/2025**, l'écriture manuelle `099001b251670001` (saisie `CHEICHEID059`, validée
`MBATOHID0012`) solde le compte en 55 lignes, contrat par contrat :

| Élément | Montant (XAF) |
|---|---:|
| Solde du compte au 13/06/2025 | 2 927 747 645 |
| Courus du 16/06/2025 (dernier accrual automatique) | 36 144 257 |
| **Solde réel à apurer** | **2 963 891 902** |
| **Crédit effectivement passé** | **4 169 123 793** |
| **SUR-APUREMENT** | **1 205 231 891** |

**Cause identifiée.** Le rapprochement contrat par contrat montre que l'écriture a crédité, pour
chaque contrat, **le cumul des intérêts courus depuis son origine**, sans déduire **les coupons
déjà encaissés**. Exemple :

> Contrat `099OTAP232130001` — cumul des courus depuis le 01/08/2023 : **353 424 658 XAF** ;
> coupon déjà encaissé avant la bascule : **181 572 816 XAF** ; solde réel restant :
> **171 851 842 XAF**. Montant crédité à la migration : **353 424 658 XAF**,
> soit **181 572 816 XAF de trop**.

**23 des 55 contrats** sont concernés, pour un écart cumulé de **1 444 094 752 XAF** au niveau
contrat (l'écart au niveau du compte, 1 205 231 891 XAF, est net des courus du jour).

**Conséquences, sur deux comptes à la fois :**
1. Le compte `511800100`, qui est un **compte d'actif**, a présenté un **solde créditeur de
   1 205 231 891 XAF** — une position anormale par construction ;
2. la contrepartie étant un **débit du compte BEAC `099ACO00001`**, la banque a enregistré
   **4 169 123 793 XAF d'encaissement** là où la créance réelle était de 2 963 891 902 XAF :
   le **nostro BEAC a été surévalué de 1,2 Md XAF** sur la même période.

**Durée de l'anomalie : 45 jours**, du 16/06/2025 au 30/07/2025 inclus — **l'arrêté semestriel du
30/06/2025 est traversé**. La correction n'intervient que le **31/07/2025**, par l'écriture
`099000b252120001` (saisie `NDJOCKOS0067`, validée `MBATOHID0012`), libellée
**« ACCRUALS LIQUIDATION RELATED TO CALYPSO GO LIVE »** : D `511800100` 1 205 231 891 /
C `099ACO00001` 1 207 226 407. L'écart de **1 994 516 XAF** entre les deux jambes indique une
troisième jambe, non identifiée dans les extractions disponibles.

**Ce qu'il faut instruire :**
1. Les **états financiers au 30/06/2025** portaient-ils ce solde créditeur de 1,2 Md sur un compte
   d'actif, et un nostro BEAC surévalué d'autant ? Si un arrêté semestriel a été publié, l'anomalie
   y figure.
2. Le **rapprochement du nostro BEAC** de juin et juillet 2025 : un écart de 1,2 Md aurait dû être
   détecté par le rapprochement bancaire mensuel. Pourquoi 45 jours ?
3. La **troisième jambe** de l'écriture de correction (1 994 516 XAF).
4. La **procédure de contrôle de la migration** : le calcul des courus à reprendre a été effectué
   à partir du cumul théorique par contrat et non du solde comptable ; ce mode opératoire a-t-il
   été revu ?

### 12.6 Contrôle positif : l'exactitude du calcul des intérêts courus
Le recoupement entre les données portées par les libellés (nominal, taux, montant couru) et la
durée effective de détention confirme l'**exactitude du calcul des courus**. Exemple :

> Contrat `099OTAP243480002` — nominal 4 000 000 000 XAF à 6,70 %, couru du 13/12/2024 au
> 16/06/2025 (185 jours). Attendu : 4 000 000 000 × 6,70 % × 185/365 = **135 890 411 XAF**.
> Comptabilisé : **135 797 500 XAF**, soit un écart de 0,07 % (convention de décompte des jours).

Sur les 55 contrats migrés, 31 n'avaient encaissé aucun coupon avant la bascule et 24 en avaient
encaissé un — répartition cohérente avec des titres acquis majoritairement en 2024 et 2025 et
portant des coupons annuels. **Aucun indice d'arriéré de paiement des États émetteurs** n'est
décelable dans ces données.

### 12.7 Enseignement de méthode
Cet épisode illustre une limite à garder présente à l'esprit pour toute la suite des travaux :
**une extraction filtrée par module peut faire apparaître une anomalie qui n'existe pas.** Le
module `DE` (écriture directe) de Flexcube porte des opérations structurantes — apurement des
coupons, corrections, écritures de migration — qui n'apparaissent dans aucune extraction filtrée
sur un module fonctionnel.

**Règle retenue pour la suite** : tout constat portant sur le solde ou le comportement d'un compte
doit être établi sur une extraction **du compte, tous modules confondus**, et non sur une
extraction par module. Les constats du présent rapport qui reposent encore sur des extractions
partielles sont signalés comme tels et devront être confirmés selon cette règle — en particulier
le §11.4 (réévaluation de change sans impact résultat), dont la contrepartie en compte de résultat
pourrait se trouver, comme ici, dans un module non extrait.

---

## 13. Quatrième exploration — les 41 comptes de trésorerie, tous modules

L'extraction demandée au §12.7 a été livrée : `final_key_accounts_Export Worksheet_part_1..6.csv`,
**329 884 lignes**, **08/06/2022 → 18/09/2026**, couvrant les **41 comptes généraux** du périmètre
trésorerie, **tous modules confondus**. Encodage UTF‑8 conforme.

C'est la première extraction qui permette de raisonner sur des **soldes** et non sur des flux
partiels : pour les comptes créés après juin 2022, le solde d'ouverture est nul par construction,
donc le cumul des mouvements **est** le solde.

Modules représentés : `DE` 214 511, `MM` 76 720, `FT` 22 654, `RE` 15 415, `RT` 556, **`GL` 28**.

### 13.1 — CONSTAT MAJEUR — 136,5 Md XAF en comptes de liaison Calypso au 30/06/2026

Deux comptes de liaison (« bridge ») ont été ouverts lors du démarrage de Calypso. Leur **première
écriture date du 16/06/2025**, leur solde d'ouverture est donc **nul** et le cumul des mouvements
est le solde exact.

| Fin de trimestre | `467000186` CALYPSO BRIDGE | `467000188` CALYPSO BRIDGE MONEY MARKET |
|---|---:|---:|
| 30/06/2025 | +15 491 672 | 0 |
| 30/09/2025 | −5 233 940 957 | 0 |
| 31/12/2025 | −15 685 996 937 | −5 000 000 000 |
| 31/03/2026 | −33 604 411 774 | −93 902 460 379 |
| **30/06/2026 (fin de période d'audit)** | **−42 058 339 493** | **−94 451 445 974** |
| 18/09/2026 | −48 325 343 347 | −94 549 929 809 |

> **Au 30/06/2026, les deux comptes de liaison Calypso présentent un solde créditeur cumulé de
> 136 509 785 467 XAF**, en progression monotone depuis l'origine.

Un compte de liaison est, par construction, un **compte de passage** : il est mouvementé dans un
sens à l'initiation de l'opération et dans l'autre à son dénouement, et doit donc **revenir à zéro**.
Un solde de 136,5 Md qui ne fait que croître signale que **le dénouement ne suit pas l'initiation**.

**Décomposition par événement** :

| Compte | Événement | Lignes | Net (XAF) |
|---|---|---:|---:|
| `467000186` | `NOMINAL` (entrée des titres) | 625 | −278 964 643 333 |
| | `CST_S_SETTLED` (règlement espèces) | 752 | +225 434 453 018 |
| | `PREM_DISC` | 232 | +13 070 027 663 |
| | `NOM_FULL` (ventes clientèle) | 95 | −16 277 959 855 |
| | `ACCRUAL_BS` | 525 | −4 766 217 073 |
| `467000188` | `CST_S_SETTLED` | 802 | −136 845 391 709 |
| | `PRINCIPAL_DEPOSIT` (repo) | 261 | +20 000 000 000 |
| | `INTEREST` (repo) | 129 | −2 716 616 674 |

Par portefeuille, l'écart se concentre sur :
- **`ABCM_MM.Plmt.Tkn.Secured` (pensions livrées BEAC) : −120 253 163 889 XAF** ;
- **`ABCM_FVOCI.Bond` : −38 010 893 736 XAF** ;
- `ABCM_FI.Sales` : −16 289 259 855 XAF ; `ABCM_FVOCI.Bills` : −7 200 657 222 XAF.

**Ce qu'il faut instruire, par ordre d'urgence :**
1. **Le solde de ces deux comptes figure-t-il tel quel au bilan au 30/06/2026 ?** 136,5 Md XAF en
   compte d'attente non justifié seraient un point d'audit de première importance.
2. **Existe-t-il un état de rapprochement** de ces comptes, et à quelle fréquence est-il produit ?
   Une dérive monotone sur 15 mois suggère qu'aucun apurement systématique n'est opéré.
3. **L'écart se concentre sur le repo BEAC** (−120 Md). Le rapprochement avec le compte
   `552400100` (encours emprunté : 45 Md) et avec les états de la BEAC est prioritaire.
4. S'agit-il d'écritures **non dénouées**, d'un **paramétrage d'interface asymétrique** (une jambe
   déversée dans Flexcube, l'autre non), ou d'un **décalage de dates de valeur** ?

### 13.2 Le résultat de l'activité trésorerie, par exercice
Le module **`GL`** (28 lignes, produit `ZYND`, étiquette `YEND`) porte les **écritures de clôture
annuelle** : chaque compte de résultat y est soldé en fin d'exercice. Elles donnent donc directement
le **compte de résultat de l'activité** :

| | 2022 * | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|
| **PRODUITS** | | | | |
| `733400100` Revenus d'obligations et bons assimilés | 237 349 993 | 1 948 298 718 | 4 493 601 922 | 9 391 787 162 |
| `734400100` Revenus d'obligations et bons (2ᵉ jeu) | 548 387 845 | 3 328 305 701 | 6 048 526 398 | 10 858 598 333 |
| `733200100` Revenus de bons du Trésor | 400 732 332 | 208 334 751 | 873 177 474 | 1 268 828 550 |
| `734200100` Revenus de bons du Trésor (2ᵉ jeu) | — | — | 7 519 237 | 42 928 009 |
| `727000102` Refacturation commissions refinancement BEAC | 156 673 648 | 355 118 791 | 382 454 122 | 640 098 457 |
| `729000125` Commissions de service hors CEMAC | 136 835 302 | 351 251 193 | 266 879 362 | 652 212 323 |
| `725000100` Commission gestion portefeuille titres tiers | 411 966 | 3 933 775 | 6 402 500 | 632 600 |
| **CHARGES** | | | | |
| `601100100` Intérêts sur opérations de marché monétaire | — | — | — | **−520 308 336** |
| `625000105` Commissions payées sur achat de devises | — | — | — | −4 691 336 |
| **RÉSULTAT** | **1 480 391 086** | **6 195 242 929** | **12 078 561 015** | **22 330 085 762** |

\* 2022 ne couvre que juin-décembre (début de l'extraction : 08/06/2022). 2026 n'a pas encore de
clôture annuelle.

**Le résultat double quasiment chaque année** : ×4,2 de 2022 (partiel) à 2023, ×1,95 en 2024, ×1,85
en 2025. Cette croissance est à rapprocher de l'essor du portefeuille et du recours au
refinancement BEAC. Elle mérite en elle-même une revue analytique : quelle part provient de la
progression des encours, quelle part d'un changement de méthode de valorisation ?

**Deux observations d'audit** :
- la **charge d'intérêt du refinancement BEAC n'apparaît qu'en 2025** (520 M XAF), cohérent avec le
  démarrage du repo en novembre 2025 — mais à rapprocher du constat §8.6 sur le rattachement
  défaillant des charges ;
- **aucun compte de gains ou pertes de change ne figure dans les écritures de clôture** du
  périmètre trésorerie. Voir §13.3.

### 13.3 — CONSTAT CONFIRMÉ — La réévaluation de change n'est jamais portée au résultat
Le §11.4 reposait sur une extraction partielle. Avec les 41 comptes sur **quatre ans et tous
modules**, le constat est désormais établi :

**Test 1 — les couples position / contre-valeur se compensent exactement.**

| Devise | Position (`475…`) | Contre-valeur (`476…`) | Écart |
|---|---:|---:|---:|
| USD | −7 228 911 275 | +7 228 911 275 | **0** |
| EUR | −30 821 293 932 | +30 821 293 932 | **0** |
| GBP | +234 602 783 | −234 602 783 | **0** |
| ZAR | +88 752 605 | −88 752 605 | **0** |

**Test 2 — aucune écriture touchant un compte `475…`/`476…` ne touche un compte de résultat**,
hormis des **commissions** (`729000125` : −2 357 145 000 ; `727000102` : −1 913 010 000 ;
`625000105` : +11 990 010). Aucun compte de gain ou perte de change n'apparaît jamais.

**Test 3 — le module `RE` (réévaluation) ne mouvemente que les comptes de position, de
contre-valeur et de hors bilan.** 15 415 lignes sur quatre ans, aucune jambe de résultat.

**Montant de la réévaluation jamais constatée en résultat** (compte de contre-valeur) :

| Exercice | USD | EUR | GBP | ZAR | Total |
|---|---:|---:|---:|---:|---:|
| 2022 | 138 825 565 | 777 910 | — | — | 139 603 474 |
| 2023 | 763 844 332 | −228 900 130 | — | 1 075 572 | 536 019 775 |
| 2024 | 337 605 765 | 295 236 | — | — | 337 901 001 |
| 2025 | 1 603 812 133 | 5 104 | −113 444 | — | 1 603 703 792 |
| 2026 (au 18/09) | 1 234 454 827 | −24 464 783 | 24 638 501 | 29 385 710 | 1 264 014 255 |
| **CUMUL** | **4 078 542 622** | **−252 286 663** | **24 525 057** | **30 461 282** | **3 881 242 297** |

**Portée.** En régime de parité fixe, la position en EUR ne peut pas générer de résultat de change,
ce que confirme la quasi-nullité de la colonne EUR. En revanche, **la position en USD est une
position ouverte** : sa réévaluation a produit **4 078 542 622 XAF de variation cumulée**, dont
**1,60 Md sur le seul exercice 2025** et **1,23 Md sur 2026 à fin septembre**. Ces montants restent
logés dans le compte de contre-valeur et **ne remontent jamais au compte de résultat**.

Si ce traitement est confirmé, il affecte **le résultat, les fonds propres et la position de change
réglementaire déclarée à la COBAC**. C'est, avec le §13.1, le constat le plus significatif de cette
exploration.

*Réserve* : un compte de gains et pertes de change pourrait exister hors des 41 comptes extraits et
être alimenté par une écriture sans lien avec les comptes `475`/`476`. La requête de découverte du
plan de comptes (`gl_desc LIKE '%CHANGE%'`) reste à exécuter pour lever définitivement ce doute.

### 13.4 Soldes du portefeuille — les comptes anciens sont proprement soldés
Sur l'historique complet, les comptes du dispositif Flexcube **reviennent exactement à zéro**, ce
qui confirme une extinction propre lors de la bascule :

| Compte | Lignes | Solde net | Lecture |
|---|---:|---:|---|
| `511410100` Obligations du Trésor — placement | 980 | **0** | Portefeuille MM intégralement soldé |
| `512200100` Bons du Trésor — transaction | 228 | **0** | Idem |
| `511800100` Créances rattachées — placement | 32 937 | **0** | Confirme le §12.1 |
| `591400100` Provision pour dépréciation | 68 | **0** | Provision reprise en totalité |

Et le dispositif Calypso porte les encours actuels :

| Compte | Solde au 18/09/2026 (XAF) |
|---|---:|
| `512410100` Obligations du Trésor — transactions | **273 879 643 333** |
| `512800100` Créances rattachées — transaction | 23 095 801 059 |
| `511210100` Bons du Trésor (BTA) — placement | 11 010 000 000 |
| `472200106` / `472200108` Comptes de régularisation | 718 339 497 / −628 532 411 |

### 13.5 Refinancement BEAC — chiffres corrigés
L'historique complet corrige l'estimation du §7 (fondée sur une extraction partielle) :

| | Estimation §7 | **Chiffre corrigé** |
|---|---:|---:|
| Encours emprunté (`552400100`) au 14/09/2026 | ~25 Md | **45 000 000 000 XAF** |
| Collatéral mobilisé (`952100100`) | 77,85 Md | **71 847 170 000 XAF** |
| **Sur-collatéralisation** | ~53 Md | **26 847 170 000 XAF** |

Le compte `552400100` présente par ailleurs une écriture isolée en **2022** (3,5 Md au débit et au
crédit, net nul), antérieure de trois ans au démarrage du repo — à qualifier.

La sur-collatéralisation de **26,8 Md XAF** (60 % de l'encours emprunté) reste un point à
instruire : titres restés affectés en garantie après dénouement, ou exigence de marge de la BEAC ?

### 13.6 Écritures techniques du 10/06/2023 (`i099` / `z099`)
Une paire d'écritures techniques touche **tous les comptes du périmètre** le 10/06/2023 :
chaque compte reçoit un montant **négatif** sous le produit `i099` et le **même montant positif**
sous `z099` — effet net **nul**. Exemples : `511410100` ±24 981 550 000, `512200100` ±2 050 000 000,
`511800100` ±780 228 400, `475000102`/`476000102` ±2 984 132 000.

Il s'agit selon toute vraisemblance d'une **reprise technique de soldes** (renumérotation ou
migration interne Flexcube). L'effet comptable est nul, mais l'opération doit être documentée : elle
touche 14 comptes du périmètre pour des montants significatifs, un même jour, et elle n'a pas
d'équivalent ailleurs dans l'historique.

### 13.7 Ce qui reste hors d'atteinte
- La **troisième jambe** des écritures de migration du compte `511800100` (§12.5) n'est pas dans les
  41 comptes : l'écart de 1 994 516 XAF entre les deux jambes connues reste inexpliqué.
- Les **comptes de gains et pertes de change** n'ont pas été identifiés (codes inconnus) — requête
  de découverte du plan de comptes à exécuter.
- Les **soldes en balance générale** aux dates d'arrêté n'ont pas été fournis. Pour les comptes créés
  après juin 2022 (comptes de liaison Calypso notamment), le cumul des mouvements tient lieu de
  solde ; pour les autres, l'ancrage reste nécessaire.

---

## 14. Révision — l'historique des 41 comptes est intégral, les soldes sont calculables

La banque a signalé que la quatrième extraction porte l'historique **entier** des 41 comptes de
trésorerie. Ce point change la portée de plusieurs analyses : il fallait le vérifier, puis en tirer
les conséquences.

### 14.1 Démonstration de la complétude
Trois éléments concordants l'établissent :

| Élément de preuve | Constat |
|---|---|
| **Comptes revenant exactement à zéro** | `511410100`, `512200100`, `511800100` et `591400100` présentent un solde net de **0,00 XAF** sur toute leur vie. Un historique tronqué ne le permettrait pas. |
| **Concordance avec l'extraction dédiée** | L'extraction du seul compte `511800100` compte **32 937 lignes** du 16/08/2022 au 31/07/2025, solde 0,00 — **strictement identique** à ce que porte l'extraction des 41 comptes. |
| **Absence de mur de troncature** | Les dates de première écriture sont échelonnées (2 comptes au 08/06/2022, 3 au 10/06, 1 au 13/06, 2 au 05/08, 3 au 16/08…) et non concentrées sur une date unique. |

**Conséquence** : pour chacun des 41 comptes, le solde d'ouverture est nul par construction et le
cumul des mouvements constitue le solde exact à toute date. La limite n°1 du §9.1 est levée.

### 14.2 — CORRECTION du §7 — Le solde anormal du compte d'emprunt n'est pas un solde d'ouverture

J'avais écrit au §7.3 que le cumul du compte `552400100` partant à −5 000 000 000 XAF démontrait
l'existence d'un solde d'ouverture non fourni. **C'était faux.** L'historique intégral montre que
le compte démarre bien à zéro le 28/09/2022 et que le résidu a une tout autre origine.

Le 07/11/2025, le deal `3186053` produit trois écritures sur le compte d'emprunt au lieu de deux :

| Référence externe | Sens | Montant | Nature |
|---|---|---:|---|
| `CLP3186053_23630317_182512` | C | 5 000 000 000 | tirage |
| `CLP3186053_23630318_182512` | D | 5 000 000 000 | remboursement |
| `CLP3186053_23630318_182513` | D | 5 000 000 000 | **remboursement en double** |

Le mouvement Calypso **23630318** est déversé **deux fois**, sous deux références Flexcube
distinctes et deux horodatages différents. Il en résulte un résidu débiteur permanent de
**5 000 000 000 XAF** sur un compte d'emprunt, qui persiste plus de dix mois — jusqu'à la fin de
l'extraction.

### 14.3 — CONSTAT NOUVEAU — L'interface Calypso n'est pas idempotente

Ce cas n'est pas isolé. La recherche systématique des mouvements Calypso portant le même
identifiant de transfert, le même compte, le même sens et le même montant sous plusieurs références
Flexcube donne :

| | |
|---|---:|
| **Mouvements déversés en double** | **178** |
| **Montant total dupliqué** | **289 631 995 600 XAF** |
| Période | 29/09/2025 → 15/09/2026 |
| Comptes touchés | 36 |

Impact sur le solde des comptes les plus affectés :

| Compte | Libellé | Mouvements | Impact sur le solde (XAF) |
|---|---|---:|---:|
| `552400100` | Emprunt au jour le jour | 4 | **+30 000 000 000** |
| `467000188` | Calypso bridge account money market | 15 | −29 685 292 656 |
| `952100100` / `995000100` | Titres affectés en garantie | 2 | ±16 000 000 000 |
| `467000186` | Calypso bridge account | 17 | −14 893 700 500 |
| **`099ACO00001`** | **Banque des États de l'Afrique Centrale** | 7 | **+11 693 426 801** |
| **`512410100`** | **Obligations du Trésor — transactions** | 6 | **+3 153 680 000** |

**Portée.** L'interface peut rejouer une opération déjà déversée sans la détecter. Deux comptes du
bilan sont directement touchés : le **nostro de la banque centrale**, surévalué de 11,7 Md XAF, et
le **portefeuille de titres**, surévalué de 3,2 Md XAF. Aucune écriture d'annulation n'est passée.

Ce défaut constitue par ailleurs une **cause racine** de la dérive des comptes de liaison décrite
au §13.1 : à eux seuls, les doublons expliquent 44,6 Md XAF sur les 136,5 Md constatés.

*À demander* : le journal de l'interface, le mécanisme de contrôle d'unicité prévu, et le
rapprochement quotidien entre mouvements émis par Calypso et écritures reçues dans le grand livre.

### 14.4 — CONSTAT NOUVEAU — Soldes contraires à la nature comptable aux dates d'arrêté

Le calcul des soldes aux dates d'arrêté, désormais possible, fait apparaître trois comptes dont le
solde contredit leur nature :

| Compte | Libellé | Nature | Arrêté | Solde à cette date |
|---|---|---|---|---:|
| `511800100` | Créances rattachées — placement | actif | **30/06/2025** | **−1 205 231 891** |
| `472200106` | Produits perçus d'avance sur bons du Trésor | passif | **30/06/2026** | **+686 724 016** |
| `559000101` | Dettes rattachées emprunt au jour le jour | passif | **30/06/2026** | **+66 000 000** |

Le premier cas est celui déjà documenté au §12.5 — le contrôle le détecte désormais
automatiquement à la date d'arrêté.

Le deuxième est nouveau et significatif : un compte de **produits perçus d'avance** devenu
**débiteur** signifie que l'étalement au résultat a dépassé le produit initialement différé. Le
compte est créditeur jusqu'au 31/12/2025 (−55,7 M) puis bascule : +323,9 M au 31/03/2026,
**+686,7 M au 30/06/2026**. Autrement dit, **686,7 M XAF de produits ont été reconnus sans
contrepartie** à la clôture semestrielle.

### 14.5 — CONSTAT NOUVEAU — Les intérêts courus dépassent une année de coupons

Le calcul du portefeuille et des courus à chaque arrêté donne :

| Date d'arrêté | Portefeuille (XAF) | Courus (XAF) | Courus / portefeuille | Années d'intérêts |
|---|---:|---:|---:|---:|
| 31/12/2023 | 71 749 600 000 | 662 336 797 | 0,92 % | 0,15 |
| 30/06/2024 | 79 310 970 000 | 1 975 466 036 | 2,49 % | 0,42 |
| 31/12/2024 | 115 432 180 000 | 2 455 219 083 | 2,13 % | 0,35 |
| 30/06/2025 | 135 921 813 333 | 2 185 349 530 | 1,61 % | 0,27 |
| 31/12/2025 | 212 912 553 333 | 10 964 366 724 | 5,15 % | 0,86 |
| **30/06/2026** | **244 098 816 666** | **19 249 608 622** | **7,89 %** | **1,31** |

Rapportées à une année d'intérêts théorique au taux médian du portefeuille (6,00 %), les créances
rattachées dépassent **douze mois de coupons** au 30/06/2026. Sur un portefeuille de titres à
coupon annuel, cela signifie que des coupons échus n'ont pas été encaissés, ou que les courus
correspondants n'ont pas été apurés.

La rupture est nette et datée : le ratio reste entre 0,15 et 0,42 année sous Flexcube, puis passe à
0,86 au 31/12/2025 et à 1,31 au 30/06/2026 — **après la bascule**. Il convient de déterminer si le
changement d'outil a altéré le suivi des encaissements de coupons.

### 14.6 Enseignement de méthode, complémentaire du §12.7
Le §12.7 retenait qu'un constat sur le solde d'un compte doit reposer sur une extraction tous
modules confondus. Le présent épisode ajoute une seconde condition, symétrique :

> **Avant de conclure qu'un solde d'ouverture manque, il faut vérifier que l'extraction ne porte
> pas déjà l'historique intégral.** Un solde anormal n'est pas nécessairement la trace d'une
> donnée absente : il peut être l'anomalie elle-même.

Appliquée ici, cette vérification a transformé une limite supposée en trois constats d'audit.

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

2. **Cinq pistes d'audit prioritaires** :
   - **136,5 Md XAF de solde créditeur non apuré** sur les deux comptes de liaison Calypso au
     30/06/2026, ouverts à zéro le 16/06/2025 et en dérive monotone depuis, dont **120 Md sur le
     seul portefeuille de pensions livrées BEAC** (§13.1) ;
   - **215 opérations de Sell-Buy-Back** (896 Md XAF réglés) comptabilisées en cession et
     acquisition fermes au lieu d'un financement garanti, un même titre étant recyclé jusqu'à
     **9 fois** avec la même contrepartie (§11.5) ;
   - la **réévaluation de change n'est jamais portée au résultat** — constat désormais établi sur
     quatre ans et tous modules : **4 078 542 622 XAF** de variation cumulée sur la position USD,
     dont 1,60 Md sur le seul exercice 2025 (§13.3) ;
   - le **sur-apurement de 1 205 231 891 XAF** du compte d'intérêts courus à la migration, laissant
     un **compte d'actif en solde créditeur et le nostro BEAC surévalué d'autant pendant 45 jours**,
     **arrêté semestriel du 30/06/2025 compris** (§12.5) ;
   - les **3 076 écritures manuelles sans validateur** (1 231 Md XAF, §8.8) et les **pensions
     livrées de 6 à 98 jours** logées en emprunt au jour le jour (832 Md XAF, §8.6).

   **Deux constats antérieurs sont retirés** (§8.1 et §11.10) : l'extraction complète du compte
   `511800100` montre qu'il est **intégralement apuré, solde net nul**, les coupons étant bien
   encaissés en trésorerie sur le compte BEAC par des écritures manuelles en module `DE`.

3. **Une zone d'ombre à lever d'urgence** : l'absence du **référentiel des deals Calypso**, qui
   prive l'audit de toute donnée contractuelle sur 65 % de la période.

   S'y ajoute une **règle de méthode désormais acquise** (§12.7) : tout constat portant sur le solde
   ou le comportement d'un compte doit être établi sur une extraction **du compte, tous modules
   confondus**. Une extraction filtrée par module peut faire apparaître une anomalie inexistante —
   c'est précisément ce qui s'est produit sur le compte `511800100`.

4. **Le résultat de l'activité double quasiment chaque exercice** — 6,20 Md en 2023, 12,08 Md en
   2024, 22,33 Md en 2025, d'après les écritures de clôture annuelle (§13.2). Cette progression
   appelle une revue analytique : quelle part tient à la croissance des encours, quelle part à un
   changement de méthode de valorisation ?

5. **Une source de preuve nouvelle et sous-exploitée** : les **22 847 commentaires libres** saisis
   par la salle des marchés dans le champ `DESCRIPTION` documentent l'**intention économique** des
   opérations (SBB, marges de change négociées, rétrocessions réglementaires). C'est par eux que la
   nature réelle des Sell-Buy-Back a pu être établie — elle était invisible dans les seuls schémas
   comptables. Ils doivent être systématiquement exploités dans la suite des travaux.

---

*Rapport d'exploration établi à partir des données extraites du core banking.
Le détail chronologique des travaux, des requêtes exécutées et des vérifications figure dans le
document `CARNET_DE_BORD.md`.*
