# Orchestration d'une copie Snell-Descartes

A71e consomme les feedbacks, diagnostics et résolutions A71c sans relancer l'analyse. Le notebook source demeure intact ; seule une copie mémoire peut recevoir les annotations planifiées.

Le résultat A71c alimente le rapport professeur A71d. A71c reste l'unique couche d'analyse et d'évaluation ; A71d projette ses résultats sans relire le notebook ni recalculer un statut.

## Rôle d'A71c

A71c relie la configuration professeur A71b aux moteurs existants pour une
copie explicitement fournie. Le notebook est chargé une fois avec `nbformat`,
en lecture seule. L'option `execute_notebook` vaut `False` par défaut et sa
valeur `True` est explicitement refusée dans ce jalon.

```text
Notebook
   ↓
Inspection technique
   ↓
Résolution des productions
   ↓
Adaptateurs texte / code / outputs / graphe
   ↓
Évaluations scientifiques
   ↓
Diagnostics
   ↓
Feedbacks
   ↓
CopyAnalysisResult
```

## Inspection et résolution

L'inspection conserve le format, le kernel, les effectifs de cellules, les
codes non exécutés, erreurs enregistrées, outputs, cellules vides, pièces
jointes et références simples à des fichiers externes. Un `?` n'est signalé
que dans une cellule de code. Un import exécuté sans sortie n'est pas une
erreur.

Les 19 bindings A71b sont résolus par le moteur A69c. Chaque résolution reste
`RESOLVED`, absente ou ambiguë sans sélection arbitraire. Les textes transmis
aux chaînes A70 sont les fragments exacts des cellules résolues : aucune
fusion, normalisation ou correction n'est appliquée.

## Valeurs et outputs enregistrés

L'adaptateur AST accepte seulement une affectation simple d'un littéral
numérique, avec signe unaire éventuel. Il n'emploie ni `eval`, ni `exec`, ni
appel de fonction, ni état de kernel. Les outputs `stream`, `execute_result` et
`display_data` en `text/plain` peuvent fournir une preuve associée sans aucune
exécution. Leur provenance et leur texte minimal sont conservés.

La priorité est appliquée par niveau : texte quantitatif explicite de la
production, puis littéral sûr d'une cellule de code associée, puis output
enregistré. Une ambiguïté au niveau prioritaire bloque tout fallback. Les
preuves de niveaux inférieurs restent néanmoins structurées afin de rendre une
divergence observable. Plusieurs preuves identiques ne créent pas une fausse
valeur distincte.

L'unicité scientifique minimale porte sur le couple valeur–unité. Deux preuves
de même valeur et de même unité sont concordantes et restent toutes conservées.
La même valeur numérique avec deux unités différentes, ou avec une unité dans
un cas et aucune dans l'autre, est ambiguë. Aucune conversion ni normalisation
d'unité n'est effectuée par l'orchestration ; cette règle reste distincte de la
limitation générale A70b sur les grandeurs sans dimension.

La valeur sélectionnée est adaptée en une preuve quantitative minimale, puis
transmise au pipeline A68/A69 existant avant A70b. Le moteur scientifique garde
donc l'autorité sur la structure et l'incertitude ; A71c ne recalcule rien. La
détection originale reste parallèlement accessible par `production_id`, avec
sa source, sa cellule, son texte brut, ses offsets et son indicateur
d'obsolescence. Un output enregistré peut être obsolète lorsque sa cellule n'a
pas été exécutée ou conserve une erreur ; il n'est jamais supposé synchronisé
avec le code.

## Quantités, relations et comparaisons

Le resolver A69c produit d'abord le jeu de résolutions partagé. Après détection
et adaptation, le pipeline quantitatif A68/A69 est appelé une seule fois, puis
les évaluateurs A70b, A70d, A70e et A70g sont appelés une fois chacun pour les deux
comparaisons configurées. En interne, conclusion objective, En étudiant,
interprétation et justification restent quatre objets séparés.

Une limite antérieure est conservée sans modification : A70b exige une unité
observée pour toute comparaison, alors qu'A71b déclare les indices optiques
sans dimension et ignore leur unité. Dans cet état, ces comparaisons peuvent
rester `NOT_EVALUABLE`; A71c conserve la raison au lieu d'inventer une unité.

Les relations déclarées conservent leur résolution structurelle. A71c ne
comprend pas librement une loi physique et ne calcule aucune incertitude
absente.

## Graphe et régression

L'adaptateur graphique inspecte uniquement l'AST du code associé et la présence
d'un output image. Il conserve les expressions x/y, labels littéraux, appel de
régression et cible de pente. Il sait signaler une inversion structurelle de
`sin(i2)` et `sin(i1)`, une régression absente ou inversée, et une syntaxe non
évaluable. Aucun pixel n'est analysé, aucun OCR ni Matplotlib n'est exécuté.

## Diagnostics, feedbacks et options

Les builders A70c, A70f et A70h consomment les évaluations existantes. Les
catalogues français A71b sont les seules sources de texte. Les options peuvent
désactiver diagnostics, rendu, audience étudiant ou audience professeur sans
modifier les catalogues. Aucun feedback positif, score ou note n'est ajouté.

## Conclusion finale et résultat global

`FinalConclusionObservation` conserve séparément la résolution et le texte de
`final_conclusion`. Elle ne reçoit jamais le statut de la dernière comparaison.

`CopyAnalysisResult` agrège inspection, résolutions, valeurs et provenances,
quantités, incertitudes, relations, graphe, quatre étages de comparaison,
diagnostics, feedbacks, conclusion et limites. `requires_human_review` est un
indicateur de prudence, jamais une notation. Le résumé public expose seulement
les identifiants locaux non nominatifs et les effectifs, jamais le chemin ou le
texte complet des réponses.

## Confidentialité et suite

Les tests utilisent uniquement des notebooks synthétiques anonymes. Aucun
notebook, chemin privé, nom, output réel ou rapport individuel n'est versionné.
Le script local exige un chemin explicite, ne modifie ni n'exécute le fichier
et n'enregistre aucun rapport.

A71d devra construire le rapport professeur détaillé à partir de l'objet
structuré, avec validation humaine. L'insertion de commentaires, les exports,
le traitement par lot, l'interface et la notation restent hors périmètre.
A71f consomme le résultat d'analyse et le plan A71e pour publier une copie
annotée et son HTML, sans relire ni exécuter le code étudiant à des fins de
recalcul.
