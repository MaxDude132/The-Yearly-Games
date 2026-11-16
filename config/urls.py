from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.views.i18n import set_language

from games.views import health

urlpatterns = [
    path("health/", health, name="health"),
    path("language/", set_language, name="set_language"),
    path("", include("games.urls")),
]

if settings.DEBUG:
    # Local photos in media/. In production they come straight from the S3 bucket.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.BROWSER_RELOAD:
    urlpatterns += [path("__reload__/", include("django_browser_reload.urls"))]
