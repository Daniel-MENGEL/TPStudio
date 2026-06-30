# TPStudio — commande `improve`

La commande `tpstudio improve` génère une copie améliorée d'un notebook de TP.

Elle est conçue pour être **non destructive** : le notebook source n'est jamais modifié.

## Utilisation

```bash
tpstudio improve "chemin/vers/le/dossier/du/TP"
```

TPStudio cherche dans le dossier :

- un notebook `.ipynb` élève ;
- un ou plusieurs fichiers `.tex` associés au TP.

Il crée ensuite un nouveau notebook :

```text
NomDuNotebook-ameliore.ipynb
NomDuNotebook-ameliore-2.ipynb
NomDuNotebook-ameliore-3.ipynb
...
```

si des copies améliorées existent déjà.

## Sélection du notebook source

TPStudio évite d'utiliser comme source les notebooks qui ressemblent à des fichiers de correction ou à des fichiers déjà générés.

Sont notamment ignorés comme sources :

```text
-correction
-corrige
-corrigé
-solution
-prof
-teacher
-ameliore
-amélioré
```

Cela évite d'améliorer plusieurs fois une copie déjà améliorée.

## Rôle de `\rapport`

La macro LaTeX `\rapport` sert d'indicateur pédagogique.

Si le fichier LaTeX contient une instruction active :

```latex
\rapport
```

alors TPStudio ajoute une grille complète :

```text
Évaluation par compétences
```

Si la ligne est commentée :

```latex
%\rapport
```

ou si `\rapport` est absent, TPStudio ajoute seulement une checklist légère :

```text
Checklist de fin de TP
```

La détection ignore ce qui se trouve après `%` sur chaque ligne LaTeX.

## Cellules ajoutées

Selon le contenu du notebook, TPStudio peut ajouter :

- des cellules `Résultat — ...` ;
- une cellule de comparaison des résultats ;
- une conclusion ou un bilan ;
- un bloc final `Améliorations proposées par TPStudio` ;
- une grille d'évaluation ou une checklist légère.

Les cellules `Résultat — ...` sont placées autant que possible à la fin de la section qui les a déclenchées.

## Principe pédagogique

La commande `improve` ne cherche pas à corriger le TP à la place du professeur.

Elle prépare une version plus exploitable du notebook :

- en identifiant les résultats expérimentaux attendus ;
- en ajoutant des zones de rédaction ;
- en harmonisant la structure ;
- en laissant le professeur valider le résultat final.

## Tests associés

Les comportements essentiels sont protégés par les tests de `tests/test_improver.py`.

Ils vérifient notamment :

- `\rapport` actif → grille complète ;
- `%\rapport` commenté → checklist légère ;
- absence de `\rapport` → checklist légère ;
- le notebook source n'est pas modifié ;
- les notebooks `-ameliore` ne sont pas repris comme source.
