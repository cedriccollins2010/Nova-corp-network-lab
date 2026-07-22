# Guide de déploiement — NOVA_CORP

Comment déployer l'infrastructure du lab, étape par étape, avec incidents rencontrés et résolutions.

> **Note :** Pour la structure technique, voir [architecture.md](architecture.md).

---

## Phase 1 — Déploiement du Switch L3

**Résultat : ✅ Opérationnel**

1. Importer l'appliance Cisco IOSvL2 dans GNS3
2. Créer 5 VLANs (10/20/30/40/50)
3. Configurer les SVIs : `192.168.x.254` comme passerelle pour chaque VLAN
4. Créer un trunk 802.1Q vers R1
5. Configurer les ACLs inter-VLAN selon votre matrice de flux
6. Tester SNMP v2c (community `nova-ro`, read-only)

**Fichier config :** `configs/network/switch-L3.conf`

---

## Phase 2 — Déploiement du Routeur R1

**Résultat : ✅ Opérationnel**

1. Importer l'appliance Cisco IOSv dans GNS3
2. Créer 5 sous-interfaces dot1Q sur Fa0/0 (une par VLAN, .10 à .50)
3. Configurer l'interface WAN : `Gi2/0 = 10.0.0.2/30` (vers FortiGate port2 = 10.0.0.1)
4. Ajouter la route par défaut : `ip route 0.0.0.0 0.0.0.0 10.0.0.1`
5. Configurer NTP avec correction EDT (summer-time)
6. Configurer SNMP v2c (community `nova-ro`)
7. Activer SSH v2 : `crypto key generate rsa modulus 2048` + `transport input ssh` sur VTY
8. Configurer syslog vers la GNS3 VM : `logging host 192.168.66.128:514`

**Fichier config :** `configs/network/R1.conf`

---

## Phase 3 — Déploiement FortiGate VM 7.6.7

**Résultat : ✅ Opérationnel**

### Incident 3.1 — Console noire dans GNS3

**Symptôme :** console PuTTY complètement noire, aucun output.

**Diagnostic :** image qcow2 incorrecte (pas une image KVM native). Port console mappé mal.

**Résolution :** 
- Télécharger l'image officielle KVM depuis Fortinet Support
- Importer via l'appliance `fortigate.gns3a` du marketplace GNS3
- GNS3 gère le mapping console automatiquement + crée le disque data `empty30G.qcow2`

### Incident 3.2 — Corruption du système de fichiers

**Symptôme :** avertissement disk au démarrage, puis comportements aléatoires (DHCP perdu, config non sauvegardée).

**Cause :** redémarrages forcés répétés (ctrl+C ou power off brutal).

**Résolution :** `execute disk scan 17` depuis la console FortiGate. Système restauré après le scan.

### Incident 3.3 — Activation licence bloquée par double-NAT

**Symptôme :** `execute update-now` restait en attente indéfinie.

**Cause :** lab derrière double-NAT (GNS3 VM NAT + routeur domestique), empêchant les callbacks FortiCare.

**Résolution :** activation via CLI avec identifiants FortiCare :
```
execute vm-license-options account-id <YOUR_ID>
execute vm-license-options account-password <YOUR_PASSWORD>
execute vm-license
```

### Incident 3.4 — Limite 3 policies

**Symptôme :** `edit 4` retourne erreur code -4.

**Résolution :** condenser 6 besoins en 3 policies via groupes d'adresses. Voir [architecture.md](architecture.md).

### Configuration finale FortiGate

```
Interfaces :
  port1 — LAN (réseau interne)
  port2 — lien R1 (10.0.0.1/30), allowaccess: ping ssh
  port3 — WAN (Internet)

Route statique :
  dst 192.168.0.0/16 via 10.0.0.2 (R1)

Objets :
  NET-USERS    = 192.168.10.0/24
  NET-SERVERS  = 192.168.20.0/24
  NET-GUESTS   = 192.168.50.0/24
  GRP-INTERNET-ALLOWED = NET-USERS + NET-SERVERS

Policies :
  1. GRP-INTERNET-ALLOWED → Internet (ALL services, log)
  2. NET-GUESTS → Internet (HTTP/HTTPS/DNS only, log)
  [deny all implicite]
```

**Fichier config :** `configs/fortigate/policies.conf`

---

## Phase 4 — Réseau de supervision

**Résultat : ✅ Opérationnel**

### Incident 4.1 — Conflit de sous-réseau

**Symptôme :** VM Ubuntu sur 192.168.50.0/24 (même sous-réseau que VLAN 50), collisions ARP.

**Résolution :** migrer la supervision vers 192.168.60.0/24 sur VMnet2. Appliquer sur :
- VMnet2 dans VMware (DHCP désactivé)
- `eth2` GNS3 VM (Netplan)
- `ens33` Ubuntu VM (NetworkManager)
- Route statique FortiGate

### Déploiement Docker

```bash
cd configs/supervision/
docker-compose up -d
```

**Services :**
- **syslog-ng** : Collecte logs UDP/514 (R1, FortiGate)
- **Graylog** : Interface web http://192.168.60.x:9000
- **OpenSearch** : Indexation 9200
- **Zabbix** : SNMP monitoring http://192.168.60.x:8080
- **LibreNMS** : Cartographie réseau http://192.168.60.x:8081

**Fichier config :** `configs/supervision/docker-compose.yml`

---

## Phase 5 — Active Directory

**Résultat : ✅ Opérationnel**

1. Déployer Windows Server 2022 dans VMware
2. Créer le domaine `novaenterprise.com`
3. Promouvoir en DC : `dcpromo`
4. Créer des OUs de base et des groupes
5. Joindre un poste Windows 11 (PROD01) au domaine
6. Configurer GPOs de base
7. Scripts PowerShell : LAPS v2, tiering, Sysmon

---

## Phase 6 — NetPilot AI (optionnel)

### Initialiser les index OpenSearch

```bash
pip install opensearch-py sentence-transformers
python netpilot/init_indices.py
```

Cela crée 3 index :
- `nova_configs` — stockage des running-configs avec embeddings
- `nova_changes` — diffs de configuration
- `nova_knowledge` — base de connaissance avec recherche sémantique

**Fichier script :** `netpilot/init_indices.py`

---

## Checklist rapide

- [ ] Switch L3 : 5 VLANs + trunk
- [ ] R1 : subinterfaces + syslog
- [ ] FortiGate : 3 policies + licences
- [ ] Docker : stack supervision running
- [ ] OpenSearch : 3 index created
- [ ] AD : domaine opérationnel

---

## Dépannage

- **Syslog R1 ne passe pas par FortiGate** → voir [troubleshooting.md](troubleshooting.md#bug-b--)
- **Accès FortiGate impossible** → voir [troubleshooting.md](troubleshooting.md#bug-a--)
- **Graylog ne reçoit pas les logs** → vérifier Docker logs, vérifier connectivité 192.168.66.128
