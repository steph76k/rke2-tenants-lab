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
# Nach Öffnen des dokumentierten OpenSearch-Tunnels und mit administrativem Lab-Zugang:
python3 scripts/lab-terraform.py init -lockfile=readonly
python3 scripts/lab-terraform.py plan -out=tenants.tfplan
python3 scripts/lab-terraform.py apply tenants.tfplan
```

`TERRAFORM_BIN` wählt bei Bedarf eine andere Terraform-Binärdatei. Der Lab-Runner
liest vorhandene administrative Zugänge nur in den Prozessspeicher; er ist für den
Plattformoperator gedacht. `scripts/terraform-admin.py` ist die Alternative für
bereits sicher bereitgestellte Umgebungsvariablen, etwa spätere eingeschränkte CI-Zugänge.

Anschließend den administrativen Namespace-Katalog im Plattform-Repository ergänzen,
Logging-Routen über Fleet ausrollen und mandantenspezifische Index-Patterns anlegen.
Ohne diese Plattformschritte werden neue Namespace-Logs weiterhin ausschließlich im
Plattformbereich gesammelt. Ein fehlender Katalogeintrag gibt keine fremden Logs frei.

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
