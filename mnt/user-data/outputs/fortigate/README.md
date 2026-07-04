# Config FortiGate

`policies.conf` regroupe les interfaces, les objets adresse, le groupe d'adresses, la route par défaut et les politiques de pare-feu du FortiGate VM 7.6.7, nettoyés pour publication.

Le point intéressant de cette config est la contrainte : la licence invalide plafonne le pare-feu à trois policies, trois interfaces et trois routes. Plutôt que de chercher à contourner la limite, j'ai fait tenir les six besoins de sécurité initiaux dans trois règles, en m'appuyant sur les groupes d'adresses et sur le deny-all implicite du FortiGate. Le raisonnement complet est dans [../docs/architecture.md](../docs/architecture.md).

Les IP publiques, la passerelle WAN et tout élément lié à la licence sont en placeholders (`<WAN_GATEWAY_IP>`, etc.). Les adresses privées sont conservées telles quelles puisqu'elles font partie de la logique documentée.

Pour réexporter la config complète depuis le FortiGate :

```
show full-configuration
```
