# Détection littérale des relations déclarées

`LiteralRelationMatcher` recherche dans une réponse étudiante les expressions
exactement déclarées par le professeur dans les `ExpectedRelation` d'un
`ExpectationSet`. Il produit une `RelationDetection` pour chaque relation, y
compris lorsqu'elle est absente.

```python
from tpstudio.examples.snell_descartes import snell_descartes_expectations
from tpstudio.reasoning import match_declared_relations

text = r"La relation est $n_1 \sin(i_1) = n_2 \sin(i_2)$."
detections = match_declared_relations(text, snell_descartes_expectations())

match = detections.found[0].first_match
assert match is not None
assert text[match.start:match.end] == match.matched_text
```

La forme canonique est examinée en premier, mais ne bénéficie d'aucun
privilège mathématique. Une variante acceptée est simplement une chaîne
supplémentaire explicitement fournie par le professeur. Une égalité inversée,
une casse différente ou des espaces différents ne sont reconnus que si cette
forme exacte est déclarée.

## Sémantique des résultats

La recherche est sensible à chaque caractère : casse, espaces, retours à la
ligne, Unicode, écriture LaTeX et ordre des membres. Les offsets utilisent la
convention Python : `start` est inclusif et `end` exclusif. `matched_text` est
toujours exactement égal à `text[start:end]` et à l'expression déclarée.

Une relation trouvée est seulement une correspondance textuelle, pas une
validation mathématique. Une relation absente n'est pas encore un diagnostic
ou une erreur pédagogique. Les `ExpectedConclusion` sont ignorées.

Cette fragilité est volontaire : A67b ne normalise rien, ne parse pas LaTeX et
ne calcule aucune équivalence algébrique. Elle stabilise les contrats de
détection et de preuve avant l'introduction éventuelle d'une normalisation
contrôlée.

Dans le modèle général introduit par A68a, ce matcher reste un détecteur
spécialisé, limité aux relations dont le contenu textuel est explicitement
déclaré par le professeur.
