# NOVA_CORP — Lab réseau PME

Simulation complète d'une PME (20-50 postes) sur une seule machine : 5 VLANs, routage Cisco, FortiGate, Active Directory, SIEM (Graylog/OpenSearch), Zabbix, LibreNMS.

Terrain de pratique pour certifications CCNA · Security+ · FCP FortiGate NSE4.

---

## 📖 Documentation

| Document | Contenu |
|---|---|
| **[Architecture](docs/architecture.md)** | Structure technique, VLANs, plan d'adressage, choix architecturaux |
| **[Deployment Guide](docs/deployment.md)** | Comment tout configurer, phase par phase, incidents et résolutions |
| **[Troubleshooting](docs/troubleshooting.md)** | Bugs identifiés (asymmetric bridge, syslog FortiGate), diagnostics détaillés |
| **[Roadmap](docs/roadmap.md)** | Prochaines étapes et backlog |

---

## 📊 Statut

| Composant | État |
|---|---|
| Switch L3 (5 VLANs, SNMP) | 
| Routeur R1 (inter-VLAN, syslog) | 
| FortiGate VM 7.6.7 (3 policies) | 
| Graylog + OpenSearch | 
| Zabbix + LibreNMS | 
| Active Directory | 
| Bug A (asymmetric bridge) | 
| Bug B (syslog FortiGate) | 
| NetPilot AI | 

---

##  Quick Start

```bash
# 1. Lancer le lab dans GNS3
# (configs dans configs/network/ et configs/fortigate/)

# 2. Démarrer la supervision
cd configs/supervision
docker-compose up -d

# 3. Initialiser OpenSearch
pip install opensearch-py sentence-transformers
python netpilot/init_indices.py

# 4. Accéder aux interfaces
# - Graylog: http://192.168.60.x:9000
# - Zabbix: http://192.168.60.x:8080
# - LibreNMS: http://192.168.60.x:8081
```

Pour les détails, voir [Deployment Guide](docs/deployment.md).

---

##  Structure

```
configs/
├── network/
│   ├── R1.conf
│   └── switch-L3.conf
├── fortigate/
│   └── policies.conf
└── supervision/
    └── docker-compose.yml

docs/
├── architecture.md          # Structure technique
├── deployment.md            # Guide de déploiement
├── troubleshooting.md       # Bugs et diagnostics
└── roadmap.md               # À faire

netpilot/
└── init_indices.py          # Initialisation OpenSearch
```

---

##  Stack

| Outil | Rôle |
|---|---|
| Cisco IOSv | Routeur inter-VLAN |
| Cisco IOSvL2 | Switch 5 VLANs |
| FortiGate 7.6.7 | Pare-feu Internet |
| syslog-ng | Collecte logs |
| Graylog + OpenSearch | SIEM |
| Zabbix | Supervision SNMP |
| LibreNMS | Cartographie réseau |
| Windows Server 2022 | Active Directory |

---

##  Problèmes connus

### Bug A — Asymmetric bridge (GNS3 Cloud node)
**Statut :** Workaround actif  
Réponses ARP bloquées via Cloud node → tout passe par lien 10.0.0.0/30 interne.

### Bug B — Syslog R1 → FortiGate → SIEM
**Statut :** Non résolu  
Paquets bloqués avant moteur de policy FortiGate. Piste : changer destination syslog R1.

  Diagnostics complets : [Troubleshooting](docs/troubleshooting.md)

---

##  Licence

MIT — configurations sanitisées, à adapter à votre environnement.

---

*Cédric Tanekeu Somkwe — CCNA · Security+ · MD-102 · FortiGate NSE4*
