# Betrieb und Voraussetzungen

Terraform >= 1.10, < 2.0; aktueller Remote-State-Lauf geprüft mit 1.14.7. Die fixierten Provider unterstützen die
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

Die Kubernetes-Verbindung nutzt `~/.kube/config`, Kontext `rancher`, mit dem
Cluster-2-Endpunkt `https://rancher.berger.ph/k8s/clusters/c-44q9v`.
OpenBao kontaktiert den nativen API-Endpunkt `https://192.168.1.164:6443` mit der
öffentlichen CA aus `config/cluster2-ca.crt`. Terraform benötigt nur die CA, keinen
persistenten TokenReviewer-Token: ESO authentifiziert sich mit kurzlebigen SA-Tokens.
Der gemeinsame ClusterRole `lab-infra-openbao-tokenreview` muss bereits vorhanden sein und darf
nur `create` auf `authentication.k8s.io/tokenreviews` erlauben. ESO und seine v1-CRDs,
Rancher/OIDC, Realm berger, Harbor und OpenBao sind Plattform-Voraussetzungen.

## OpenSearch und Lab-Runner

Für administrative Terraform-Läufe einen lokalen TLS-Tunnel öffnen:

```bash
kubectl --context=rancher --server=https://rancher.berger.ph/k8s/clusters/c-44q9v \
  port-forward -n opensearch svc/opensearch-cluster-master 19200:9200
```

Der OpenSearch-Provider prüft die öffentliche CA und den Zertifikatsnamen
`opensearch-cluster-master.opensearch.svc.cluster.local`; TLS wird nicht abgeschaltet.
`scripts/lab-terraform.py` liest die bestehenden Lab-Zugänge aus Kubeconfig, OpenBao
und der Keycloak-Bootstrap-Konfiguration in den Prozessspeicher. Dieser Helfer ist
für bestehende Plattformadministratoren vorgesehen, nicht für Mandantenbenutzer.
`TERRAFORM_BIN` muss auf eine passende installierte Terraform-Version zeigen.
Die Systemversion 1.3.9 reicht für S3-Locking nicht aus.

Alternativ `scripts/terraform-admin.py` verwenden und alle Provider- sowie Backend-
Variablen extern bereitstellen. Zusätzlich benötigt: `TF_VAR_opensearch_password`,
`TF_VAR_opensearch_ca_file`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`AWS_SSE_CUSTOMER_KEY`, `AWS_CA_BUNDLE`. Backend-Zugänge und Recovery siehe
[remote-state.md](remote-state.md). Keine gemeinsamen Root-Zugänge an Mandanten ausgeben.

## Import und Recovery

Die historischen Import-IDs von Mandant A stehen in [validation.md](validation.md).
Sie beziehen sich auf Cluster 1 und dürfen nach dem Umzug nicht erneut importiert werden.
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
ClusterSecretStores wählen seit dem Namespace-Self-Service geschützte Projektlabels;
zusätzliche Namespaces erfordern keine Änderung ihrer Konfiguration. Secretwerte und bestehende ExternalSecrets
werden nicht übernommen oder überschrieben.

Nach jedem Apply `terraform plan -detailed-exitcode` ausführen: 0 bedeutet kein Drift,
2 geplante Änderungen, 1 Fehler. ESO-Store und vorhandene ExternalSecrets zusätzlich
auf Ready/SecretSynced prüfen. Eine neue Mandantengruppe allein legt keine Benutzer an.

## Historische Sicherung vor der Remote-State-Migration

Nach der Übernahme liegt eine SOPS-verschlüsselte, durch Entschlüsselung geprüfte
State-Kopie unter `/home/tanzu/manifest/backups/platform-rollout-2026-10-10/tenant-state.sops.json`.
Die passende neue Age-Identität ist getrennt unter
`/home/tanzu/manifest/.local-recovery-keys/platform-20261010.agekey` geschützt abgelegt.
Die zuvor konfigurierte SOPS-Identität war ungültig und wurde nicht verändert.
Für die neue Sicherung die neue Identität ausdrücklich per SOPS_AGE_KEY_FILE wählen.
Ein lokales Backup ersetzt kein Off-host-Backup; Schlüssel separat sichern.

Aktuelle Sicherungen des gemeinsamen Verwaltungs-States und das Recovery-Verfahren stehen in
[remote-state.md](remote-state.md). Die obigen Angaben zur ersten Sicherung sind historisch.

## Dynamische Namespaces und Logging

Namensregeln, Projektlabel-Schutz, Zuständigkeiten und der geprüfte Ablauf stehen in
[namespace-self-service.md](namespace-self-service.md). Terraform besitzt jetzt auch
die Cluster-2-Logging-Routen; Fleet besitzt Collector und generischen Label-Schutz.
Die einmalige Logging-Feldübernahme ist abgeschlossen. `logging_takeover` bleibt im
Normalbetrieb `false`. Die zentrale Pufferbudget-Prüfung muss vor weiteren Mandanten
berücksichtigt werden; zusätzliche Namespaces erzeugen keine eigenen Puffer.
