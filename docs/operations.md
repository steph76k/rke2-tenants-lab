# Betrieb und Voraussetzungen

Terraform >= 1.3, < 2.0; getestet mit 1.3.9. Die fixierten Provider unterstützen die
hier genutzten APIs. `hashicorp/vault` wird für OpenBao 2.7.0 verwendet, mit ausgeschalteter
Vault-Versionserkennung und ohne Erzeugung eines Child-Tokens. TLS-Prüfung bleibt aktiv.

Authentifizierung nur über Prozessumgebung oder interaktive, geschützte lokale Abläufe:

| Variable | Inhalt |
| --- | --- |
| `RANCHER_TOKEN_KEY` | Rancher-API-Token mit den erforderlichen Projekt-/RBAC-Rechten |
| `KEYCLOAK_USER`, `KEYCLOAK_PASSWORD` | Verwaltungszugang für den Realm; Provider-Anmeldung über master/admin-cli |
| `HARBOR_USERNAME`, `HARBOR_PASSWORD` | Zugang zum Anlegen/Verwalten der Mandantenprojekte |
| `VAULT_TOKEN` | OpenBao-Verwaltungszugang für Mandanten-Namespaces |
| `SSL_CERT_FILE` | CA-Bundle aus System-CAs plus öffentlicher Lab-CA für Harbor |

Keine Secret-Werte in `.tfvars`, Shell-History oder Git schreiben. Für das Lab wurden
die bestehenden Administratorzugänge nur im Prozessspeicher verwendet. Für Team-/CI-Betrieb
separate eingeschränkte Servicekonten bereitstellen. `VAULT_NAMESPACE` muss für reguläre
Pläne leer sein; Ressourcen wählen ihren Mandanten-Namespace explizit.

Die Kubernetes-Verbindung nutzt `~/.kube/config`, Kontext `rke2-cluster1`.
OpenBao kontaktiert den nativen API-Endpunkt `https://192.168.1.23:6443` mit der
öffentlichen CA aus `config/cluster1-ca.crt`. Terraform benötigt nur die CA, keinen
persistenten TokenReviewer-Token: ESO authentifiziert sich mit kurzlebigen SA-Tokens.
Der gemeinsame ClusterRole `openbao-tokenreviewer` muss bereits vorhanden sein und darf
nur `create` auf `authentication.k8s.io/tokenreviews` erlauben. ESO und seine v1-CRDs,
Rancher/OIDC, Realm berger, Harbor und OpenBao sind Plattform-Voraussetzungen.

## Import und Recovery

Die geprüften Import-IDs von Mandant A stehen in [validation.md](validation.md).
Der Vault-Provider übernimmt bei CLI-Imports die Ressourcen-Namespace-Angabe nicht
zuverlässig. Beim Import eines OpenBao-Unterobjekts muss der Provider temporär auf
`mandant-a` zeigen. Anschließend muss auch dessen State-Attribut `namespace` ausdrücklich
`mandant-a` enthalten, bevor der normale Root-Provider wieder genutzt wird.
Ein Import ohne diese Prüfung kann fälschlich ein gleichnamiges Root-Objekt lesen.

Im Erstlauf wurde diese Eigenheit vor jedem Apply erkannt und nur im lokalen State
korrigiert; der vollständige Refresh-/Plan zeigte danach keine Änderung an OpenBao.
Ein State-Backup wurde vorher geschützt gesichert. Kein Root-Mount und keine Root-Policy
wurden durch Terraform verändert. Bei State-Recovery diese Zuordnung und die Accessor-IDs
mit OpenBao vergleichen; nicht blind die Importbefehle wiederholen.

Kubernetes-Namespaces behalten Rancher-eigene Metadaten durch gezielte `ignore_changes`.
Das ClusterSecretStore-Manifest behält die deklarierte Namespace-Reihenfolge; dadurch
war die Übernahme ohne `force_conflicts` möglich. Secretwerte und bestehende ExternalSecrets
werden nicht übernommen oder überschrieben.

Nach jedem Apply `terraform plan -detailed-exitcode` ausführen: 0 bedeutet kein Drift,
2 geplante Änderungen, 1 Fehler. ESO-Store und vorhandene ExternalSecrets zusätzlich
auf Ready/SecretSynced prüfen. Eine neue Mandantengruppe allein legt keine Benutzer an.

## Verifizierte State-Sicherung

Nach der Übernahme liegt eine SOPS-verschlüsselte, durch Entschlüsselung geprüfte
State-Kopie unter `/home/tanzu/manifest/backups/platform-rollout-2026-10-10/tenant-state.sops.json`.
Die passende neue Age-Identität ist getrennt unter
`/home/tanzu/manifest/.local-recovery-keys/platform-20261010.agekey` geschützt abgelegt.
Die zuvor konfigurierte SOPS-Identität war ungültig und wurde nicht verändert.
Für die neue Sicherung die neue Identität ausdrücklich per SOPS_AGE_KEY_FILE wählen.
Ein lokales Backup ersetzt kein Off-host-Backup; Schlüssel separat sichern.
