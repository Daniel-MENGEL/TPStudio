# Configuration professeur Lois de Snell-Descartes — A71b

## Rôle

A71b matérialise la décision de l'audit A71a sous la forme d'une configuration
Python explicite, immuable et validée. `snells_laws_teacher_project()` construit
les références, productions, bindings et attentes du support amélioré. La
fabrique ne lit aucun fichier et ne contient ni copie, ni résultat étudiant,
ni chemin local.

Une configuration professeur décrit ce qui est attendu. Les cellules, valeurs,
sorties, identités et décisions de validation d'une copie appartiendront à
l'orchestration A71c ; elles ne sont jamais stockées dans ce projet versionné.

## Identité et références

L'identité est `snells-laws-mvp`, intitulée « Lois de Snell-Descartes », pour la
physique en CPGE, version `A71b`, langue française. Elle n'indique ni
professeur, établissement, classe nominative ou année privée.

Trois simples noms de fichiers sont déclarés, sans chemin ni lecture
automatique :

- l'énoncé amélioré ;
- le corrigé de référence disponible ;
- la copie artificielle améliorée contrôlée.

Aucune copie réelle `COPY_A` à `COPY_D` ne figure dans la configuration.
L'orchestrateur ou une future interface résoudra physiquement ces références.
Aucun fingerprint n'est déclaré tant que la politique de version des notebooks
n'est pas arrêtée.

## Productions et associations

Le plan contient 19 productions : trois angles, trois indices, une pente, cinq
relations, un graphe, deux commentaires de résultat, deux comparaisons, une
conclusion et une justification de limites. Les identifiants décrivent le sens
scientifique, jamais un numéro de cellule.

| Production | Type | Association | Attentes | Moteur |
|---|---|---|---|---|
| `critical_angle` | QUANTITY | marqueur de mesure `il` | degré, incertitude | A68–A69 après adaptateur code |
| `incidence_angle` / `refraction_angle` | QUANTITY | marqueurs `i1` / `i2` | degré, incertitudes | A68–A69 après adaptateur code |
| `direct_index` | QUANTITY | titre du premier résultat | indice sans dimension, incertitude | A68–A69 |
| `geometric_index` | QUANTITY | titre du second résultat | indice sans dimension, incertitude | A68–A69 |
| `regression_graph` | PLOT | commentaire de vérification graphique | x=`sin(i2)`, y=`sin(i1)`, régression | adaptateur de graphe futur |
| `regression_slope` | QUANTITY | cellule d'équation de droite | pente sans dimension | A68–A69 après adaptateur code |
| `regression_index` | QUANTITY | marqueur de méthode statistique | indice sans dimension, incertitude | A68–A69 après adaptateur code |
| `compare_direct_geometric` | COMPARISON | réponse de la seconde méthode | En, conclusion, justification | A70a–A70h |
| `compare_geometric_regression` | COMPARISON | réponse de comparaison globale | En, conclusion, justification | A70a–A70h |
| `final_conclusion` | INTERPRETATION | titre Conclusion/bilan | synthèse finale | orchestration future |
| `method_limitations` | JUSTIFICATION | même section finale | limites de méthode | orchestration future |

Les associations utilisent toutes `SOURCE_MARKER`, car le notebook réel ne
possède ni UUID ni tags stables. Les indices de cellules ne sont jamais des
clés. Une cellule déplacée reste donc associable. Une absence produit
`CELL_NOT_FOUND` et plusieurs cellules correspondantes produisent
`CELL_AMBIGUOUS` ; aucune première occurrence n'est choisie arbitrairement.

La proposition A71a `compare_direct_regression` devient
`compare_geometric_regression` : le second bloc de code compare sa valeur à la
« valeur précédente », qui est la détermination géométrique. Cette divergence
est scientifique et indépendante des indices de cellules.

## Grandeurs, unités et incertitudes

Les angles d'entrée sont déclarés en degrés, avec `deg` comme variante. Le code
effectue ensuite explicitement la conversion en radians ; la configuration ne
convertit rien silencieusement. Les sinus, indices, pente et En sont sans
dimension.

Les incertitudes sont obligatoires pour les angles et les trois indices utilisés
dans les comparaisons. Les politiques de qualité contrôlent présentation,
positivité et chiffres significatifs. Elles restent distinctes :

- de l'incertitude scientifique annoncée par l'étudiant ;
- de la tolérance de reconnaissance textuelle ;
- de la tolérance absolue `Decimal("0.05")` appliquée au En étudiant.

Cette dernière correspond à une lecture d'un En arrondi au centième. Elle ne
masque pas une erreur de calcul et ne constitue pas une tolérance expérimentale.

## Relations, graphe et régression

Les cinq relations déclarées sont la loi de Snell-Descartes, l'indice par angle
limite, l'indice par un couple d'angles, la relation pente–indice et la formule
de l'écart normalisé. Seules les expressions et variantes explicitement
déclarées sont reconnues.

Le graphe place `sin(i2)` en abscisse et `sin(i1)` en ordonnée. La régression
linéaire est requise et sa pente `a` représente l'indice `n`. Des labels LaTeX
et textuels sont acceptés. Une légende est attendue comme dans le support ; ni
couleur, ni style, ni titre exact ne sont imposés. `GraphExpectationSet` vit
dans le paquet `projects` : aucun contrat A66–A70h n'a été modifié.

## Comparaisons, En et interprétation

Deux comparaisons sont configurées : angle limite/couple, puis couple/série.
Elles conservent exactement les seuils A70b : 2 et 4. La première utilise le
contexte `OPEN`, la seconde `INCOHERENCE_POSSIBLE`. Le contexte
`METHOD_LIMITATION_EXPECTED` n'est pas appliqué : le bilan demande une limite,
mais ne prédit pas que la comparaison sera fortement incohérente.

Les labels `E_n` et `En` sont acceptés littéralement. Six formulations
d'interprétation réalistes couvrent cohérence, incohérence, incohérence forte et
limitation de méthode. Elles pourront être enrichies explicitement dans une
future interface, sans compréhension libre du français.

## Justifications et limites

Pour chaque comparaison, la valeur de En, le seuil et la classification sont
déclarés `REQUIRED`; la référence aux incertitudes est `OPTIONAL`. Pour la
seconde comparaison, limitation de méthode, biais expérimental et incertitude
de lecture sont facultatifs. Aucun groupe `ONE_OF_GROUP` n'est imposé dans la
cellule de comparaison, car l'énoncé demande les limites dans la cellule finale
séparée.

Les formulations littérales de seuil couvrent les trois domaines A70b :
`En < 2`, `En >= 2` et `En >= 4`. Leur détection vérifie uniquement la présence
structurelle d'un seuil déclaré ; elle ne garantit pas que le seuil cité soit
scientifiquement cohérent avec la valeur de En écrite par l'étudiant.

Cette séparation révèle une limite pour A71c : A70g consomme aujourd'hui une
source unique par comparaison. L'orchestrateur devra conserver distinctement
la justification de comparaison et la production finale `method_limitations`,
sans concaténation implicite et sans rendre obligatoire une preuve dans la
mauvaise cellule.

## Catalogues explicites

Quatre catalogues français existants sont construits et stockés dans un ordre
déterministe : quantités, comparaisons, interprétations et justifications. Il
n'existe ni catalogue implicite, ni catalogue global fusionné, ni catalogue de
graphe inventé. Aucun diagnostic ou feedback n'est produit par A71b.

## Validation contre l'énoncé

`scripts/validate_snells_laws_project.py` reçoit explicitement le chemin de
l'énoncé et, facultativement, celui du corrigé. Il charge les notebooks comme
données avec `nbformat`, construit la configuration et résout les bindings en
lecture seule. Il ne lit aucune copie étudiante, n'exécute aucune cellule et ne
modifie aucun fichier.

Sur l'énoncé amélioré audité : 23 cellules, 19 bindings résolus, aucun binding
absent, aucun binding ambigu et 19 productions couvertes. Le corrigé de
référence disponible comporte 9 cellules ; il est seulement validé comme
notebook lisible. Aucune divergence non expliquée avec A71a ne subsiste.

## Confidentialité et limites du MVP

Les notebooks, chemins locaux, identités, résultats et rapports privés restent
hors de Git. Les tests utilisent exclusivement de petits notebooks synthétiques
anonymes.

A71b ne vérifie pas les valeurs de code ou outputs, ne juge pas le graphe,
n'analyse aucune copie et ne produit ni diagnostic, rapport, commentaire,
score ou note. A71c devra orchestrer les moteurs, fournir les adaptateurs code
et graphe et préserver la validation humaine obligatoire.

## Orchestration A71c

La configuration est désormais consommée par l'[orchestration en lecture
seule](snells_laws_copy_orchestration.md). Celle-ci conserve les résolutions,
provenances et non-évaluabilités sans modifier les attentes A71b. La conclusion
finale reste distincte des deux interprétations de comparaison.
