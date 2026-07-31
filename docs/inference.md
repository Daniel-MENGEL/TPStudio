# Moteur d'inférence

Le jalon A65 introduit `InferenceEngine`, l'orchestrateur déterministe des
règles pédagogiques. Il applique chaque `Rule` d'un `RuleSet` au même
`FactSet`, une seule fois et dans l'ordre d'insertion des règles.

L'évaluation individuelle d'une `Rule` produit une `RuleEvaluation`.
L'évaluation globale d'un `RuleSet` produit un `InferenceResult` regroupant
toutes ces traces. Ses propriétés `triggered`, `not_triggered` et
`conclusions` sont des vues calculées qui conservent l'ordre initial. Les
conclusions ayant le même code restent distinctes.

```python
from tpstudio.reasoning import (
    AllOf, Fact, FactKind, FactKindExists, FactSet,
    InferenceEngine, Not, Rule, RuleConclusion, RuleSet, SubjectExists,
)

facts = FactSet((
    Fact("concept:snell", FactKind.CONCEPT_MENTION,
         "snell_descartes", "mentioned"),
))
rules = RuleSet((
    Rule(
        id="R001",
        label="Relation absente",
        condition=AllOf(
            SubjectExists("snell_descartes"),
            Not(FactKindExists(FactKind.RELATION)),
        ),
        conclusion=RuleConclusion(code="relation_missing"),
    ),
    Rule(
        id="R002",
        label="Incertitude présente",
        condition=SubjectExists("incertitude"),
        conclusion=RuleConclusion(code="uncertainty_present"),
    ),
))

result = InferenceEngine().evaluate(facts, rules)
assert [item.rule_id for item in result.triggered] == ["R001"]
assert [item.rule_id for item in result.not_triggered] == ["R002"]
```

## Ordre et erreurs

Un déclenchement n'interrompt jamais les règles suivantes. La priorité d'une
règle ne réordonne pas l'évaluation et ne supprime aucune conclusion. En
revanche, toute exception levée par une règle est immédiatement propagée : le
moteur ne retourne pas un résultat global incomplet. Les règles du prototype
antérieur à A64 doivent ainsi être migrées avant toute inférence.

## Limites d'A65

Le moteur ne résout pas les conflits, ne fusionne pas les conclusions et ne
les convertit pas en faits. Il n'effectue donc aucun chaînage avant. Il ne
produit ni diagnostic rédigé, ni commentaire, ni note. Les futures stratégies
de sélection, dépendances entre règles et transformations de conclusions
pourront être ajoutées autour de cette trace globale sans changer le contrat
d'évaluation déterministe d'A65.
