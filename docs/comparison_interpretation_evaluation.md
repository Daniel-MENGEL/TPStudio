# Observation et évaluation de l'interprétation du En

A70e sépare trois informations : le `normalized_error` interne calculé par
A70b, la valeur finale de En écrite par l'étudiant et comparée par A70d, et la
conclusion textuelle observée par A70e. Les deux dernières évaluations sont
parallèles : concordance ou absence du En étudiant ne modifie jamais le statut
de sa conclusion.

Le professeur déclare, pour chaque comparaison concernée, des couples formés
d'un `ComparisonInterpretationKind` et d'une phrase littérale. L'extracteur
recherche exclusivement ces phrases, avec leur casse et leur Unicode exacts.
Il ne normalise, ne corrige, ne complète et ne recherche aucun synonyme. Une
conclusion implicite n'est donc pas devinée.

Une unique source `RESOLVED` et une unique observation sont nécessaires. Les
preuves conservent la phrase et ses offsets, jamais le texte source complet.
Absence et ambiguïté donnent des raisons structurées ; plusieurs sources ne
sont ni concaténées ni départagées. Le départage par longueur, puis par ordre
de déclaration en cas d'égalité, s'applique uniquement aux phrases qui
commencent au même offset. Les occurrences commençant à des offsets distincts
sont toutes conservées, même lorsque leurs intervalles se chevauchent.

La conclusion est comparée exclusivement au statut A70b. Elle peut
`MATCHES_OBJECTIVE_CLASSIFICATION`, le contredire, ou lui correspondre
partiellement. Ainsi une conclusion simplement `INCOHERENT` ne restitue que
partiellement une référence `STRONGLY_INCOHERENT`.

Pour une référence fortement incohérente, `METHOD_LIMITATION` correspond
complètement lorsque le contexte déclaré est `METHOD_LIMITATION_EXPECTED` ;
sinon la correspondance reste partielle. Ce contexte ne change ni En ni le
classement objectif. Il indique seulement l'objectif pédagogique déclaré.

A70e n'évalue pas la formule, les étapes, la justification détaillée ou la
qualité du raisonnement. Il ne relit ni n'exécute le notebook, ne recalcule ni
En ni A70b et ne produit aucun diagnostic, feedback, score, pénalité ou note.
