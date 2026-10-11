# Validierung am 10.10.2026

- `terraform fmt`, `init -lockfile=readonly` und `validate`: erfolgreich.
- Bestehende Gruppe, Rancher-Projekt, Kubernetes-Namespaces, OpenBao-Namespace/KV/Auth/
  Policy/Rolle und ESO-ServiceAccount/RBAC/Store importiert.
- Finaler Apply: neues privates Harbor-Projekt und Projektgruppenbindung; bestehender
  SecretStore in Terraform-Feldverwaltung übernommen. Keine Löschungen.
- Nachgelagerter vollständiger Plan: **No changes**.
- Temporäre Konfiguration `mandant-validation`: Plan mit exakt 16 Creates ausschließlich
  für diesen Mandanten; Mandant A unverändert. Kein Apply; Testdatei entfernt.
- Rancher-OIDC mit eigenem temporären Benutzer in Gruppe mandant-a: Login HTTP 201,
  Projekt Mandant A HTTP 200; fremdes Project-1 HTTP 403/404. Testidentität entfernt.
- Automount des vorhandenen ESO-ServiceAccounts bleibt false. Bestehende Rancher-
  Namespace-Metadaten bleiben erhalten. OpenBao-Policy und Auth-Konfiguration unverändert.
- Ein initialer Store-Apply kollidierte lediglich wegen umsortierter Namespace-Liste
  mit kubectl-client-side-apply; Reihenfolge erhalten, ohne erzwungene Übernahme korrigiert.

| Ressource | Import-ID |
| --- | --- |
| Keycloak-Gruppe | berger/709d7143-bdd2-4264-b6f5-bcc926e80be3 |
| Rancher-Projekt | c-m-prkskj2p:p-9nh78 |
| Namespaces | mandant-a-dev, mandant-a-test, mandant-a-prod |
| OpenBao-Namespace | mandant-a |
| KV-Mount im Namespace mandant-a | secret |
| Auth-Mount im Namespace mandant-a | rke2-cluster1 |
| Kubernetes-Auth-Konfiguration | auth/rke2-cluster1/config |
| ESO-Policy im Namespace mandant-a | eso-read |
| ESO-Rolle im Namespace mandant-a | auth/rke2-cluster1/role/eso-mandant-a |
| ServiceAccount | external-secrets/openbao-mandant-a |
| TokenReview-Bindung | openbao-mandant-a-tokenreviewer |
| SecretStore | apiVersion=external-secrets.io/v1,kind=ClusterSecretStore,name=openbao-mandant-a |

Provider: rancher2 15.1.2, keycloak 5.10.0, harbor 3.12.5, kubernetes 3.3.0,
vault 5.12.0. Quellen: [Rancher-Provider](https://github.com/rancher/terraform-provider-rancher2),
[Keycloak-Provider](https://github.com/keycloak/terraform-provider-keycloak),
[Harbor-Provider](https://github.com/goharbor/terraform-provider-harbor),
[Vault-Provider](https://github.com/hashicorp/terraform-provider-vault/tree/v5.12.0).

## Gemeinsamer administrativer State am 11.10.2026

- A/B zusammengeführt: 56 verwaltete Ressourceninstanzen, identische Adressen und
  Ressourcenattribute; keine Ressource angelegt, geändert oder gelöscht.
- Beide Quellstates während der Migration gesperrt und zusammen mit Backend-Zugängen
  SOPS-verschlüsselt gesichert; Entschlüsselung im Speicher verifiziert.
- Neuer zentraler State: `lab/tenants/terraform.tfstate`; abschließender Plan Exitcode 0.
- Alter Einzelmandanten-Runner blockiert; alte Backend-Zugänge schreibgeschützt.
- Gesetztes zentrales S3-Lock verhindert einen normalen Terraform-Plan.
- Temporäre neue Mandantendatei: exakt 28 Creates, keine Änderung an A/B; kein Apply.
  Testdatei entfernt und danach erneut leerer Plan.
- Bereinigte Nachweise: `tests/results/shared-state-migration.json` und
  `tests/results/shared-state-validation.json`.

## Cluster-2-Migration und Egress am 11.10.2026

Die oben genannten Cluster-1-Import-IDs sind historisch. Aktuell: A `c-44q9v:p-p2q7n`,
B `c-44q9v:p-j79sh`, OpenBao-Kubernetes-Auth jeweils `rke2-cluster2`.
Alle alten clustergebundenen Tenant-Ressourcen wurden nach Sicherung und Prüfung entfernt;
KV-Daten und historische Logzugriffe bleiben erhalten.

- Rancher-Projekt-Isolation: 16/16 positive/negative Netzwerkfälle über beide Worker.
- Rancher-OIDC: A/B-Developers sowie bestehende Gruppe A; eigene Projekte und
  Namespace-Podlisten 200, fremde 403, PKCE S256, Prüfidentitäten entfernt.
- Egress-IP-Nachweis: A `.200/.201`, B `.202/.203`, jeweils am externen LAN-Empfänger.
- Neuer Mandant: `.204/.205`, zwei persistente Adressen und zwei Policies automatisch;
  insgesamt 32 Creates, nur Reservierungsliste geändert, keine Änderungen an A/B.
  Nur Plan, kein Apply; Testdeklaration entfernt.
- Drei migrierte A-Secrets vor Quellbereinigung identisch, alle ESO-Stores Ready.
- Shared-State-Egress-Apply: neun neue Instanzen, keine Löschung; danach 65 verwaltete
  Ressourceninstanzen. Vollständiger nachgelagerter Plan ohne Änderungen.

Nachweise: `tests/results/cluster2-migration.json`, `project-isolation-cluster2.json`,
`rancher-access-cluster2.json`, `egress-cluster2.json`, `new-tenant-egress-plan.json`.
Logging-/Collector-Nachweise stehen im Plattformrepo. Betriebsgrenzen: [Egress](egress.md).
