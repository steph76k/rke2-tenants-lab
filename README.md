# RKE2 Lab – Mandanten mit Terraform

Ein Mandant wird durch `tenants/<name>.json` beschrieben. Terraform verwaltet seine
Keycloak-Gruppen im Realm `berger`, das Rancher-Projekt, Namespaces, private
Harbor-Projekte und Projektmitgliedschaften, OpenBao/ESO sowie isolierte
OpenSearch-Leserollen und Dashboards-Tenants.

Lokaler Pfad: `/home/tanzu/manifest/fleet/rke2-tenants-lab`.
Remote: `git@github.com:steph76k/rke2-tenants-lab.git`.
Plattforminstallationen, Logging und OIDC-Clients bleiben in `rke2-platform-lab`.

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

## Neuen Mandanten hinzufügen

Voraussetzungen und Zugänge: [Betrieb](docs/operations.md), [Remote-State](docs/remote-state.md).
Terraform **>= 1.10** ist wegen S3-Lockdateien erforderlich; getestet wird mit 1.14.7.

```bash
python3 scripts/new-tenant.py mandant-c --name 'Mandant C'
# Im Plattform-Repository einmal den getrennten Backend-Zugang bereitstellen:
python3 ../rke2-platform-lab/scripts/afi-isolation/bootstrap-state.py mandant-c
# Nach Öffnen des dokumentierten OpenSearch-Tunnels und mit administrativem Lab-Zugang:
python3 scripts/lab-terraform.py mandant-c init -lockfile=readonly
python3 scripts/lab-terraform.py mandant-c plan -out=mandant-c.tfplan
python3 scripts/lab-terraform.py mandant-c apply mandant-c.tfplan
```

`TERRAFORM_BIN` wählt bei Bedarf eine andere Terraform-Binärdatei. Der Lab-Runner
liest vorhandene administrative Zugänge nur in den Prozessspeicher; er ist für den
Plattformoperator gedacht. `scripts/terraform-tenant.py` ist die Alternative für
bereits sicher bereitgestellte Umgebungsvariablen, etwa spätere eingeschränkte CI-Zugänge.

Anschließend den administrativen Namespace-Katalog im Plattform-Repository ergänzen,
Logging-Routen über Fleet ausrollen und mandantenspezifische Index-Patterns anlegen.
Ohne diese Plattformschritte werden neue Namespace-Logs weiterhin ausschließlich im
Plattformbereich gesammelt. Ein fehlender Katalogeintrag gibt keine fremden Logs frei.

## State und Lebenszyklus

Jeder Mandant hat einen eigenen verschlüsselten State unter
`lab/<mandant>/terraform.tfstate` im privaten MinIO-Bucket `afi-terraform-state`.
Der Backend-Zugang ist auf diesen Mandanten beschränkt. Native S3-Lockdateien verhindern
konkurrierende Änderungen desselben States; unterschiedliche Mandanten sind unabhängig.
Terraform-Arbeitsdaten liegen separat unter `.terraform/<mandant>/`.
State, Pläne und Zugangsdaten gehören niemals in Git. Details zu Versionierung,
SSE-C, Sicherung und Wiederherstellung stehen in [Remote-State](docs/remote-state.md).

Bestehende Ressourcen vor dem ersten Apply importieren. `prevent_destroy` schützt
wichtige Gruppen, Projekte, Namespaces und OpenBao-Datenspeicher. Das Entfernen einer
Modulkonfiguration kann diesen Schutz umgehen: Offboarding benötigt einen eigenen,
geprüften Ablauf. Das Repository ersetzt keine vollständige Netzwerk-, Quota- oder
Anwendungsisolation; diese Grenzen bleiben ausdrücklich bestehen.
