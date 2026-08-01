# Démonstration de bout en bout Snell-Descartes

A66.5 assemble les composants déterministes existants dans un prototype
observable :

`Text → Glossary → ConceptExtractor → FactSet → RuleSet → InferenceEngine → DiagnosticBuilder → DiagnosticSet`

L'orchestration générique se trouve dans `tpstudio.reasoning.demo`. La
configuration pédagogique, le glossaire et les cas Snell-Descartes restent
isolés dans `tpstudio.examples.snell_descartes` et ne deviennent donc pas des
dépendances du moteur.

## Exécution

Depuis la racine du projet :

```console
python -m tpstudio.examples.snell_descartes
```

Le module peut aussi être importé :

```python
from tpstudio.examples.snell_descartes import run_snell_descartes_demo
from tpstudio.reasoning import format_end_to_end_report

reports = run_snell_descartes_demo()
print(format_end_to_end_report(reports[1]))
```

Les trois cas fournis sont :

1. `complete`, qui mentionne la loi, l'indice et les deux angles ;
2. `partial`, qui mentionne la loi et l'indice, mais aucun angle ;
3. `off-topic`, qui ne contient aucun concept du glossaire de démonstration.

Extrait du rendu du cas partiel :

```text
Case: partial
Description: La loi et les indices sont présents, mais pas les angles.
Student answer: La loi de Snell-Descartes utilise les indices de réfraction.
Detected facts:
  - concept_mention:snell_descartes:3:25 | concept_mention | subject=snell_descartes | evidence='loi de Snell-Descartes'
  - concept_mention:indice_refraction:38:59 | concept_mention | subject=indice_refraction | evidence='indices de réfraction'
Triggered rules:
  - SNELL_MISSING_INCIDENCE_ANGLE
  - SNELL_MISSING_REFRACTION_ANGLE
...
Diagnostics:
  - angle_incidence_missing | warning | rule=SNELL_MISSING_INCIDENCE_ANGLE | key=diagnostic.snell.angle_incidence_missing
    evidence: subject=snell_descartes excerpt='loi de Snell-Descartes'
```

Ce rendu sans couleurs est un outil de développement. Il montre les faits,
les règles déclenchées ou non, les diagnostics structurés et leurs preuves ;
il ne constitue pas un feedback adressé à l'étudiant.

## Capacités et limites observées

Le prototype détecte uniquement la présence ou l'absence de quatre concepts
grâce au glossaire. Le `ConceptExtractor` produit exclusivement des
`CONCEPT_MENTION`. Aucune relation, équation ou valeur numérique n'est créée
manuellement dans le flux.

En particulier, écrire une formule de Snell-Descartes incorrecte tout en
mentionnant les quatre concepts produit le même résultat que les mentionner
correctement. Le système ne dispose encore d'aucun parseur d'équations,
d'analyse mathématique, de NLP ou d'IA capable de distinguer ces situations.
Cette limite devra guider le prochain jalon avant toute prétention de valider
une relation scientifique.
