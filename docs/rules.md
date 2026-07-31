# Règles pédagogiques déclaratives

Le jalon A64 ajoute des règles inspectables aux faits structurés d'A63. Un
`Fact` décrit une information atomique extraite ou construite. Une `Rule`
décrit déclarativement les faits attendus et la conclusion structurée à
produire lorsque cette attente est satisfaite.

## Conditions et traces

Les conditions sont des objets, pas des fonctions anonymes. Les conditions
élémentaires recherchent un type de fait (`FactKindExists`), un sujet
(`SubjectExists`), un prédicat (`PredicateExists`) ou plusieurs critères
portés par le même fait (`FactExists`). `FactAbsent` exprime explicitement une
absence. `AllOf`, `AnyOf` et `Not` permettent leur composition logique.

```python
from tpstudio.reasoning import (
    AllOf, FactKind, FactKindExists, Not, SubjectExists,
)

condition = AllOf(
    SubjectExists("snell_descartes"),
    Not(FactKindExists(FactKind.RELATION)),
)
result = condition.evaluate(facts)
```

L'évaluation renvoie un `ConditionResult` immutable. Il indique la valeur
booléenne, conserve les faits contributeurs dans un ordre stable, les traces
des sous-conditions et de petites données techniques d'explication. Aucun
commentaire destiné à l'étudiant n'est généré.

## Structure et évaluation d'une règle

```python
from tpstudio.reasoning import Rule, RuleConclusion

rule = Rule(
    id="R001",
    label="Relation scientifique absente",
    condition=condition,
    conclusion=RuleConclusion(
        code="relation_missing",
        category="scientific_relation",
        data=(("concept", "snell_descartes"),),
    ),
    priority=10,
    metadata=frozenset(("optics",)),
)

evaluation = rule.evaluate(facts)
```

`RuleConclusion` transporte un code stable et des données structurées, jamais
la rédaction finale. `RuleEvaluation` contient l'identifiant de la règle, son
état déclenché ou non et la trace détaillée de sa condition. Sa conclusion est
présente uniquement lorsque la règle se déclenche.

`RuleSet` est une collection ordonnée. Il garantit l'unicité stricte des
identifiants, permet une recherche par identifiant et des vues filtrées par
priorité ou métadonnée. Il n'évalue pas automatiquement ses règles.

## Limites volontaires d'A64

A64 ne fournit ni moteur global d'inférence, ni résolution de priorités ou de
conflits, ni agrégation des conclusions, notation ou diagnostic rédigé. Les
traces immutables et les conclusions structurées préparent ces responsabilités
pour les prochains jalons. Les comparaisons numériques, quantificateurs et
stratégies d'application pourront être ajoutés sous forme de nouvelles
conditions sans modifier les règles existantes.
