# Remote-State und Wiederherstellung

Terraform >= 1.10 (geprüft: 1.14.7) verwendet den vorhandenen On-Premises-MinIO-Dienst
auf Cluster 2. GitHub enthält nur Konfiguration und besitzt kein State-Locking.
GitLab HTTP-State wäre geeignet, würde aber eine zusätzliche GitLab-Installation
erfordern. MinIO/S3 wurde einschließlich Locking mit zwei echten Terraform-Prozessen
geprüft und bleibt vollständig On-Premises betreibbar.

## Aufbau und Bootstrap

- Endpoint: `https://192.168.1.197:9000`, Bucket `afi-terraform-state`, Versionierung aktiv.
- State-Key: `lab/<mandant>/terraform.tfstate`, Lock: derselbe Key mit `.tflock`.
- Ein Zugang je Mandant darf nur seinen Präfix lesen/schreiben. Löschen ist auf die
  Lockdatei und isolierte `validation/`-Objekte beschränkt; produktiver State ist geschützt.
- TLS-Prüfung und `encrypt = true` sind aktiviert. SSE-C-Schlüssel werden ausschließlich
  über `AWS_SSE_CUSTOMER_KEY` übergeben; weder Schlüssel noch Zugangsdaten als Backend-CLI-Argument.
- OpenBao: `secret/platform/terraform-state/<mandant>` enthält `access_key`,
  `secret_key`, `sse_customer_key`. Ein Mandanten-Backend-Zugang ist kein Plattform-Adminzugang.
- Terraform-Workspaces werden nicht verwendet. Weitere Plattformumgebungen erhalten
  eigene Backend-Konfiguration und IAM-Präfixe; `dev/test/prod` sind derzeit Namespaces
  innerhalb eines Mandanten-States der Lab-Plattform, keine getrennten States.

Im Plattform-Repository `bootstrap-state.py <mandant>` ausführen; das Skript legt
Bucket-Versionierung, Benutzer und Präfix-Policy idempotent an. Bestehende Schlüssel
werden nicht rotiert. Python-Abhängigkeiten stehen dort unter `scripts/afi-isolation/requirements.txt`.
Danach `scripts/lab-terraform.py <mandant> init -lockfile=readonly` im Mandanten-Repository.
Provider-Verbindungen siehe [operations.md](operations.md).

## Sicherung

MinIO läuft mit einem 20-GiB-Longhorn-Volume und zwei Storage-Replikaten. Das schützt
nicht vor Verlust des gesamten Clusters, versehentlichem administrativem Löschen oder
Verlust des SSE-C-Schlüssels. S3-Versionierung ersetzt keine unabhängige Sicherung.

Im Plattform-Repository:

```bash
export AFI_RECOVERY_KEY=/geschuetzter/pfad/recovery.agekey
export AFI_BACKUP_DIR=/unabhaengiger/backup-pfad
python3 scripts/afi-isolation/backup-state.py mandant-a mandant-b
```

Das Skript liest den aktuellen State mit dem jeweiligen Mandantenzugang, verschlüsselt
State, Backend-Zugang und Versionsmetadaten in getrennte SOPS-Dateien und verifiziert
jede Datei durch Entschlüsselung im Speicher. Keine Secret-Werte werden ausgegeben.
Der Age-Schlüssel muss unabhängig von diesen Dateien gesichert werden. Für diesen Lauf
liegen geprüfte Sicherungen unter `/home/tanzu/manifest/backups/afi-isolation-2026-10-10`;
die geschützte Age-Identität liegt unter
`/home/tanzu/manifest/.local-recovery-keys/platform-20261010.agekey`.
Ein externer Backup-Zielort und ein automatischer Zeitplan sind noch nicht eingerichtet.

## Recovery-Verfahren

1. Terraform-Schreibvorgänge für den betroffenen Mandanten koordinieren und stoppen.
   Einen vorhandenen Lock nicht blind entfernen; erst den Besitzer und laufende Jobs prüfen.
2. Gewünschte S3-Version anhand Zeit, State-Serial und Lineage auswählen. Mit dem
   ursprünglichen SSE-C-Schlüssel lesen. Bei MinIO-Verlust die geprüfte SOPS-Sicherung
   mit der separat aufbewahrten Age-Identität entschlüsseln; nur in einem geschützten
   temporären Verzeichnis (umask 077) arbeiten, niemals in Git oder Terminal ausgeben.
3. Zuerst unter `lab/<mandant>/validation/<lauf>/recovered.tfstate` mit SSE-C wiederherstellen.
   Einen temporären Terraform-Arbeitsbereich mit diesem Backend-Key initialisieren.
   `terraform state list` sowie State-Serial, Lineage, Namespace-Zuordnung und IDs prüfen.
4. Erst nach Freigabe den geprüften State unter Verwendung des normalen Backend-Locks
   zurückspielen (`terraform state push <geschuetzte-datei>` über den Mandanten-Runner).
   Ohne `-force` arbeiten; Lineage-/Serial-Konflikte zuerst untersuchen. Den aktuellen
   State vorher erneut sichern. Eine alte Version kann Ressourcen seit dem Backup
   vergessen; vor Apply zuerst einen Refresh-/Plan prüfen, nicht ungeprüft neu anlegen.
5. Temporäre Klartextdateien und ausschließlich die eigenen Recovery-Testobjekte entfernen.
   Eine Wiederherstellung ist erst abgeschlossen, wenn Plan und reale Ressourcen übereinstimmen.

Am 10.10.2026 erfolgreich getestet: ältere S3-Version auf separaten Recovery-Key kopiert,
mit Terraform initialisiert und `terraform_data.probe` aus dem wiederhergestellten State
gelesen. Zwei konkurrierende Applies auf einem isolierten State: erster erfolgreich,
zweiter mit `Error acquiring the state lock` abgewiesen. Mandant B erhält HTTP 403 auf
den State von A; ohne SSE-C-Schlüssel wird der Abruf mit HTTP 400 abgelehnt.

Die ursprüngliche lokale State-Datei von A wurde migriert; dessen Ressourcenattribute
blieben dabei unverändert. Die geschützte lokale `.backup`-Datei ist eine historische
Sicherung, keine aktive State-Quelle. Niemals wieder ohne den S3-Backend-Block anwenden.
