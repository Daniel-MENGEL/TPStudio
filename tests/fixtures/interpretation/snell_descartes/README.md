# Fixtures A73c1.1 — Snell-Descartes

Ce corpus sert de **test de généralisation hors corpus Lentille**.

Il contient 15 cas :
- 5 `CLEARLY_SUFFICIENT`
- 5 `CLEARLY_INSUFFICIENT`
- 5 `AMBIGUOUS`

Les contextes scientifiques sont issus de vraies copies historiques.
Les réponses d'interprétation sont simulées et fixées avant exécution du moteur.

Les cinq contextes ne reproduisent pas tous la même tâche :
- comparaison de deux déterminations de l'indice ;
- interprétation d'une régression de `sin(i1)` en fonction de `sin(i2)` ;
- contrôle de cohérence d'un écart normalisé manifestement suspect.

## Cas Hugo/Carl

Le notebook calcule :

`abs(n.mean() - n0 / sqrt(...))`

au lieu de :

`abs(n.mean() - n0) / sqrt(...)`

Le `En = 10.0833` affiché n'est donc pas fiable. Ce cas est conservé
volontairement pour tester une situation où l'interprétation doit remettre
en cause un résultat numérique incohérent.

Aucune modification du moteur A73c1.1 n'est incluse dans ce paquet.
