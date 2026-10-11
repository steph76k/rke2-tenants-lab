# RKE2 Lab – Mandanten mit Terraform

Ein Mandant wird durch `tenants/<name>.json` beschrieben. Terraform verwaltet seine
Keycloak-Gruppen im Realm `berger`, das Rancher-Projekt, Namespaces, private
Harbor-Projekte und Projektmitgliedschaften, OpenBao/ESO sowie isolierte
OpenSearch-Leserollen und Dashboards-Tenants. A/B liegen vollständig auf Cluster 2.
Jeder Mandant erhält zwei persistente Egress-IP-Adressen und zwei Cilium-Policies,
je eine pro Worker. Details und Ausfallgrenzen: [Egress](docs/egress.md).

Lokaler Pfad: `/home/tanzu/manifest/fleet/rke2-tenants-lab`.
Remote: `git@github.com:steph76k/rke2-tenants-lab.git`.
Plattforminstallationen, Logging-Collector und OIDC-Clients bleiben in `rke2-platform-lab`.
Cluster-2-Logging-Routen und dynamische Mandanten-Selector verwaltet dieses Terraform-Repo.

## Mandanten und Rechte

Mandant A wurde übernommen; Mandant B ist ein zusätzlicher PoC-Testmandant.
Bestehende Benutzer werden nicht automatisch in neue Gruppen aufgenommen.

| Keycloak-Gruppe | Rancher | Harbor | OpenSearch |
| --- | --- | --- | --- |
| `<mandant>` | bisher konfigurierte Projektrolle | keine automatische Zuweisung | keine automatische Zuweisung |
| `<mandant>-developers` | Project Member | Developer, eigenes privates Projekt | keine automatische Zuweisung |
| `<mandant>-admins` | Project Owner | Project Admin, eigenes privates Projekt | keine automatische Zuweisung |
| `<mandant>-logs-readers` | keine automatische Zuweisung | keine automatische Zuweisung | eigene Logindizes und Saved Objects lesen |

Ein Benutzer kann mehrere ausdrücklich zugewiesene Gruppen haben. Logleser dürfen
keine Logs schreiben. Plattformadministratoren stellen die Index-Patterns bereit.
Kein Mandanten-Modul verwaltet globale Adminrechte oder bestehende Benutzerkonten.

Die fünf dienstbezogenen Plattform-Admin-Gruppen und die additive Mitgliedschaft
von `berger/admin` verwaltet das Terraform-Root-Modul separat:
[Plattformadministration](docs/platform-admins.md).
Auch der gemeinsame [Rancher-/Keycloak-Logout](docs/rancher-oidc-logout.md)
wird über Terraform konfiguriert.
[OpenSearch: globale Indexansichten und Logout](docs/opensearch-platform-ui.md)
beschreibt die Plattformansicht für Administratoren.

## Neuen Mandanten hinzufügen

Voraussetzungen und Zugänge: [Betrieb](docs/operations.md), [Remote-State](docs/remote-state.md).
Terraform **>= 1.11** ist wegen Write-only-OIDC-Secrets erforderlich; getestet wird mit 1.14.7.

```bash
python3 scripts/new-tenant.py mandant-c --name 'Mandant C'
# Nach Öffnen des dokumentierten OpenSearch-Tunnels und mit administrativem Lab-Zugang:
python3 scripts/lab-terraform.py init -lockfile=readonly
python3 scripts/lab-terraform.py plan -out=tenants.tfplan
python3 scripts/lab-terraform.py apply tenants.tfplan
```

`TERRAFORM_BIN` wählt bei Bedarf eine andere Terraform-Binärdatei. Der Lab-Runner
liest vorhandene administrative Zugänge nur in den Prozessspeicher; er ist für den
Plattformoperator gedacht. `scripts/terraform-admin.py` ist die Alternative für
bereits sicher bereitgestellte Umgebungsvariablen, etwa spätere eingeschränkte CI-Zugänge.

`new-tenant.py` reserviert automatisch zwei freie Adressen aus `192.168.1.200–220`.
Die Reservierungen stehen dauerhaft in der Mandantendatei; bestehende Mandanten
werden nicht neu nummeriert.

Logging-Routen entstehen beim Terraform-Apply automatisch. Die Plattformadministration
legt weiterhin das Dashboards-Index-Pattern für den neuen Mandanten an.
Admins und Developers können zusätzliche Namespaces mit dem Präfix `<mandant>-` direkt
im eigenen Rancher-Projekt erstellen. Egress, Logging und ESO erfassen sie automatisch
über geschützte Projektlabels; kein zusätzlicher Apply oder Namespace-Import nötig.
Details: [Namespace Self-Service](docs/namespace-self-service.md).

Argo-CD-AppProjects, Repo-Freigaben und Admin-/Developer-Rechte entstehen ebenfalls
über Terraform. Fachbereiche verwalten ihre Anwendungsmanifeste in eigenen Repositories.
Anleitung und Grenzen: [Argo CD](docs/argocd.md).

Alle Mandantengruppen erhalten im Lab lesenden Zugriff auf das zentrale, clusterweite
Monitoring. Diese Freigabe ist ausdrücklich nicht mandantengetrennt und wird ebenfalls
über Terraform verwaltet: [Monitoring-Zugriff](docs/monitoring.md).

## State und Lebenszyklus

Alle Mandanten werden zentral in **einem** verschlüsselten State unter
`lab/tenants/terraform.tfstate` im privaten MinIO-Bucket `afi-terraform-state` verwaltet.
Nur die Plattformadministration erhält den technischen Backend-Zugang. Ein natives
S3-Lock schützt die gesamte Mandantenverwaltung vor konkurrierenden Änderungen.
Terraform-Arbeitsdaten liegen unter `.terraform/tenants/`. Jeder normale Plan prüft alle
Dateien in `tenants/`; ein neuer Mandant benötigt keinen eigenen Backend-Zugang.
Die Projekt-, Namespace- und Datenrechte der Mandanten bleiben davon unabhängig.

Die früheren States für A/B wurden zusammengeführt und bleiben als historische,
schreibgeschützte Rückfallsicherung erhalten. Der alte Einzelmandanten-Runner verweigert
weitere Aufrufe. State, Pläne und Zugangsdaten gehören niemals in Git.
Bootstrap, Sicherung und Wiederherstellung: [Remote-State](docs/remote-state.md).

Bestehende Ressourcen vor dem ersten Apply importieren. `prevent_destroy` schützt
wichtige Gruppen, Projekte, Namespaces und OpenBao-Datenspeicher. Das Entfernen einer
Modulkonfiguration kann diesen Schutz umgehen: Offboarding benötigt einen eigenen,
geprüften Ablauf. Das Repository ersetzt keine vollständige Netzwerk-, Quota- oder
Anwendungsisolation; diese Grenzen bleiben ausdrücklich bestehen.
