# Correction individuelle

La commande `correct-copy` assemble les briques de correction déjà validées par TPStudio.

```bash
tpstudio correct-copy modele.ipynb copie-etudiant.ipynb   --output-dir corrections/
```

Elle crée, sans modifier la copie originale :

```text
corrections/
├── copie-etudiant-correction.ipynb
└── copie-etudiant-correction.md
```

Le notebook corrigé réutilise les diagnostics existants : comparaison au modèle, réponses écrites, code, graphiques, commentaires locaux, couleurs et synthèse globale.

Par sécurité, TPStudio refuse d'écraser une correction existante. Le remplacement doit être explicite :

```bash
--overwrite
```
