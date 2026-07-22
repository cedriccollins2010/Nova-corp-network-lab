# Journal de déploiement — NOVA_CORP

Chronologie complète des travaux, incidents et décisions depuis le début du projet.

---

## Phase 0 — Conception initiale

**Objectif :** concevoir l'architecture d'un lab PME réaliste sur machine unique.

Décisions prises :
- 5 VLANs (10/20/30/40/50) en 192.168.x.0/24
- Routage inter-VLAN sur R1 (router-on-a-stick, subinterfaces dot1Q)
- FortiGate en passerelle Internet uniquement (pas de routage interne)
- Stack de supervision séparée : syslog-ng, Graylog/OpenSearch, Zabbix, LibreNMS
- Domaine AD : `novaenterprise.com`
- Tous les équipements réseau dans GNS3, la supervision dans VMware directement

Livrable initial : document Word (Strategie_IT_PME_Lab.docx) + config Markdown complète sur 6 phases (switch, R1, FortiGate, syslog-ng, Graylog/ELK, Zabbix/LibreNMS + Ansible).

---

## Phase 1 — Déploiement du Switch L3

**Résultat : ✅ Opérationnel**

- 5 VLANs créés (10/20/30/40/50)
- SVIs configurées : 192.168.x.254 comme passerelle pour chaque VLAN
- Trunk 802.1Q vers R1
- ACLs inter-VLAN selon matrice de flux
- SNMP v2c configuré (community `nova-ro`, read-only)

---

## Phase 2 — Déploiement du Routeur R1

**Résultat : ✅ Opérationnel**

- Sous-interfaces dot1Q sur Fa0/0 (une par VLAN, .10 à .50)
- Interface WAN : Gi2/0 = 10.0.0.2/30 (lien vers FortiGate port2 = 10.0.0.1)
- Route par défaut : `ip route 0.0.0.0 0.0.0.0 10.0.0.1`
- NTP configuré avec correction EDT (summer-time)
- SNMP v2c : community `nova-ro`
- SSH v2 : `crypto key generate rsa modulus 2048`, `transport input ssh` sur VTY
- Syslog vers `192.168.66.128:514` (GNS3 VM)

---

## Phase 3 — Déploiement FortiGate VM 7.6.7

**Résultat : ✅ Opérationnel (avec contrainte licence)**

### Incident 3.1 — Console noire dans GNS3

**Symptôme :** console PuTTY complètement noire, aucun output.

**Diagnostic :** image qcow2 incorrecte (pas une image KVM native). Port console mappé sur 5001 (QEMU) mais GNS3 annonçait 5002.

**Résolution :** téléchargement de l'image officielle KVM depuis le portail Fortinet Support (`FGT_VM64_KVM-v7.6.7.M-build3704-FORTINET.out.kvm.zip`). Import via l'appliance `fortigate.gns3a` du marketplace GNS3 (gère le mapping console automatiquement + disque data `empty30G.qcow2` requis).

### Incident 3.2 — Corruption du système de fichiers

**Symptôme :** avertissement disk au démarrage, puis comportements aléatoires (DHCP sur port1 perdu, config non sauvegardée).

**Cause :** redémarrages forcés répétés pendant les tests (ctrl+C / power off brutal depuis GNS3).

**Résolution :** `execute disk scan 17` depuis la console FortiGate. DHCP port1 restauré après le scan.

### Incident 3.3 — Activation licence bloquée par double-NAT

**Symptôme :** `execute update-now` restait en attente indéfinie ("Requesting FortiCare Trial license…").

**Cause :** le lab est derrière un double-NAT (GNS3 VM NAT + routeur domestique), empêchant FortiCare de répondre aux callbacks entrants.

**Résolution alternative :** activation via CLI avec identifiants FortiCare :
```
execute vm-license-options account-id 2134670
execute vm-license-options account-password <credential>
execute vm-license
```
**Résultat :** License Status: Valid, nouveau hostname `FGVMEVWVTDI-EMA5`.

### Incident 3.4 — Limite 3 policies (vdom-max=3)

**Symptôme :** `edit 4` retourne erreur code -4.

**Réponse :** condensation de 6 besoins en 3 policies via groupes d'adresses. Voir `architecture.md`.

**Note :** un test ultérieur de création de la 4e policy n'a pas retourné d'erreur — la limite pourrait ne pas être appliquée sur cette build spécifique. Test interrompu par disk warning, résultat inconnu.

### Configuration finale FortiGate

```
Interfaces :
  port1 — LAN (192.168.x.x réseau interne)
  port2 — lien R1 (10.0.0.1/30), allowaccess: ping ssh
  port3 — WAN (Internet)

Route statique :
  dst 192.168.0.0/16 via 10.0.0.2 (R1) — trafic retour vers VLANs

Objets :
  NET-USERS    = 192.168.10.0/24
  NET-SERVERS  = 192.168.20.0/24
  NET-GUESTS   = 192.168.50.0/24
  HOST-R1      = 10.0.0.2/32
  GRP-INTERNET-ALLOWED = NET-USERS + NET-SERVERS
  SERVICE SYSLOG = TCP+UDP/514

Policies :
  1. GRP-INTERNET-ALLOWED → Internet : ALL, log all
  2. NET-GUESTS           → Internet : HTTP/HTTPS/DNS, log all
  [deny all implicite]
```

---

## Phase 4 — Réseau de supervision

**Résultat : ✅ Opérationnel**

### Incident 4.1 — Conflit de sous-réseau

**Symptôme :** la VM Ubuntu de supervision (SIEM) était configurée sur 192.168.50.0/24, même sous-réseau que le VLAN 50 (Guests) dans GNS3.

**Impact :** collisions ARP, traffic mal routé entre les deux segments.

**Résolution :** migration du réseau de supervision vers 192.168.60.0/24. Corrections appliquées sur :
1. VMnet2 dans VMware Workstation (DHCP désactivé, plage 192.168.60.x)
2. `eth2` de la GNS3 VM via Netplan (`/etc/netplan/90-gns3vm-static.yaml`)
3. `ens33` de l'Ubuntu VM (fichiers `00-installer-config.yaml` + NetworkManager)
4. Route statique FortiGate (`192.168.60.0/24 via 10.0.0.2`)

### Déploiement syslog-ng

```bash
docker run -d \
  --name nova_syslog_ng \
  --restart unless-stopped \
  -p 514:514/udp \
  -p 514:514/tcp \
  -v ~/nova_corp_docker/syslog-ng/config/network-devices.conf:/etc/syslog-ng/conf.d/network-devices.conf \
  -v ~/nova_corp_docker/syslog-ng/logs:/var/log/nova_corp \
  balabit/syslog-ng
```

Écoute sur `0.0.0.0:514` UDP+TCP. Logs écrits dans `~/nova_corp_docker/syslog-ng/logs/${HOST}/${YEAR}-${MONTH}-${DAY}.log`.

### Déploiement Graylog + OpenSearch, Zabbix, LibreNMS

Stack complète déployée via Docker Compose sur l'Ubuntu VM. Accessible depuis le réseau de supervision. SNMP configuré sur R1 et le switch (community `nova-ro`) — Zabbix et LibreNMS découvrent les équipements correctement.

---

## Phase 5 — Bug A — Asymmetric bridge GNS3

**Résultat : 🔶 Workaround actif, bug structurel documenté**

### Symptôme

Les paquets sortent de la GNS3 VM vers le réseau physique via le Cloud node/eth1, mais les réponses ARP ne reviennent jamais. Confirmé par tcpdump :
- `eth1` : paquets ARP sortants visibles
- `eth1` : aucune réponse ARP entrante

Le bug survit aux reboots complets (VM + GNS3).

### Diagnostic approfondi

`ps aux | grep ubridge` a révélé **4 instances ubridge distinctes** sur des ports séparés (4008, 4128, 3904, 4400). Chaque instance crée un bridge virtuel isolé — les paquets entrent dans un bridge et ne peuvent pas atteindre un autre.

Causes éliminées : routage, cache ARP, santé VMnet1, règles Windows Firewall, driver Npcap.

**Cause racine confirmée :** architecture multi-instance de ubridge dans GNS3 lorsqu'on utilise plusieurs Cloud nodes sur une même GNS3 VM.

### Workaround actif

L'accès au FortiGate se fait via le lien interne `10.0.0.0/30` sur R1 (Gi2/0). Ce lien fonctionne car il reste entièrement dans GNS3 — aucun Cloud node impliqué.

SSH activé sur port2 FortiGate :
```
config system interface
    edit "port2"
        set allowaccess ping ssh
    next
end
```

### Impact sur la supervision

Les VM Ubuntu de supervision sont maintenant connectées via VMnet2 directement (hors GNS3), contournant complètement le Cloud node défaillant. Ce chemin est stable et fonctionnel.

---

## Phase 6 — Bug B — Syslog R1 → FortiGate → SIEM

**Résultat : 🔴 Non résolu**

### Symptôme

R1 envoie ses logs syslog vers `10.0.0.1:514` (port2 du FortiGate). Les paquets arrivent sur port2 (confirmé par sniffer), mais n'atteignent jamais syslog-ng sur la GNS3 VM.

### Diagnostic détaillé (`diagnose debug flow`)

Pour chaque paquet syslog `10.0.0.2:xxxxx → 192.168.66.128:514` :
1. Nouvelle session créée (session-00000131, 132, 134…) ✅
2. Route trouvée via port1 ✅
3. Trace s'arrête après `__vf_ip_route_input_rcu` ❌
4. Aucune ligne `policy_id`, `accept` ou `deny` n'apparaît jamais
5. Sniffer sur port1 : aucun paquet sortant correspondant

**Conclusion :** le drop est interne au FortiGate, **avant** le moteur de policy. Signature d'un drop au niveau RPF (Reverse Path Forwarding / anti-spoof) ou traitement local-in.

### Tentatives de résolution (toutes échouées)

- Création d'un objet service `SYSLOG` (TCP+UDP/514)
- Ajout de `HOST-R1` (10.0.0.2/32) dans `GRP-INTERNET-ALLOWED`
- Création d'une `local-in-policy` dédiée
- Réordonnancement des policies
- Activation SSH sur port2 (fait, mais non lié au bug)

**Pourquoi ces actions n'ont pas fonctionné :** elles agissent toutes sur le moteur de policy — une couche que le paquet n'atteint jamais.

### Piste de résolution (non encore testée)

Changer la destination syslog sur R1. Au lieu de `10.0.0.1` (l'IP de port2 — l'IP propre du FortiGate), pointer directement vers l'IP de syslog-ng (`192.168.66.128:514`). Le FortiGate serait alors un simple routeur pour ce flux, pas la destination — évitant le traitement local-in.

```
! Sur R1 — à tester
no logging host 10.0.0.1
logging host 192.168.66.128
```

Prérequis : confirmer que `192.168.66.128` est bien l'IP actuelle de la GNS3 VM.

---

## Phase 7 — Active Directory

**Résultat : ✅ Opérationnel**

- Domaine `novaenterprise.com` déployé
- Contrôleur de domaine : WIN-FP37U0DSQU8 (192.168.253.128)
- Poste client Windows 11 PROD01 joint au domaine
- GPO de base configurées
- Scripts PowerShell : backup System State, LAPS v2, tiering, Sysmon
- Phase 3 hardening documentée (GPO naming conventions, AD backup/recovery)

---

## Phase 8 — GitHub

**Résultat : ✅ Repo préparé**

Repo : `nova-corp-network-lab`

Contenu :
- README principal avec diagramme Mermaid de topologie L2/L3
- `docs/architecture.md` — choix et justifications
- `docs/known-issues.md` — Bug A et Bug B
- `docs/topology.svg` — diagramme exportable
- `network/R1.conf` — config sanitisée (placeholders pour secrets)
- `network/switch-L3.conf` — config sanitisée
- `fortigate/policies.conf` — policies sanitisées
- `.gitignore` + licence MIT

---

## Phase 9 — NetPilot AI (en cours)

**Résultat : 🚧 MVP en développement**

Architecture : FastAPI + OpenSearch + sentence-transformers (all-MiniLM-L6-v2) + Netmiko + Anthropic API.

Complété :
- Architecture MVP définie (v0 → v5+)
- `init_indices.py` — 3 index OpenSearch créés (configs, changes, knowledge avec knn_vector fields) — **validé : 11 assertions OK**

Prochaine étape :
- Collecteur Netmiko (SSH vers R1 — déjà accessible)
- Diffs hiérarchiques via `hier_config`
- Endpoint FastAPI `/collect`

---

## Décisions d'architecture majeures — résumé

| Décision | Raison |
|---|---|
| Supervision hors GNS3 (VMware direct) | Bug A (Cloud node/ubridge instable) |
| Lien 10.0.0.0/30 comme seul accès FortiGate | Workaround Bug A |
| 3 policies condensées | Limite licence évaluation (vdom-max=3) |
| Supervision migrée vers 192.168.60.0/24 | Conflit avec VLAN 50 |
| syslog-ng sur GNS3 VM (pas Ubuntu VM) | Proximité réseau avec R1 |
