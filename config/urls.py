from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path, re_path
from django.views.i18n import set_language
from django.views.static import serve

from games.views import health

urlpatterns = [
    path("health/", health, name="health"),
    path("language/", set_language, name="set_language"),
    path("", include("games.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # Uploaded photos: a few small JPEGs per game, so Django serving them is enough here.
    # Move them to object storage (S3, R2...) if traffic ever grows.
    media_prefix = settings.MEDIA_URL.strip("/")
    urlpatterns += [re_path(rf"^{media_prefix}/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT})]

if settings.BROWSER_RELOAD:
    urlpatterns += [path("__reload__/", include("django_browser_reload.urls"))]
