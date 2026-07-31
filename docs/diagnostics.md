# Diagnostics pédagogiques structurés

Le jalon A66 transforme les conclusions logiques du moteur d'inférence en
diagnostics pédagogiques indépendants de toute formulation. Le flux est :

`FactSet → RuleSet → InferenceEngine → DiagnosticBuilder → DiagnosticSet`.

Une `RuleConclusion` décrit le résultat interne d'une règle. Un `Diagnostic`
lui associe une catégorie, une gravité, une clé abstraite de message, la règle
source et les faits contributeurs. Le futur feedback choisira une langue, un
style et une formulation ; A66 ne stocke donc aucun message rédigé.

```python
from tpstudio.reasoning import (
    DiagnosticBuilder, DiagnosticCategory, DiagnosticDefinition,
    DiagnosticRegistry, DiagnosticSeverity, Fact, FactKind, FactSet,
    InferenceEngine, Rule, RuleConclusion, RuleSet, SubjectExists,
)

facts = FactSet((
    Fact("concept:snell", FactKind.CONCEPT_MENTION,
         "snell_descartes", "mentioned"),
))
rules = RuleSet((
    Rule(
        "R001",
        SubjectExists("snell_descartes"),
        RuleConclusion("relation_missing", data=(("concept", "snell_descartes"),)),
        label="Relation absente",
    ),
))
inference = InferenceEngine().evaluate(facts, rules)

registry = DiagnosticRegistry((
    DiagnosticDefinition(
        conclusion_code="relation_missing",
        diagnostic_code="relation_missing",
        category=DiagnosticCategory.MISSING_ELEMENT,
        severity=DiagnosticSeverity.WARNING,
        message_key="diagnostic.relation_missing",
    ),
))
diagnostics = DiagnosticBuilder(registry).build(inference)
```

## Registre, ordre et preuves

Le registre contient une seule définition immutable par code de conclusion.
Une conclusion déclenchée sans définition provoque
`UnknownDiagnosticDefinitionError` : rien n'est ignoré silencieusement. Le
builder ne transforme que les règles déclenchées, dans leur ordre d'évaluation.
Il reprend directement les faits contributeurs de `ConditionResult`, sans
réévaluer les règles ni rechercher les faits.

La provenance des données reste explicite dans `Diagnostic` : `metadata`
contient uniquement les métadonnées statiques déclarées par
`DiagnosticDefinition`, tandis que `conclusion_data` contient uniquement le
payload dynamique de `RuleConclusion.data`. Le builder ne fusionne pas ces
deux collections et ne les interprète pas.

`DiagnosticSet` conserve l'ordre et les doublons. Il offre des vues filtrées
par gravité, catégorie, code et règle source, sans modifier la collection.

## Limites d'A66

A66 ne rédige aucune phrase, ne fournit ni templates linguistiques ni
internationalisation complète, et ne calcule aucune note. Il ne fusionne, ne
classe et ne pondère pas les diagnostics. La résolution de conflits et la
transformation de diagnostics en feedback relèvent des jalons suivants.
