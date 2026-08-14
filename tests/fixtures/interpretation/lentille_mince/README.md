# Fixtures A73c1 — Lentille mince

Ce jeu contient **15 fixtures contrôlées** pour tester la revue assistée des
`interpretation_response` :

- 5 contextes scientifiques provenant de vraies copies étudiantes historiques ;
- pour chaque contexte :
  - une réponse simulée `CLEARLY_SUFFICIENT` ;
  - une réponse simulée `CLEARLY_INSUFFICIENT` ;
  - une réponse simulée `AMBIGUOUS`.

## Principe de provenance

Les notebooks étudiants originaux ne sont pas modifiés.

Les champs de `scientific_context` sont dérivés des sorties réellement présentes
dans les copies. Les champs `student_answer` sont volontairement simulés afin de
constituer un banc d'essai dont la classification attendue est fixée à l'avance.

## Attention — copie Hugo/Carl

La copie Hugo/Carl contient dans le calcul de l'écart normalisé l'opérateur `//`
au lieu de `/`, ce qui conduit à l'affichage `En = 0.0`. La fixture conserve cette
information comme provenance mais **ne considère pas ce `En=0.0` comme un résultat
scientifique fiable**.

## Destination proposée dans le dépôt

```text
tests/fixtures/interpretation/lentille_mince/
    README.md
    a73c1_lentille_mince_cases.json
```

Aucune modification du moteur A73c1 n'est incluse dans ce paquet.
