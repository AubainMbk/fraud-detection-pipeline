# Procédure de contestation d'un blocage de compte

Lorsqu'un client conteste le blocage automatique de son compte suite à une alerte
de fraude, l'analyste doit suivre la procédure suivante :

1. Vérifier l'identité du client via les deux facteurs d'authentification standards
   (pièce d'identité + code envoyé sur le numéro de téléphone enregistré).
2. Consulter l'historique de la transaction ayant déclenché le blocage dans le
   système de scoring, en notant le score de probabilité de fraude et le seuil
   de décision appliqué au moment du blocage.
3. Si le score était proche du seuil de décision (dans une marge de 0.05), et que
   le client fournit une justification cohérente (voyage à l'étranger, achat
   inhabituel mais légitime), l'analyste peut lever le blocage immédiatement.
4. Si le score est très supérieur au seuil, une vérification renforcée est
   obligatoire avant toute levée de blocage, incluant un rappel téléphonique
   du client sur son numéro enregistré.
5. Toute levée de blocage doit être documentée dans le système de tickets avec
   la justification de l'analyste, conservée 5 ans à des fins d'audit.

Le délai maximal de traitement d'une contestation est de 24 heures ouvrées.