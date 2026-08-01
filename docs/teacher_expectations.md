# Attendus scientifiques du professeur

Le package `tpstudio.expectations` décrit les références scientifiques
fournies explicitement par le professeur. Un `ExpectationSet` correspondra
plus tard à une question, une réponse ou une partie précise d'un TP. A67a ne
le rattache encore ni à une cellule de notebook ni au pipeline de correction.

Une `ExpectedRelation` conserve une `canonical_expression` et des
`accepted_expressions` facultatives. Une `ExpectedConclusion` suit le même
principe avec `canonical_statement` et `accepted_statements`. Les propriétés
`expressions` et `statements` placent la référence canonique en premier et
retirent seulement les doublons exacts, dans l'ordre de déclaration.

```python
from tpstudio.expectations import (
    ExpectedConclusion,
    ExpectedRelation,
    ExpectationSet,
)

expectations = ExpectationSet(
    id="snell_answer",
    title="Loi de Snell-Descartes",
    relations=(
        ExpectedRelation(
            id="snell_relation",
            label="Relation attendue",
            canonical_expression=r"n_1 \sin(i_1) = n_2 \sin(i_2)",
            accepted_expressions=("n1 sin(i1) = n2 sin(i2)",),
        ),
    ),
    conclusions=(
        ExpectedConclusion(
            id="snell_meaning",
            label="Grandeurs reliées",
            canonical_statement=(
                "La loi relie les indices de réfraction aux angles "
                "d’incidence et de réfraction."
            ),
        ),
    ),
)
```

## Limites d'A67a

Ces objets sont uniquement des contrats déclaratifs stockés en Python afin de
stabiliser leur API. Ils ne reconnaissent encore rien dans une copie. Aucune
normalisation mathématique, équivalence algébrique ou équivalence sémantique
n'est calculée. Une égalité inversée n'est acceptée que si le professeur l'a
déclarée comme variante. Aucun parseur LaTeX, fichier YAML ou JSON, moteur
d'IA, fait, règle ou diagnostic n'est créé par cette couche.
