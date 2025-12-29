{{/*
Expand the name of the chart.
*/}}
{{- define "ryumem.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "ryumem.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "ryumem.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "ryumem.labels" -}}
helm.sh/chart: {{ include "ryumem.chart" . }}
{{ include "ryumem.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "ryumem.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ryumem.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "ryumem.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "ryumem.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Dashboard fullname
*/}}
{{- define "ryumem.dashboard.fullname" -}}
{{- printf "%s-dashboard" (include "ryumem.fullname" .) }}
{{- end }}

{{/*
Dashboard labels
*/}}
{{- define "ryumem.dashboard.labels" -}}
helm.sh/chart: {{ include "ryumem.chart" . }}
{{ include "ryumem.dashboard.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Dashboard selector labels
*/}}
{{- define "ryumem.dashboard.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ryumem.name" . }}-dashboard
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
