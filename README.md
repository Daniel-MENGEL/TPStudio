# TPStudio

La verticale Snell-Descartes dispose d'un [rapport professeur Markdown A71d](docs/snells_laws_teacher_report.md), construit exclusivement depuis l'analyse structurée A71c.

Outils de génération et de correction de TP de physique en CPGE.

## Jalon A2 — parseur LaTeX

Cette étape ajoute une première commande utilisable :

```bash
tpstudio inspect /chemin/vers/un/dossier/de/TP
```

Elle détecte le fichier `.tex`, extrait les métadonnées et les blocs pédagogiques normalisés, puis écrit dans `_build/` :

- `manifest.json` ;
- `rapport_inspection.md`.

Le parseur est spécialisé pour la structure habituelle des TP : `\objectifs`, `\materiel`, `\annexes`, `\indications`, `\questions`, `\rapport`, `\appels`.

## Documentation

- [Audit de la verticale Snell-Descartes](docs/snells_laws_vertical_audit.md) : comparaison des supports et copies anonymisées, couverture des moteurs historiques et actuels, puis périmètre du MVP A71.
- [Configuration professeur Snell-Descartes](docs/snells_laws_teacher_configuration.md) : projet Python explicite, bindings et attentes du support amélioré, sans donnée de copie.
- [Orchestration d'une copie Snell-Descartes](docs/snells_laws_copy_orchestration.md) : lecture seule, adaptateurs prudents et chaînes A70 agrégées sans exécution ni notation.
- [Commande `improve`](docs/improve.md) : génération non destructive de notebooks améliorés.
- [Glossaire scientifique](docs/glossary.md) : vocabulaire et détection déterministe utilisés par les diagnostics.
- [Attendus scientifiques du professeur](docs/teacher_expectations.md) : relations et conclusions de référence déclarées en Python.
- [Détection littérale des relations](docs/literal_relation_matching.md) : recherche exacte des expressions déclarées par le professeur.
- [Productions scientifiques](docs/scientific_production_model.md) : nature des productions attendues et bases de leurs futures évaluations.
- [Attendus de grandeurs numériques](docs/quantity_expectations.md) : symboles, unités et exigences structurelles déclarés sans valeur imposée.
- [Évaluation des comparaisons quantitatives](docs/quantity_comparison_evaluation.md) : calcul Decimal objectif de l'écart normalisé à partir des résultats A69d.
- [Observation du En étudiant](docs/student_normalized_error_evaluation.md) : extraction littérale et comparaison à la référence interne avec une tolérance explicite.
- [Interprétation du En](docs/comparison_interpretation_evaluation.md) : observation de phrases déclarées et comparaison de la conclusion au classement objectif.
- [Diagnostics](docs/comparison_interpretation_diagnostics.md) et [feedbacks](docs/comparison_interpretation_feedback.md) de l'interprétation : constats structurés et messages configurables, sans notation.
- [Justification d'une comparaison](docs/comparison_justification_evaluation.md) : présence structurelle d'éléments déclarés, sans analyse scientifique libre.
- [Diagnostics](docs/comparison_justification_diagnostics.md) et [feedbacks](docs/comparison_justification_feedback.md) de justification : constats structurés et messages configurables, sans notation.
- [Diagnostics des comparaisons](docs/quantity_comparison_diagnostics.md) et [feedback configurable](docs/quantity_comparison_feedback.md) : constats objectifs et messages explicites, sans notation.
- [Observations textuelles de quantités](docs/quantity_observations.md) : extraction littérale de valeurs, incertitudes et unités déclarées.
- [Évaluation structurelle des quantités](docs/quantity_structural_evaluation.md) : contrôle interne de présence, sans jugement scientifique ni diagnostic.
- [Évaluation intrinsèque des incertitudes](docs/quantity_uncertainty_evaluation.md) : positivité et présentation d'une incertitude observée.
- [Diagnostics structurés des quantités](docs/quantity_diagnostics.md) : traduction stable des évaluations, sans message étudiant ni sévérité.
- [Feedback configurable des quantités](docs/quantity_feedback.md) : formulations statiques, audiences et priorités fournies par catalogue.
- [Orchestration d'une grandeur textuelle](docs/quantity_assessment_pipeline.md) : chaîne complète et auditable pour une production quantitative à la fois.
- [Rattachement cellule–production](docs/notebook_production_bindings.md) : configuration déclarative des cellules destinées aux productions scientifiques.
- [Résolution des rattachements](docs/notebook_binding_resolution.md) : recherche littérale et extraction en lecture seule dans un notebook nbformat déjà chargé.
- [Évaluation des quantités du notebook](docs/notebook_quantity_assessment.md) : orchestration des bindings quantitatifs résolus vers le pipeline d'assessment.
- [Attendus de comparaisons quantitatives](docs/quantity_comparison_expectations.md) : méthode, seuils objectifs et contexte pédagogique déclarés sans calcul.
