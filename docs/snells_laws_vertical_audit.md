# Audit de la verticale Lois de Snell-Descartes — A71a

La verticale dispose maintenant du rapport Markdown A71d, exclusivement construit depuis A71c. Il retrouve la synthèse et les priorités utiles d'A61 sans réintroduire ses heuristiques comme autorité scientifique.

## 1. Périmètre et méthode

Cet audit prépare une verticale reproductible pour un seul TP. Il compare le
support historique, le support amélioré, quatre copies réelles issues du
support historique, un cas artificiel contrôlé et les capacités de TPStudio.
Il ne corrige aucune copie et ne constitue pas une évaluation des étudiants.

Les notebooks ont été lus comme données avec `nbformat`, sans exécuter leurs
cellules. Les statistiques, marqueurs et écarts de structure ont été reproduits
avec `scripts/audit_snells_laws_notebooks.py`. Les sorties déjà enregistrées
ont seulement été comptées et typées. Elles peuvent être anciennes ou ne pas
correspondre exactement à l'état courant du code.

Les copies réelles sont des données personnelles. Elles sont désignées
uniquement par `COPY_A`, `COPY_B`, `COPY_C` et `COPY_D`. La correspondance avec
les fichiers locaux n'est pas versionnée. Aucun contenu complet, nom ou
adresse électronique n'est reproduit ici.

## 2. Fichiers analysés

Les fichiers privés ont été trouvés sous le dossier historique de la séance et
son dossier de résultats. Les chemins absolus et la table d'identité restent
hors de Git.

| Rôle | Désignation versionnée | Disponibilité | Usage |
|---|---|---:|---|
| ancien énoncé | `Lois-de-Snell-Descartes.ipynb` | oui | référence des copies réelles |
| énoncé amélioré | `Lois-de-Snell-Descartes-ameliore.ipynb` | oui | référence proposée pour le MVP |
| copies réelles | `COPY_A` à `COPY_D` | 4/4 | audit anonymisé et validation future |
| cas contrôlé amélioré | fausse copie améliorée | oui | anomalies intentionnelles |
| correction contrôlée | notebook et rapport Markdown | oui | preuve historique de rendu |
| rapport historique | rapport texte de comparaison | oui | preuve de diagnostic technique |
| suivi historique | bilan et CSV de suivi/anomalies/non-rendus | oui | preuve de traitement par lot |

Une autre version homonyme de 18 cellules existe ailleurs dans les documents,
mais elle ne correspond ni au support historique de cette séance ni aux quatre
copies retenues. Elle a donc été exclue de la comparaison principale, mais sa
fausse copie a été inspectée comme preuve historique. Les variantes suffixées
indiquées dans la demande n'ont pas été nécessaires.

### Limites de l'audit

- aucune cellule étudiante n'a été exécutée ;
- aucune sortie n'a été tenue pour une vérité fraîche ;
- l'absence de cellule Markdown de réponse dans l'ancien support interdit une
  comparaison textuelle complète avec le support amélioré ;
- l'alignement structurel repose sur le type et le contenu exact des cellules,
  pas sur une compréhension sémantique ;
- la pertinence scientifique libre des explications n'est pas évaluée ;
- les anciens artefacts prouvent un comportement historique, pas à eux seuls
  un contrat compatible avec A66–A70h.

## 3. Inspection sûre des notebooks

| Notebook | nbformat | Cellules | Markdown | Code | Raw | Outputs | Erreurs enregistrées | Code non exécuté | Pièces jointes | Kernel |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| ancien | 4.4 | 16 | 4 | 12 | 0 | 0 | 0 | 12 | 0 | `conda-base-py` |
| amélioré | 4.4 | 23 | 11 | 12 | 0 | 0 | 0 | 12 | 0 | `conda-base-py` |
| COPY_A | 4.2 | 17 | 4 | 13 | 0 | 7 | 0 | 1 vide | 0 | `python3` |
| COPY_B | 4.4 | 15 | 4 | 11 | 0 | 8 | 0 | 0 | 0 | `python3` |
| COPY_C | 4.2 | 16 | 4 | 12 | 0 | 7 | 0 | 1 vide | 0 | `python3` |
| COPY_D | 4.4 | 16 | 4 | 12 | 0 | 8 | 0 | 1 vide | 0 | `python3` |
| cas contrôlé amélioré | 4.4 | 23 | 11 | 12 | 0 | 8 | 2 | 0 | 0 | `conda-base-py` |
| cas contrôlé historique | 4.5 | 18 | 12 | 6 | 0 | 3 | 1 | 3 | 0 | `conda-base-py` |
| copie corrigée contrôlée | 4.4 | 29 | 17 | 12 | 0 | 8 | 2 | 0 | 0 | `conda-base-py` |

Les métadonnées des deux énoncés et des copies sont limitées principalement à
Colab, au kernel et à la langue ; l'amélioré ajoute une métadonnée `tpstudio`.
Aucune pièce jointe intégrée n'est présente. Les références externes observées
sont les deux documents pédagogiques liés par HTTP(S), sans fichier de données
local requis par ces notebooks.

L'ancien support contient des marqueurs `?` dans huit cellules de code.
L'amélioré en contient dans neuf cellules de code. Le caractère interrogatif
d'une consigne Markdown de la grille est volontairement ignoré par cet audit.
L'amélioré ajoute trois marqueurs `Réponse`, des titres `Résultat`, une
zone `Protocole`, une comparaison et une conclusion explicites. Les quatre
copies réelles n'ont plus de marqueur de code à compléter. Les cellules de
code non exécutées de COPY_A, COPY_C et COPY_D sont des cellules vides finales,
donc pas des calculs attendus manquants. Deux sorties texte de COPY_B et COPY_D
contiennent des avertissements Python, mais aucun output Jupyter de type
`error`.

## 4. Identité des copies

Les quatre notebooks réels ne contiennent ni cellule d'identité reconnue ni
métadonnée d'identité. L'identité n'est donc disponible que dans le nom local
du fichier.

| Copie | Indice du nom de fichier | Identité interne | Ambiguïté pour un traitement par lot |
|---|---|---|---|
| COPY_A | deux segments de personne possibles | absente | ordre prénom/nom et séparation du binôme ambigus |
| COPY_B | deux personnes probables, ponctuation irrégulière | absente | découpage du binôme ambigu |
| COPY_C | une personne probable | absente | prénom/nom composé à confirmer humainement |
| COPY_D | deux personnes probables, segments répétés | absente | dédoublonnage et ordre des noms ambigus |

Le parseur historique de nom de fichier retourne une paire non vide pour les
quatre fichiers, mais cela ne prouve ni le nombre de personnes ni le bon
découpage. Pour le futur lot, l'identité interne structurée doit être
prioritaire ; le nom de fichier reste une proposition à valider humainement.
Le mécanisme actuel n'est pas modifié par A71a.

## 5. Ancien support et énoncé amélioré

### Structure générale

L'ancien support alterne trois titres Markdown et douze cellules de code. Il
guide les calculs par des commentaires et des marqueurs `?`, mais ne réserve
aucune zone de rédaction. Les conclusions de cohérence sont imprimées par des
branches de code qui contiennent simultanément les deux formulations possibles.

L'amélioré conserve les douze cellules de code et les trois méthodes. Il passe
de 16 à 23 cellules en ajoutant sept cellules Markdown : identification,
protocole, résultat de la première méthode, résultat de la seconde méthode,
comparaison globale, conclusion/bilan et grille de compétences. Les cellules
de résultat, comparaison et conclusion nomment explicitement la production et
isolent une zone `Réponse` lorsque nécessaire.

| Axe | Ancien | Amélioré | Effet sur la corrigeabilité |
|---|---|---|---|
| sections scientifiques | trois méthodes | mêmes trois méthodes | continuité des calculs |
| identité | absente | zone dédiée | association de lot plus fiable après saisie |
| protocole | implicite | zone Markdown dédiée | binding textuel possible |
| résultats rédigés | absents | deux zones dédiées | quantités textuelles observables |
| comparaison | code seulement | code + synthèse Markdown | A70a–A70h raccordables |
| conclusion | implicite dans les prints | zone dédiée | conclusion littérale déclarable |
| justification | non demandée explicitement | limites demandées dans le bilan | A70g raccordable |
| grille | absente | présente | hors MVP de notation |
| UUID de cellule | absent | absent | préférer tags futurs ou marqueurs exacts |

### Productions demandées et zones de réponse

Les deux versions demandent réellement : mesures angulaires, incertitudes,
propagation Monte-Carlo, trois estimations de l'indice, série de couples
d'angles, graphe de `sin(i1)` en fonction de `sin(i2)`, régression linéaire,
pente et ordonnée à l'origine, deux écarts normalisés et conclusions de
cohérence. Les tableaux sont représentés par des tableaux NumPy, pas par une
production tabulaire indépendante.

L'amélioré rend en plus explicites le protocole, les résultats rédigés avec
incertitude, la comparaison des méthodes, la conclusion globale et les limites
de méthode. Il ne demande pas une démonstration algébrique complète ni une
analyse libre de toutes les causes expérimentales.

Les cellules de code restent associables par marqueur de source, mais plusieurs
marqueurs sont génériques et répétés. Les cellules Markdown améliorées sont
nettement plus stables pour les bindings. L'absence d'UUID et de tags impose à
A71b des sélecteurs littéraux soigneusement choisis et des erreurs d'ambiguïté
explicites.

## 6. Inventaire des productions du support amélioré

Les identifiants ci-dessous sont provisoires et destinés à la configuration
Python A71b. Les indices sont ceux du support amélioré audité ; aucun UUID
n'est disponible.

| ID | Section/cellule | Type | Consigne ou production | Données/unité | Référence | Type TPStudio envisagé | Couverture | Priorité |
|---|---|---|---|---|---|---|---|---|
| `protocol_limit` | première méthode, 4 | Markdown | décrire le protocole | texte | consigne seulement | JUSTIFICATION | configuration déclarative ; pertinence manquante | P2 |
| `limit_measurement` | première méthode, 5 | code | angle limite et incertitude | `il`, `uil`, degré puis radian | corrigé/code | QUANTITY ×2 | binding/quantités disponibles ; observation du code à adapter | P1 |
| `index_limit` | première méthode, 6–7 | code + Markdown | indice et incertitude par Monte-Carlo, résultat rédigé | `n`, sans unité | formule + corrigé | QUANTITY | A68–A69 configurables sur texte ; code/output à adapter | P1 |
| `pair_measurements` | seconde méthode, 9 | code | couple d'angles et incertitudes | `i1`, `ui1`, `i2`, `ui2`, radian | corrigé/code | QUANTITY | observation du code à adapter | P2 |
| `index_pair` | seconde méthode, 10–11, 13 | code + Markdown | indice et incertitude par un couple | `n`, sans unité | formule + corrigé | QUANTITY | A68–A69 configurables sur réponse | P1 |
| `comparison_limit_pair` | seconde méthode, 12–13 | code + Markdown | comparer deux indices avec En et conclure | `n0`, `un0`, `En` | seuil dans le code | COMPARISON | A70a–A70h configurables sur Markdown | P1 |
| `angle_series` | troisième méthode, 15 | code | série de couples angulaires | tableaux `i1`, `i2`, degré/radian | corrigé/code | QUANTITY, données source | extraction de tableaux absente | P2 |
| `snell_plot` | troisième méthode, 16 | code | tracer `sin(i1)` en fonction de `sin(i2)` | axes sans unité | code modèle | PLOT | ancien comparateur disponible, raccord moderne manquant | P1 |
| `snell_regression` | troisième méthode, 16–17 | code | régression, pente, intercept, équation | `a`, `b` | relation attendue | RELATION + QUANTITY | relation littérale disponible ; résultat de code à adapter | P1 |
| `index_series` | troisième méthode, 18 | code | indices par couple, moyenne et incertitude | tableau `n`, sans unité | formule + corrigé | QUANTITY | scalaire final configurable ; tableau hors MVP | P1 |
| `comparison_pair_series` | troisième méthode, 19–20 | code + Markdown | second En et synthèse des méthodes | `n0`, `un0`, `En` | seuil dans le code | COMPARISON | A70a–A70h configurables sur Markdown | P1 |
| `final_conclusion` | bilan, 21 | Markdown | résultats principaux et limites | texte | attentes professeur | INTERPRETATION + JUSTIFICATION | A70e–A70h configurables littéralement | P1 |

Le corrigé fournit des formules et une structure de code. Il ne fournit pas une
valeur numérique fixe universelle : les indices dépendent des mesures de la
copie. Les comparaisons doivent donc reposer sur les productions de la copie,
pas sur une constante globale inventée.

## 7. Analyse anonymisée des copies réelles

Les quatre copies sont issues de l'ancien support : titres et ordre général
coïncident, aucune ne possède les zones rédactionnelles ajoutées ensuite.
Elles ne doivent donc pas être comparées à l'amélioré comme si elles avaient
omis volontairement ces zones.

| Copie | Structure par rapport à l'ancien | Code et sorties conservées | Graphe | Réponses spontanées | Appréciation structurelle |
|---|---|---|---|---|---|
| COPY_A | une cellule de code vide ajoutée en fin ; dix cellules remplies/modifiées | chaîne principale exécutée, 7 outputs, aucune erreur enregistrée | présent | aucune zone Markdown ajoutée | proche du modèle |
| COPY_B | une cellule de moins, calculs graphiques regroupés | tout code non vide exécuté, 8 outputs, avertissements texte | présent | aucune zone Markdown ajoutée | modérément modifiée |
| COPY_C | même cardinalité, cellule vide finale | chaîne principale exécutée, 7 outputs, aucune erreur enregistrée | présent | aucune zone Markdown ajoutée | proche du modèle |
| COPY_D | même cardinalité, cellule vide finale, formule finale modifiée | chaîne principale exécutée, 8 outputs, avertissements texte | présent | aucune zone Markdown ajoutée | proche du modèle avec cas scientifique intéressant |

Le comparateur historique de graphes juge les quatre graphes cohérents avec le
modèle pour les expressions et la régression. Le comparateur sémantique de code
ne signale rien sur ces quatre copies : le modèle historique contient des
placeholders qui rendent plusieurs cellules non analysables par l'AST. Cette
absence de signal ne vaut donc pas validation scientifique. De même, le niveau
historique de corrigeabilité est faible pour toutes les copies parce que
l'ancien support ne possède aucune zone `Réponse`.

## 8. Héritage A60/A61 et étapes voisines

Aucun tag `A60*` ou `A61*` n'est présent, mais les commits A60, A61a, A61b,
A61c-a et A61c-b existent. Le code associé est encore dans la branche courante.

| Capacité historique | Emplacement actuel | État et tests observés | Décision |
|---|---|---|---|
| inspection modèle/copie, code incomplet, cellules non exécutées, erreurs enregistrées | `student_inspection.py`, `copy_comparison.py` | présent ; 8 + 7 tests directs | réutiliser derrière un adaptateur structuré |
| exécution dans une copie temporaire et fallback kernel | `notebook_execution.py`, `correction_bundle.py` | présent ; tests d'exécution, erreurs partielles et kernels | réutiliser en option explicite, jamais pendant l'audit |
| sections Protocole/Objectifs/Problématique | `pedagogical_sections.py` | présent ; 10 tests directs + intégration | adapter aux bindings déclaratifs |
| réponses fragiles | `response_extraction.py`, `response_diagnostics.py` | présent, testé ; heuristiques lexicales historiques | ne pas rendre autoritaire ; remplacer par attentes A70 lorsque possible |
| graphe, axes, labels, variable de régression | `graph_comparison.py` | présent ; 4 tests directs et intégration feedback | adapter puis structurer ; le parseur reste limité à Matplotlib |
| écarts sémantiques de formules | `code_semantics.py` | présent ; 8 tests directs + intégration | réutiliser prudemment ; ajouter une référence syntaxiquement valide |
| cohérence numérique code/réponse/corrigé | `numerical_consistency.py` | présent ; 6 tests directs + intégration | remplacer comme autorité par A68–A70 ; réutiliser seulement les observations utiles |
| commentaires locaux et copie corrigée | `copy_feedback.py`, `correction_bundle.py` | présent ; 11 tests directs et intégration | adapter pour propositions validées humainement |
| rapport étudiant/professeur | `feedback_report.py`, `correction_bundle.py` | présent et démontré par artefacts | réécrire l'assemblage autour des objets structurés actuels |
| identité, suivi, anomalies, non-rendus, doublons | `gradebook_export.py`, `gradebook_*` | présent ; identité couverte par 25 tests directs, nombreux tests de lot | réutiliser ; renforcer le cas des binômes ambigus |

Les rapports historiques confirment concrètement la détection de marqueurs `?`
dans le code, des erreurs enregistrées, d'une réponse fragile et
d'axes/labels/régression inversés,
l'insertion de commentaires et la synthèse de séance. Ils restent des
artefacts privés et ne sont pas intégrés au dépôt. Les anciennes fonctions
écrivent parfois directement du texte ou modifient une copie de correction :
elles ne doivent pas contourner les objets immuables, catalogues explicites et
validation humaine de l'architecture actuelle.

## 9. Couverture A66–A70h

La classification suivante concerne l'usage dans cette verticale, pas la
qualité intrinsèque des modules.

| Brique | État | Motif/action Snell-Descartes |
|---|---|---|
| chargement JSON/nbformat sans exécution | READY | lecteurs présents ; normaliser l'entrée vers `NotebookNode` |
| sections et cellules | READY | cellules, titres et sources accessibles |
| bindings cellule–production | CONFIGURATION_NEEDED | marqueurs exacts à déclarer ; pas d'UUID dans l'énoncé |
| productions scientifiques et dépendances | CONFIGURATION_NEEDED | plan A68a à écrire pour les productions inventoriées |
| quantités textuelles | CONFIGURATION_NEEDED | symboles, unités et exigences à déclarer |
| quantités dans code ou outputs | ADAPTER_NEEDED | A69d consomme du texte résolu, pas une variable exécutée arbitrairement |
| relations littérales | CONFIGURATION_NEEDED | loi de Snell déjà démontrée dans l'exemple A66.5 |
| incertitudes | CONFIGURATION_NEEDED | structure et positivité disponibles, calcul non vérifié |
| graphes et régression | ADAPTER_NEEDED | ancien comparateur présent, aucun contrat moderne unifié |
| comparaison et En objectif | CONFIGURATION_NEEDED | A70a–A70c directement mobilisables après quantités |
| En écrit par l'étudiant | CONFIGURATION_NEEDED | A70d disponible sur une zone textuelle explicite |
| conclusion | CONFIGURATION_NEEDED | A70e–A70f disponibles avec phrases déclarées |
| justification structurelle | CONFIGURATION_NEEDED | A70g–A70h disponibles avec éléments déclarés |
| état d'exécution et placeholders | ADAPTER_NEEDED | ancien moteur présent, à raccorder au rapport structuré |
| orchestration de toutes les branches | MISSING | aucune façade Snell ne relie encore ces sets |
| rapport professeur unifié | MISSING | anciens rapports textuels à reconstruire depuis les objets actuels |
| insertion contrôlée de commentaires | ADAPTER_NEEDED | mécanisme ancien présent, validation/provenance à ajouter |
| notation automatique | OUT_OF_SCOPE_MVP | volontairement exclue |
| analyse scientifique libre | OUT_OF_SCOPE_MVP | aucune IA ni compréhension générale |

### Matrice de couverture des productions

| Production | A60/A61 | A66–A70h | Configuration | Manque fonctionnel | MVP |
|---|---|---|---|---|---:|
| protocole | section et réponse fragile | justification déclarative | phrases/éléments | pertinence détaillée | P2 |
| angle limite et incertitude | inspection du code | quantité/incertitude sur texte | symboles et binding | adaptateur code sûr | P1 |
| indice méthode 1 | cohérence numérique historique | quantité complète A68–A69 | attente `n` | source code/output | P1 |
| indice méthode 2 | idem | idem | attente `n` distincte | source code/output | P1 |
| comparaison 1–2 | heuristique numérique | A70a–A70h | seuils, phrases, justification | orchestration | P1 |
| série angulaire | comparaison de code | production générique seulement | binding | observation de tableau | après MVP |
| graphe | axes/labels/polyfit | `PLOT` déclarable sans évaluateur | modèle graphique | contrat moderne de graphe | P1 via adaptateur |
| pente/intercept | code sémantique | relation et quantité | expressions/symboles | lecture contrôlée du résultat | P1 |
| indice méthode 3 | cohérence numérique historique | quantité complète A68–A69 | attente `n` distincte | source code/output | P1 |
| comparaison finale | rapport historique | A70a–A70h | attentes complètes | orchestration | P1 |
| conclusion et limites | réponse fragile historique | interprétation/justification déclaratives | phrases/éléments/catalogues | aucune analyse libre | P1 |

En résumé, le moteur actuel couvre mieux les contrats scientifiques et la
traçabilité ; l'ancien moteur couvre mieux l'état technique, les graphes,
l'écriture de rapports et l'insertion. La verticale doit les raccorder par des
adaptateurs étroits, pas restaurer les heuristiques historiques comme source de
vérité scientifique.

## 10. Copies pilotes

- **Pilote principal — COPY_D.** Sa structure reste proche de l'ancien support,
  la chaîne numérique et le graphe sont présents, et une modification de
  formule produit un cas intéressant sans cumuler erreurs Jupyter, cellules
  déplacées et code incomplet. Elle est adaptée au raccord technique et
  quantitatif de l'ancien support.
- **Validation favorable — COPY_B.** Tout le code non vide est exécuté, le
  graphe et ses outputs sont présents, et aucune erreur Jupyter n'est
  enregistrée. La cellule regroupée vérifie que l'association ne doit pas
  dépendre strictement d'un indice.
- **Validation difficile — COPY_C.** La structure est lisible mais les valeurs
  des méthodes divergent assez pour exercer comparaisons, En et revue humaine,
  sans confondre difficulté scientifique et erreur d'exécution.
- **Validation structurelle supplémentaire — COPY_A.** La cellule vide ajoutée
  vérifie la tolérance aux ajouts non significatifs.
- **Cas contrôlé artificiel.** La fausse copie améliorée reste indispensable
  pour les placeholders, deux erreurs enregistrées, une réponse fragile et les
  axes/labels/régression volontairement inversés.

Comme les copies réelles sont antérieures aux zones rédactionnelles, le
parcours intégral conclusion–justification sera d'abord démontré sur le cas
contrôlé amélioré. Le pilote réel ne sera pas artificiellement déclaré en échec
pour des productions que son support ne demandait pas.

## 11. MVP A71

### Référence retenue

L'énoncé amélioré doit être la référence du MVP. Il conserve les calculs de
l'ancien support tout en nommant les zones de résultat, comparaison,
conclusion, justification et identité. C'est la seule version qui permet de
raccorder honnêtement A70d–A70h sans lire les deux branches contradictoires
d'un `if` comme une conclusion étudiante.

### Plus petit parcours de bout en bout démontrable

1. charger une copie sans modifier l'original ;
2. observer l'état d'exécution enregistré et les placeholders, sans exécuter ;
3. résoudre les bindings des deux résultats rédigés et de la comparaison ;
4. évaluer au moins deux indices avec incertitude ;
5. calculer une comparaison objective et conserver le En écrit ;
6. observer la conclusion et les éléments de justification déclarés ;
7. contrôler un graphe et sa régression via un adaptateur structuré ;
8. construire diagnostics et feedbacks à partir de catalogues explicites ;
9. générer un rapport professeur ;
10. soumettre les feedbacks proposés à validation humaine.

A71b écrit la configuration Python explicite de l'amélioré et la teste sur des
données synthétiques. A71c orchestre d'abord le cas contrôlé amélioré de bout en
bout, puis raccorde COPY_D aux productions réellement présentes dans l'ancien
support. COPY_B et COPY_C forment les validations favorable et difficile.

Sont inclus : état d'exécution enregistré, marqueurs `?` dans le code, deux
valeurs d'indice avec incertitudes, graphe/régression, comparaison, En,
conclusion, justification et
feedbacks configurables. Le protocole, la série complète de mesures et la
troisième estimation peuvent suivre en P2 si le noyau P1 reste trop large.

Sont exclus : notation, correction scientifique libre, IA générale, tous les
TP, interface graphique complète, PDF parfait, synchronisation cloud, Ninox et
traitement non supervisé de trente copies.

## 12. Spécification conceptuelle du projet professeur

Le format persistant définitif n'est pas choisi. En particulier, A71a ne décide
ni YAML ni JSON.

### Données configurées par le professeur

- identité, version et titre du projet ;
- référence de l'énoncé et éventuellement du corrigé ;
- plan des productions et dépendances ;
- bindings par UUID, tag ou marqueur exact ;
- attentes quantitatives, symboles, unités et exigences d'incertitude ;
- relations acceptées explicitement ;
- comparaisons, seuils et contexte pédagogique ;
- labels acceptés pour le En étudiant ;
- phrases d'interprétation et éléments de justification ;
- catalogues de feedback étudiant/professeur ;
- options d'observation des outputs et d'exécution contrôlée ;
- options de rapport, validation et export.

### Données dérivées automatiquement

- résolutions de bindings et ambiguïtés ;
- observations et offsets ;
- évaluations A68–A70 ;
- diagnostics et propositions de feedback ;
- statistiques techniques et empreintes de cellules ;
- provenance et version de la configuration.

### Données propres à une copie

- chemin privé ou identifiant opaque ;
- identité proposée et sa provenance ;
- texte/cellules/outputs observés sans duplication publique ;
- état d'exécution enregistré ;
- résultats structurés et anomalies ;
- historique local des exports.

### Décisions humaines

- confirmation de l'identité et du binôme ;
- résolution d'un binding ambigu ;
- acceptation, modification ou rejet de chaque feedback ;
- autorisation éventuelle d'exécution ;
- validation du rapport et de l'export final.

Les chemins privés, notebooks étudiants, noms, adresses, table de
correspondance `COPY_*`, listes officielles et rapports individualisés ne
doivent jamais entrer dans Git. `data_private/` est déjà ignoré ; les fichiers
ont été laissés à leur emplacement et aucune nouvelle règle globale n'est
nécessaire.

## 13. Plan révisable A71b–A72

- **A71b** : configuration Python explicite de l'énoncé amélioré, bindings et
  catalogues Snell-Descartes ;
- **A71c** : orchestration d'une copie, d'abord contrôlée puis pilote réelle
  selon la compatibilité du support ;
- **A71d** : rapport professeur structuré et traçable ;
- **A71e** : proposition puis insertion contrôlée de commentaires après
  validation ;
- **A71f** : export notebook et HTML ;
- **A71g** : petit lot, identités confirmées et synthèse ;
- **A72** : prototype d'interface locale.

Ce séquencement doit être révisé si A71b montre que la lecture des résultats de
code, le graphe ou les bindings sans UUID exigent un contrat plus large que
prévu.

## 14. Risques et décisions ouvertes

1. **Deux générations de support.** Il faut versionner la configuration et ne
   jamais appliquer silencieusement celle de l'amélioré à une ancienne copie.
2. **Absence d'UUID et de tags.** Les marqueurs littéraux peuvent être dupliqués
   ou modifiés ; l'ambiguïté doit être bloquante, jamais arbitrée par indice.
3. **Code et outputs.** L'architecture moderne observe surtout du texte. Une
   couche sûre doit distinguer source, valeur calculée et output enregistré.
4. **Graphes.** L'ancien parseur apporte de la valeur, mais ne couvre ni tous
   les appels Matplotlib ni une figure produite indirectement.
5. **Modèle avec placeholders.** L'analyse AST historique ignore des cellules
   non syntaxiques ; A71b doit utiliser une référence exécutable distincte ou
   des attentes déclaratives.
6. **Identités de binômes.** L'inférence depuis le nom du fichier reste une
   suggestion ; confirmation humaine obligatoire.
7. **COMPLETE n'est pas correct.** La complétude A70g ne valide ni seuil,
   calcul, cause, graphe, relation ni qualité scientifique libre.
8. **Confidentialité.** Les résultats versionnés doivent rester agrégés et
   anonymisés ; les artefacts individuels demeurent locaux.

La décision principale pour A71b est donc : configurer l'énoncé amélioré, ne
réutiliser de l'ancien moteur que ses observations techniques utiles, et
conserver une revue humaine obligatoire à chaque sortie destinée à l'étudiant.

## Matérialisation A71b

La décision est désormais matérialisée par la
[configuration professeur Python](snells_laws_teacher_configuration.md).
Elle déclare 19 productions et 19 bindings littéraux validés contre l'énoncé
amélioré, sans chemin privé ni lecture de notebook à l'import. La seconde
comparaison est nommée `compare_geometric_regression`, conformément à la
« valeur précédente » réellement utilisée par le troisième bloc. A71c devra
encore raccorder les observations de code et de graphe et conserver séparément
la conclusion finale.

A71c matérialise ce raccordement par une orchestration en lecture seule. Les
adaptateurs AST et graphe restent prudents, les outputs enregistrés conservent
leur provenance et la revue humaine demeure obligatoire. Le rapport professeur
détaillé reste le jalon A71d.
