# TPStudio

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

- [Commande `improve`](docs/improve.md) : génération non destructive de notebooks améliorés.
- [Glossaire scientifique](docs/glossary.md) : vocabulaire et détection déterministe utilisés par les diagnostics.
- [Attendus scientifiques du professeur](docs/teacher_expectations.md) : relations et conclusions de référence déclarées en Python.
