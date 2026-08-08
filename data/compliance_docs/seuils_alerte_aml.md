# Seuils d'alerte anti-blanchiment (AML)

Les seuils suivants déclenchent une alerte automatique nécessitant une revue
manuelle, indépendamment du score de fraude du modèle de scoring transactionnel :

- Toute transaction unique supérieure à 10 000 EUR vers un pays hors zone SEPA.
- Cumul de transactions dépassant 15 000 EUR sur une fenêtre glissante de 24h
  pour un même compte émetteur, réparties sur plusieurs destinataires.
- Toute transaction impliquant un compte nouvellement ouvert (moins de 30 jours)
  dont le montant dépasse 5 000 EUR.
- Trois transactions ou plus juste en dessous du seuil de déclaration
  réglementaire (structuration suspectée) sur une période de 7 jours.

Ces seuils sont indépendants du modèle de scoring de fraude transactionnelle :
une transaction peut être jugée non-frauduleuse par le modèle tout en déclenchant
une alerte AML, et inversement. Les deux dispositifs sont complémentaires, pas
substituables l'un à l'autre.