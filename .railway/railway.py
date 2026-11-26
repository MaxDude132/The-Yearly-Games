"""Railway Infrastructure as Code for The Yearly Games (Python authoring, beta).

Railway does not read this file during deploys: the Railway CLI compares it with the project and
applies the difference after confirmation. Use the Makefile, which runs the CLI inside the uv
environment (where railway_sdk is installed) and refuses to run against any other linked project:

    make infra-plan     preview the changes
    make infra-apply    apply them

The only secret, DJANGO_SECRET_KEY, is declared with preserve(): its value lives in Railway, never in
this file. Set it once with `railway variable set` (see README, Deploying). The database and bucket
credentials are references, filled in by Railway.
"""

from railway_sdk import bucket, define_railway, github, postgres, preserve, project, service, volume

PROJECT = "the-yearly-games"
REPOSITORY = "MaxDude132/The-Yearly-Games"
BRANCH = "main"
# Where the photo bucket lives: sjc, iad, ams or sin. It cannot change once the bucket exists.
BUCKET_REGION = "iad"
# The site's address. Django only answers for hosts it knows, so the same value goes in DJANGO_ALLOWED_HOSTS.
DOMAIN = "yearlygames.maximetoussaint.com"
# The port gunicorn listens on (gunicorn.conf.py reads PORT). Pinning it here keeps the domain, the
# health check and the app on the same port, instead of relying on defaults.
PORT = 8000
# The Railway region of the web service, the database and its volume.
REGION = "us-east4-eqdc4a"


@define_railway
def main(ctx=None):
    db = postgres("postgres", region=REGION)
    # The database disk: 50 GB, resizable online, with usage alerts.
    db_volume = volume(
        "postgres-volume",
        {
            "alerts": {"usage": {"80": {}, "95": {}, "100": {}}},
            "allowOnlineResize": True,
            "region": REGION,
            "sizeMB": 50000,
        },
    )
    # Uploaded photos. Railway buckets are always private; the app links photos with signed URLs.
    photos = bucket("photos", region=BUCKET_REGION)

    web = service(
        "web",
        source=github(REPOSITORY, branch=BRANCH),
        build={"buildEnvironment": "V3", "builder": "DOCKERFILE", "dockerfilePath": "Dockerfile"},
        # Migrate and reload the game content before each deploy goes live; a failure stops the deploy.
        preDeploy="sh scripts/predeploy.sh",
        # Railway switches traffic once /health/ answers (it checks the database too).
        healthcheck="/health/",
        healthcheckTimeout=120,
        replicas={REGION: 1},
        domains=[{"domain": DOMAIN, "port": PORT}],
        deploy={"restartPolicyMaxRetries": 5},
        env={
            "DATABASE_URL": db.env.DATABASE_URL,
            "DJANGO_SECRET_KEY": preserve(),
            "PORT": str(PORT),
            "DJANGO_ALLOWED_HOSTS": DOMAIN,
            # The bucket's own variables, under the names django-storages reads (see config/settings.py).
            "AWS_STORAGE_BUCKET_NAME": photos.env.BUCKET,
            "AWS_ACCESS_KEY_ID": photos.env.ACCESS_KEY_ID,
            "AWS_SECRET_ACCESS_KEY": photos.env.SECRET_ACCESS_KEY,
            "AWS_S3_REGION_NAME": photos.env.REGION,
            "AWS_S3_ENDPOINT_URL": photos.env.ENDPOINT,
            # Railway buckets use virtual-hosted URLs (the bucket name in the host name).
            "AWS_S3_ADDRESSING_STYLE": "virtual",
        },
    )

    return project(PROJECT, resources=[web, db, db_volume, photos])
