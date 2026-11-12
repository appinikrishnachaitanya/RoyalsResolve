# Manual Cloud Run deployment
The user will deploy manually. No cloud deployment has been attempted. The Docker build context is allowlisted: only frontend source, selected aggregate JSON, report and static server are sent. Raw inputs, DuckDB, Parquet, private artifacts, credentials, Git metadata and model tables are excluded.

Use Node 24 and Docker. The multi-stage Dockerfile builds React and serves only dist with the unprivileged node user. The server uses Cloud Run's PORT variable, normally 8080; no data services are required. `frontend/dist/` is also a host-independent static export.

Local container check:
```powershell
docker build -t royals-resolve .
docker run --rm -p 8080:8080 -e PORT=8080 royals-resolve
```

Set actual values in your shell, then create/select an Artifact Registry Docker repository. Configure a dedicated build service account with Artifact Registry Writer on that repository and logging permissions, plus a runtime service account with no data privileges. Enable Cloud Build, Artifact Registry and Cloud Run APIs. Do not use broad owner credentials as a substitute for scoped roles.

```powershell
$projectId = 'YOUR_PROJECT_ID'
$region = 'YOUR_REGION'
$repository = 'YOUR_ARTIFACT_REGISTRY_REPOSITORY'
$buildAccount = 'BUILD_ACCOUNT@YOUR_PROJECT_ID.iam.gserviceaccount.com'
$runtimeAccount = 'RUNTIME_ACCOUNT@YOUR_PROJECT_ID.iam.gserviceaccount.com'
$revision = git rev-parse --short HEAD
gcloud builds submit --project $projectId --config cloudbuild.yaml --substitutions "_REGION=$region,_REPOSITORY=$repository,_BUILD_SERVICE_ACCOUNT=$buildAccount,SHORT_SHA=$revision" .
$image = "${region}-docker.pkg.dev/${projectId}/${repository}/royals-resolve:${revision}"
gcloud run deploy royals-resolve --project $projectId --region $region --image $image --port 8080 --service-account $runtimeAccount --no-allow-unauthenticated
gcloud run services describe royals-resolve --project $projectId --region $region --format='value(status.url)'
```

Default deployment is authenticated. Make it public only if the competition permits publication of these eligible-player aggregates and that is your intended audience. Verify the served analysis ID, both lists, PDF, mobile view and actual IAM audience. A successful local build does not prove Cloud Run deployment.
