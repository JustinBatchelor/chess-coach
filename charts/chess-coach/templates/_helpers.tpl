{{- define "chess-coach.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{- define "chess-coach.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := include "chess-coach.name" . -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end }}

{{- define "chess-coach.labels" -}}
app.kubernetes.io/name: {{ include "chess-coach.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | quote }}
{{- end }}

{{- define "chess-coach.selectorLabels" -}}
app.kubernetes.io/name: {{ include "chess-coach.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "chess-coach.image" -}}
{{- if .Values.image.digest -}}
{{ printf "%s@%s" .Values.image.repository .Values.image.digest }}
{{- else -}}
{{ printf "%s:%s" .Values.image.repository .Values.image.tag }}
{{- end -}}
{{- end }}

{{- define "chess-coach.sessionSecret" -}}
{{- default (printf "%s-session" (include "chess-coach.fullname" .)) .Values.session.existingSecret -}}
{{- end }}

{{- define "chess-coach.databaseSecret" -}}
{{- if .Values.postgresql.enabled -}}
{{ printf "%s-postgresql" (include "chess-coach.fullname" .) }}
{{- else -}}
{{ required "database.existingSecret is required when postgresql.enabled=false" .Values.database.existingSecret }}
{{- end -}}
{{- end }}
