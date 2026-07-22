# Roadmap NOVA_CORP

---

## Priorité 1 — Résoudre Bug B (syslog)

**Action :** Changer la destination syslog sur R1

```
! Sur R1
no logging host 10.0.0.1
logging host 192.168.66.128
```

Vérifier ensuite sur syslog-ng :
```bash
tail -f ~/nova_corp_docker/syslog-ng/logs/R1/*.log
```

Et dans Graylog : recherche `source:R1` dans les 5 dernières minutes.

---

## Priorité 2 — Valider la limite 4e policy FortiGate

Test interrompu par disk warning. Reprendre :
```
config firewall policy
    edit 4
        set name "TEST-LIMITE-4"
        set srcintf "port2"
        set dstintf "port1"
        set srcaddr "HOST-R1"
        set dstaddr "all"
        set action accept
        set schedule "always"
        set service "SYSLOG"
    next
end
```
Si `edit 4` passe sans erreur -4, la limite de 3 policies n'est pas appliquée sur cette build — ce qui ouvre la possibilité de créer des règles granulaires supplémentaires.

---

## Priorité 3 — NetPilot AI

**Étape suivante : collecteur Netmiko**

```python
# netpilot/collector.py — à créer
from netmiko import ConnectHandler

r1 = {
    "device_type": "cisco_ios",
    "host": "10.0.0.2",   # accessible via lien /30
    "username": "admin",
    "password": "<secret>",
}

with ConnectHandler(**r1) as conn:
    output = conn.send_command("show running-config")
    # → indexer dans OpenSearch index "configs"
    # → calculer diff avec hier_config
    # → stocker dans index "changes"
```

Après le collecteur : endpoint FastAPI `/collect`, puis interface React.

---

## Priorité 4 — Extension OIV/SOC

Modules planifiés (profil RAM ~12.5 Go, nécessite suspension PROD01) :

| Module | Rôle | RAM estimée |
|---|---|---|
| Wazuh | SIEM/EDR (remplace Graylog) | ~4 Go |
| Keycloak | IAM / SSO | ~1 Go |
| TheHive + Cortex | Case management SOC | ~3 Go (on-demand) |
| FreeRADIUS | NAC / 802.1X | ~256 Mo |
| Guacamole | Accès bastion web | ~512 Mo |
| OpenVAS | Scan de vulnérabilités | ~2 Go (on-demand) |

Deux profils d'exploitation :
- **Socle permanent** : Wazuh + Keycloak + FreeRADIUS + Guacamole (~11.5 Go)
- **Demo SOC** (PROD01 suspendu) : + TheHive/Cortex + OpenVAS (~12.5 Go)

---

## Priorité 5 — Certification FCP FortiGate 7.6 (NSE4)

Modules restants à compléter pour l'examen. Lab NOVA_CORP couvre déjà :
- Interfaces, zones, politiques de base
- Routage statique
- SSL VPN (configuré mais non testé en production)
- IPS et profils de sécurité (configurés)
- Syslog et SNMP (partiellement)

Modules à approfondir : SD-WAN, HA, FortiManager/FortiAnalyzer, authentification FSSO.

---

## Backlog (sans ordre de priorité)

- Résoudre Bug A (Cloud node) — investigation bridge VMware alternatif
- Tester SSL VPN en production
- Déployer GLPI (ITSM/CMDB) — config Docker Compose déjà prête
- Pousser le repo GitHub public
- Ajouter diagramme de topologie animé au README
- Documenter les scripts PowerShell AD (LAPS, backup, Sysmon)
