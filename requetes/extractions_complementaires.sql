-- =====================================================================================
--  AUDIT TRÉSORERIE — REQUÊTES D'EXTRACTION COMPLÉMENTAIRES
--  Base : requête fournie par la banque (actb_history + sttb_account + cstb_addl_text)
--  Les colonnes et leur ordre sont conservés à l'identique, pour que les fichiers
--  produits soient lisibles par les mêmes chargeurs (scripts/load.py).
-- =====================================================================================
--
--  CONSIGNES D'EXPORT (importantes, tirées des difficultés rencontrées) :
--    1. Exporter en **UTF-8**. Le fichier creance_rattaché.csv était en CP1252 et
--       contenait des espaces insécables (0xA0) : la lecture échouait.
--    2. Exporter les numéros de compte et références **en texte**, pour préserver
--       les zéros de tête (00110000006, 099ACO00001...).
--    3. Conserver le format de date tel quel ; indiquer lequel a été utilisé.
--    4. Si un fichier dépasse ~60 000 lignes, le découper (part_1, part_2...) comme
--       précédemment : la concaténation est automatique côté analyse.
--    5. Si des écritures récentes manquent, ajouter ACTB_DAILY_LOG en UNION ALL
--       (voir requête 6) : ACTB_HISTORY ne contient pas toujours la période courante.
--
-- =====================================================================================
--  REQUÊTE 0 — PLAN DE COMPTES  [PRIORITÉ 1 — très petite, très utile]
-- =====================================================================================
--  Objectif : disposer du référentiel des comptes généraux. Cela permet d'identifier
--  sans deviner les comptes de résultat de change (§11.4 du rapport) et de comprendre
--  la règle d'affectation entre les comptes 733xxx et 734xxx (§8.11).
--  Volume attendu : quelques milliers de lignes. Fichier : plan_de_comptes.csv

SELECT gl_code, gl_desc, gl_type, leaf_parent, ccy_restriction, record_stat
FROM   gltb_glmaster
ORDER  BY gl_code;

-- Si la table porte un autre nom dans votre installation, l'équivalent est le
-- référentiel des GL (chart of accounts). L'essentiel est : code + libellé + type.


-- =====================================================================================
--  REQUÊTE 1 — COMPTES DE RÉSULTAT DE CHANGE  [PRIORITÉ 1]
-- =====================================================================================
--  Objectif : trancher le constat §11.4. Les écritures de réévaluation (module RE,
--  produit ACPO) se bouclent entre le compte de position (475xxx) et sa contre-valeur
--  (476xxx) sans jamais toucher un compte de résultat. Soit le virement au résultat
--  est passé par une écriture distincte, soit il ne l'est pas.
--  Enjeu chiffré : +3 536 553 336 XAF de réévaluation cumulée sur la position USD.
--
--  Étape A — identifier les comptes concernés (à exécuter d'abord) :

SELECT gl_code, gl_desc
FROM   gltb_glmaster
WHERE  UPPER(gl_desc) LIKE '%CHANGE%'
   OR  UPPER(gl_desc) LIKE '%REEVAL%'
   OR  UPPER(gl_desc) LIKE '%RÉÉVAL%'
   OR  UPPER(gl_desc) LIKE '%ECART DE CONV%'
   OR  UPPER(gl_desc) LIKE '%GAIN%CHANGE%'
   OR  UPPER(gl_desc) LIKE '%PERTE%CHANGE%'
ORDER  BY gl_code;

--  Étape B — extraire les mouvements des comptes ainsi identifiés, en remplaçant
--  la liste ci-dessous par les codes trouvés (classes 6 et 7 du PCEC) :

SELECT
    c.addl_text description, a.trn_ref_no, a.ac_no, a.ac_ccy, a.fcy_amount,
    a.lcy_amount, a.trn_dt, a.drcr_ind, a.user_id, a.auth_id, a.amount_tag,
    a.stmt_dt, b.ac_natural_gl, a.product, b.ac_gl_desc, a.module, a.external_ref_no
FROM   actb_history a
LEFT JOIN sttb_account b    ON a.ac_no = b.ac_gl_no
LEFT JOIN cstb_addl_text c  ON c.reference_no = a.trn_ref_no
                           AND c.evnt_seq_no  = a.event_sr_no
WHERE  a.ac_no IN ( /* <-- codes issus de l'étape A */ )
ORDER  BY a.stmt_dt;


-- =====================================================================================
--  REQUÊTE 2 — ÉCRITURES COMPLÈTES DE RÉÉVALUATION  [PRIORITÉ 1]
-- =====================================================================================
--  Objectif : le moyen le plus sûr de trancher le §11.4 sans rien deviner.
--  On extrait TOUTES les jambes des écritures qui touchent un compte de position de
--  change — y compris les jambes sur des comptes que je n'ai pas. Si une jambe de
--  résultat existe, elle apparaîtra ici.
--  Volume attendu : ~30 000 à 40 000 lignes. Fichier : reevaluation_complete.csv

SELECT
    c.addl_text description, a.trn_ref_no, a.ac_no, a.ac_ccy, a.fcy_amount,
    a.lcy_amount, a.trn_dt, a.drcr_ind, a.user_id, a.auth_id, a.amount_tag,
    a.stmt_dt, b.ac_natural_gl, a.product, b.ac_gl_desc, a.module, a.external_ref_no
FROM   actb_history a
LEFT JOIN sttb_account b    ON a.ac_no = b.ac_gl_no
LEFT JOIN cstb_addl_text c  ON c.reference_no = a.trn_ref_no
                           AND c.evnt_seq_no  = a.event_sr_no
WHERE  a.trn_ref_no IN (
           SELECT DISTINCT h.trn_ref_no
           FROM   actb_history h
           WHERE  h.module = 'RE'
             AND  h.ac_no IN ('475000100','475000102','475000106','475000150','475000160',
                              '476000100','476000102','476000106','476000150','476000160')
       )
ORDER  BY a.stmt_dt, a.trn_ref_no;


-- =====================================================================================
--  REQUÊTE 3 — SELL-BUY-BACK : ÉCRITURES COMPLÈTES  [PRIORITÉ 1]
-- =====================================================================================
--  Objectif : instruire le §11.5. 215 opérations de Sell-Buy-Back (896 Md XAF réglés)
--  sont comptabilisées comme des cessions et acquisitions fermes de titres. Il faut
--  vérifier qu'aucune dette n'est enregistrée au passif en regard.
--  On cible par le commentaire libre saisi par la salle des marchés.
--  Volume attendu : ~3 000 à 6 000 lignes. Fichier : sbb_complet.csv

SELECT
    c.addl_text description, a.trn_ref_no, a.ac_no, a.ac_ccy, a.fcy_amount,
    a.lcy_amount, a.trn_dt, a.drcr_ind, a.user_id, a.auth_id, a.amount_tag,
    a.stmt_dt, b.ac_natural_gl, a.product, b.ac_gl_desc, a.module, a.external_ref_no
FROM   actb_history a
LEFT JOIN sttb_account b    ON a.ac_no = b.ac_gl_no
LEFT JOIN cstb_addl_text c  ON c.reference_no = a.trn_ref_no
                           AND c.evnt_seq_no  = a.event_sr_no
WHERE  a.trn_ref_no IN (
           SELECT DISTINCT t.reference_no
           FROM   cstb_addl_text t
           WHERE  UPPER(t.addl_text) LIKE '%SBB%'
              OR  UPPER(t.addl_text) LIKE '%SELL%BUY%BACK%'
              OR  UPPER(t.addl_text) LIKE '%BUY%SELL%BACK%'
       )
ORDER  BY a.stmt_dt, a.trn_ref_no;


-- =====================================================================================
--  REQUÊTE 4 — TROISIÈME JAMBE DE L'ÉCRITURE DE CORRECTION  [PRIORITÉ 2 — 3 lignes]
-- =====================================================================================
--  Objectif : instruire le §12.5. L'écriture de correction du 31/07/2025 présente un
--  écart de 1 994 516 XAF entre ses deux jambes connues :
--     D 511800100  1 205 231 891   /   C 099ACO00001  1 207 226 407
--  Une troisième jambe existe. Même chose pour l'écriture d'apurement du 16/06/2025.

SELECT
    c.addl_text description, a.trn_ref_no, a.ac_no, a.ac_ccy, a.fcy_amount,
    a.lcy_amount, a.trn_dt, a.drcr_ind, a.user_id, a.auth_id, a.amount_tag,
    a.stmt_dt, b.ac_natural_gl, a.product, b.ac_gl_desc, a.module, a.external_ref_no
FROM   actb_history a
LEFT JOIN sttb_account b    ON a.ac_no = b.ac_gl_no
LEFT JOIN cstb_addl_text c  ON c.reference_no = a.trn_ref_no
                           AND c.evnt_seq_no  = a.event_sr_no
WHERE  a.trn_ref_no IN ('099000b252120001','099001b251670001')
ORDER  BY a.stmt_dt, a.ac_no;


-- =====================================================================================
--  REQUÊTE 5 — LES 41 COMPTES GÉNÉRAUX DE LA TRÉSORERIE, TOUS MODULES  [PRIORITÉ 2]
-- =====================================================================================
--  Objectif : appliquer la règle de méthode retenue au §12.7 — un constat sur le solde
--  ou le comportement d'un compte doit reposer sur une extraction tous modules
--  confondus. Les extractions précédentes étaient filtrées par module ou par compte,
--  ce qui a produit un faux constat sur le compte 511800100.
--  Volume attendu : ~350 000 à 450 000 lignes → À DÉCOUPER en parts de 60 000 lignes.
--  Fichier : comptes_tresorerie_part_N.csv
--
--  NOTE : si le volume est trop lourd, exécuter par blocs en décommentant les
--  sous-ensembles A à F ci-dessous, un par un.

SELECT
    c.addl_text description, a.trn_ref_no, a.ac_no, a.ac_ccy, a.fcy_amount,
    a.lcy_amount, a.trn_dt, a.drcr_ind, a.user_id, a.auth_id, a.amount_tag,
    a.stmt_dt, b.ac_natural_gl, a.product, b.ac_gl_desc, a.module, a.external_ref_no
FROM   actb_history a
LEFT JOIN sttb_account b    ON a.ac_no = b.ac_gl_no
LEFT JOIN cstb_addl_text c  ON c.reference_no = a.trn_ref_no
                           AND c.evnt_seq_no  = a.event_sr_no
WHERE  a.ac_no IN (
    -- A. PORTEFEUILLE TITRES ------------------------------------------------------
    '511210100',  -- BONS DE TRESOR (BTA) - PLACEMENT
    '511410100',  -- OBLIGATIONS DU TRESOR ASSIMILABLES PLACEMENT
    '512200100',  -- BONS DE TRESOR - TRANSACTION
    '512410100',  -- OBLIGATIONS DU TRESOR ASSIMILABLES TRANSACTIONS
    '511800100',  -- CREANCES RATTACHEES - PLACEMENT            [déjà obtenu]
    '512800100',  -- CREANCES RATTACHEES - TRANSACTION
    '591400100',  -- PROV DEPRECIATION DES OBLIGATIONS ET BONS ASSIMILES
    -- B. COMPTES DE RÉGULARISATION ------------------------------------------------
    '472200106',  -- PRODUITS PERCU D AVANCE SUR BON DE TRESOR
    '472200108',  -- AUTRES PRODUITS COMPTABILISES D AVANCE
    -- C. RÉSULTAT SUR TITRES -------------------------------------------------------
    '733200100',  -- REVENUS DE BONS DU TRESOR
    '733400100',  -- REVENUS D OBLIGATIONS ET BONS ASSIM
    '734200100',  -- REVENUS DE BONS DU TRESOR      (2e jeu — règle à comprendre)
    '734400100',  -- REV D OBLIGATIONS ET BONS ASSIMILES (2e jeu)
    '601100100',  -- INT. SUR OPS MARCHE MONETAIRE - OPS INTERBANCAIRES
    '725000100',  -- COMM GEST PORTF TITRE CPTE DE TIERS
    -- D. REFINANCEMENT BEAC (PENSIONS LIVRÉES) ------------------------------------
    '552400100',  -- EMPRUNT AU JR LE JR BQ NON ASSOC      [solde d'ouverture à établir]
    '559000101',  -- DETTES RATTACHEES PRET EMPRUNT AU JR LE JR - NON ASS
    '952100100',  -- TITRES D INVESTISSEMENT AFFECTES EN GARANTIE OPS MM  (hors bilan)
    '995000100',  -- CPTE GL OPS SUR TITRES AFFECT EN GTIES OPS MM        (hors bilan)
    -- E. CHANGE --------------------------------------------------------------------
    '475000100','475000102','475000106','475000150','475000160',  -- positions de change
    '476000100','476000102','476000106','476000150','476000160',  -- contre-valeurs
    '971200100',  -- DEV ACHETES CTANT NON ENCORE RECU        (hors bilan)
    '971400100',  -- DEV VENDUES CTANT NON ENCORE LIVRES      (hors bilan)
    '972400100',  -- DEVISE VENDU A TERM NON ENC LIVRES       (hors bilan)
    '979000100',  -- COMPTE D AJUSTEMENT DEVISES HORS BILAN   (hors bilan)
    '625000105',  -- COMMISSIONS PAYES SUR ACHAT DE DEVISE
    '727000102',  -- REFACT COMMISSIONS REFINANCEMENT BEAC
    '729000125',  -- COMMISSIONS DE SERVICE HORS CEMAC
    -- F. COMPTES DE LIAISON ET HORS BILAN CLIENTÈLE -------------------------------
    '467000186',  -- CALYPSO BRIDGE ACCOUNT
    '467000188',  -- CALYPSO BRIDGE ACCOUNT MONEY MARKET
    '467000243',  -- CALYPSO MIRROR TRADE BRIDGE ACCOUNT
    -- '452600001' COMPTE INTER BRANCHES : ECARTE a la demande de la banque
    --             (compte de routage inter-agences, sans portee economique ;
    --              les deux jambes se compensent systematiquement)
    '938000100',  -- VAL GEREES POUR COMPTE DE LA CLIENTELE
    '998000100'   -- VALEURS GEREES POUR COMPTE DE TIERS
)
ORDER  BY a.ac_no, a.stmt_dt;


-- =====================================================================================
--  REQUÊTE 6 — VARIANTE AVEC LA PÉRIODE COURANTE
-- =====================================================================================
--  ACTB_HISTORY ne contient pas toujours les écritures de la période en cours.
--  Si vous constatez que les derniers jours manquent, utiliser cette forme :

/*
SELECT ... (mêmes colonnes)
FROM (
      SELECT trn_ref_no, ac_no, ac_ccy, fcy_amount, lcy_amount, trn_dt, drcr_ind,
             user_id, auth_id, amount_tag, stmt_dt, product, module, external_ref_no,
             event_sr_no
      FROM   actb_history
      UNION ALL
      SELECT trn_ref_no, ac_no, ac_ccy, fcy_amount, lcy_amount, trn_dt, drcr_ind,
             user_id, auth_id, amount_tag, stmt_dt, product, module, external_ref_no,
             event_sr_no
      FROM   actb_daily_log
     ) a
LEFT JOIN sttb_account b   ON a.ac_no = b.ac_gl_no
LEFT JOIN cstb_addl_text c ON c.reference_no = a.trn_ref_no
                          AND c.evnt_seq_no  = a.event_sr_no
WHERE  ...
*/


-- =====================================================================================
--  REQUÊTE 7 — SOLDES AUX DATES D'ARRÊTÉ  [PRIORITÉ 1 — indispensable]
-- =====================================================================================
--  Objectif : les extractions ne contiennent que des MOUVEMENTS, jamais de solde
--  d'ouverture. C'est la limite principale de tous les travaux menés jusqu'ici :
--  aucun encours n'est vérifiable sans ancrage sur une balance.
--  Démonstration : le cumul des mouvements du compte 552400100 part à
--  −5 000 000 000 XAF dès sa première écriture, ce qui est impossible pour un compte
--  de passif — il existe donc un solde d'ouverture non fourni.
--
--  Dates demandées : 31/12/2023, 31/12/2024, 30/06/2025, 31/12/2025, 30/06/2026.
--  Le 30/06/2025 est particulièrement important : c'est l'arrêté traversé par
--  l'anomalie du §12.5 (compte d'actif en solde créditeur de 1 205 231 891 XAF).

SELECT gl_code, ac_ccy, fin_cycle, period_code,
       cr_bal, dr_bal, cr_mov, dr_mov, cr_bal_lcy, dr_bal_lcy
FROM   gltb_gl_bal
WHERE  gl_code IN ( /* même liste que la requête 5 */ )
ORDER  BY gl_code, fin_cycle, period_code;

--  Si la structure diffère, une simple balance générale (code, libellé, solde
--  débiteur, solde créditeur) aux cinq dates ci-dessus suffit — y compris exportée
--  depuis l'état réglementaire.
